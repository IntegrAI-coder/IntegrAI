"""Backends de decisión (el "decision model" del diferencial).

  - DecisorHibrido  : matcher + prior etario (rápido, offline). El "caballo de batalla" (mejor exacto).
  - DecisorLaya     : Laya (421M) on-prem -> decisión con probabilidades calibradas (mejor ±1).
  - DecisorEnsemble : combina híbrido ⊕ Laya -> mejor exacto + mejor ±1.
  - verificar()     : Laya como GATE calibrado ("¿es consistente el nivel propuesto?") -> escala si duda.

"El matcher propone la evidencia; el decision model decide Y verifica."
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import config, marco
from .matcher import Match
from .modelo_decision import softmax, clamp01

NIVELES = list(range(1, 10))


def _norm9(d: dict) -> dict[int, float]:
    """Normaliza una distribución a las 9 claves {1..9} sumando 1."""
    out = {l: float(d.get(l, d.get(str(l), 0.0))) for l in NIVELES}
    s = sum(out.values())
    return {l: (v / s if s > 0 else 1 / 9) for l, v in out.items()}


@dataclass
class Dec:
    nivel: int | None
    probabilidades: dict[int, float]
    confianza: float
    suficiente: bool
    dominios: list[str]
    backend: str
    meta: dict[str, Any] = field(default_factory=dict)


def _dominios_de_matches(matches: list[Match], umbral: float = 0.20) -> list[str]:
    doms: list[str] = []
    for m in matches:
        if m.score >= umbral and m.manifestacion["dominio"] not in doms:
            doms.append(m.manifestacion["dominio"])
    return doms


class DecisorBase:
    nombre = "base"

    def decidir(self, texto, matches, edad_meses, esperados, umbral_evidencia=0.5) -> Dec:
        raise NotImplementedError


class DecisorHibrido(DecisorBase):
    nombre = "hibrido"

    def decidir(self, texto, matches, edad_meses, esperados, umbral_evidencia=0.5) -> Dec:
        pesos = {l: 0.0 for l in NIVELES}
        for m in matches:
            pesos[m.manifestacion["nivel"]] += m.score
        logits = [pesos[l] * 2.0 + (0.5 if l in esperados else 0.0) for l in NIVELES]
        total = sum(pesos.values())
        probs = softmax(logits, temperature=0.5) if total > 0 else [1.0 / 9] * 9
        dist = {l: round(p, 4) for l, p in zip(NIVELES, probs)}
        nivel = max(NIVELES, key=lambda l: dist[l]) if total > 0 else None
        evidencia = sum(m.score for m in matches)
        conf = clamp01((dist[nivel] if nivel else 0.0) * (0.55 + 0.45 * min(1.0, evidencia)))
        return Dec(nivel, dist, conf, evidencia >= umbral_evidencia,
                   _dominios_de_matches(matches), self.nombre,
                   {"evidencia": round(evidencia, 3), "n_matches": len(matches)})


class DecisorLaya(DecisorBase):
    """Laya (typesafe). Decide el nivel con probabilidades calibradas + verifica (gate)."""

    def __init__(self, model_path: str | None = None, subfolder: str | None = None,
                 preload: bool = True, nombre: str | None = None) -> None:
        import laya
        self._laya = laya
        self.model_path = model_path
        self.nombre = nombre or ("laya-integra" if model_path else "laya")
        self._agent = None
        if model_path:
            self._agent = laya.load(model_path, device="cpu")
        else:
            self.router = laya.Router(preload=preload)
            self.subfolder = subfolder

    def _pred(self, state: dict, questions: dict) -> dict:
        if self._agent is not None:
            return self._agent.predict(state, questions)
        return self.router.predict(state, questions)

    def _candidatos(self, matches, esperados) -> list[int]:
        if self.model_path:
            return NIVELES
        cand: set[int] = set(esperados or [])
        for m in matches:
            l = m.manifestacion["nivel"]; cand.update({l - 1, l, l + 1})
        cand = {l for l in cand if 1 <= l <= 9}
        return sorted(cand) or NIVELES

    def _state(self, texto, matches, edad_meses, esperados) -> dict:
        return {"observacion": (texto or "")[:2000],
                "edad_meses": f"{edad_meses}" if edad_meses is not None else "no informada",
                "banda_etaria_esperada": ", ".join(str(x) for x in (esperados or [])) or "sin referencia",
                "evidencia_detectada": " | ".join(m.manifestacion["texto"] for m in matches[:6]) or "sin coincidencias claras"}

    def decidir(self, texto, matches, edad_meses, esperados, umbral_evidencia=0.5) -> Dec:
        cand = self._candidatos(matches, esperados)
        crit = {str(l): marco.descripcion_nivel(l) for l in cand}
        state = self._state(texto, matches, edad_meses, esperados)
        questions = {
            "nivel": {"type": "choice",
                      "instructions": "Segun las conductas observadas de un nino o nina de educacion parvularia, "
                                      "a que nivel de la ruta de desarrollo corresponde?",
                      "criteria": crit},
            "evidencia_suficiente": {"type": "noul",
                                     "instructions": "La observacion aporta evidencia suficiente para estimar un nivel?",
                                     "criteria": {"true": "describe conductas observables claras y evaluables",
                                                  "false": "es vaga, muy breve o sin conductas observables"}},
        }
        try:
            res = self._pred(state, questions)
            ans = res["answers"]["nivel"]
            nivel = int(ans["choice"])
            probs = {int(k): float(v) for k, v in ans.get("probabilities", {}).items()}
            conf = float(ans.get("answer_confidence", ans.get("confidence", 0.0)))
            suf = float(res["answers"]["evidencia_suficiente"].get("noul", 0.0)) >= 0.5
            return Dec(nivel, probs, clamp01(conf), suf, _dominios_de_matches(matches), self.nombre,
                       {"routing": res.get("routing"), "usage": res.get("usage"), "candidatos": cand})
        except Exception as e:
            d = DecisorHibrido().decidir(texto, matches, edad_meses, esperados, umbral_evidencia)
            d.meta["fallback"] = f"{self.nombre} error: {e!r}"
            return d

    def verificar(self, texto: str, nivel: int) -> float:
        """GATE: probabilidad calibrada de que `nivel` sea consistente con las conductas."""
        q = {"consistente": {"type": "noul",
                             "instructions": f"El nivel '{nivel}' ({marco.nombre_nivel(nivel)}) es consistente con "
                                             "las conductas observadas?",
                             "criteria": {"true": "las conductas corresponden claramente a ese nivel de desarrollo",
                                          "false": "las conductas no corresponden o son de otro nivel"}}}
        try:
            res = self._pred({"observacion": (texto or "")[:2000]}, q)
            return float(res["answers"]["consistente"].get("noul", 0.5))
        except Exception:
            return 0.5


class DecisorEnsemble(DecisorBase):
    """Combina híbrido ⊕ Laya: `peso_hibrido` del híbrido, el resto de Laya."""
    nombre = "ensemble"

    def __init__(self, peso_hibrido: float = 0.6, base: DecisorBase | None = None,
                 extra: DecisorBase | None = None) -> None:
        self.w = peso_hibrido
        self.base = base or DecisorHibrido()
        self.extra = extra or DecisorLaya()

    def decidir(self, texto, matches, edad_meses, esperados, umbral_evidencia=0.5) -> Dec:
        d1 = self.base.decidir(texto, matches, edad_meses, esperados, umbral_evidencia)
        d2 = self.extra.decidir(texto, matches, edad_meses, esperados, umbral_evidencia)
        p1, p2 = _norm9(d1.probabilidades), _norm9(d2.probabilidades)
        comb = {l: self.w * p1[l] + (1 - self.w) * p2[l] for l in NIVELES}
        nivel = max(NIVELES, key=lambda l: comb[l])
        dist = {l: round(p, 4) for l, p in comb.items()}
        conf = clamp01(dist[nivel] * (0.6 + 0.4 * min(1.0, (d1.meta.get("evidencia", 0.0)))))
        return Dec(nivel, dist, conf, d1.suficiente and d2.suficiente,
                   d1.dominios or d2.dominios, self.nombre,
                   {"hibrido": d1.nivel, "laya": d2.nivel, "peso_hibrido": self.w,
                    "conf_laya": d2.confianza})


def construir_decisor(nombre: str | None = None) -> DecisorBase:
    nombre = (nombre or config.BACKEND_DECISION or "hibrido").lower()
    if nombre in ("ensemble", "ens"):
        try:
            return DecisorEnsemble()
        except Exception:
            return DecisorHibrido()
    if nombre in ("laya-integra", "integra"):
        if config.LAYA_MODEL_PATH:
            try:
                return DecisorLaya(model_path=config.LAYA_MODEL_PATH)
            except Exception:
                pass
        return DecisorHibrido()
    if nombre in ("laya", "auto"):
        try:
            return DecisorLaya()
        except Exception:
            return DecisorHibrido()
    return DecisorHibrido()
