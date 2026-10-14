"""Backends de decisión (el "decision model" del diferencial).

Tres implementaciones intercambiables que producen la MISMA decisión tipada
(nivel 1-9 + probabilidades + confianza + suficiencia):

  - DecisorHibrido  : agrega la evidencia del matcher + prior etario (rápido, offline).
  - DecisorLaya     : Laya (421M) on-prem. Recibe la evidencia + la edad y decide
                      con probabilidades CALIBRADAS.
  - DecisorLayaIntegra : idem, pero con el checkpoint AFINADO con datos de Integra.

"El matcher propone la evidencia; el decision model decide."
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import config, marco
from .matcher import Match
from .modelo_decision import softmax, clamp01


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
        niveles = [n["nivel"] for n in marco.ruta_niveles()]
        pesos = {l: 0.0 for l in niveles}
        for m in matches:
            pesos[m.manifestacion["nivel"]] += m.score
        logits = [pesos[l] * 2.0 + (0.5 if l in esperados else 0.0) for l in niveles]
        total = sum(pesos.values())
        probs = softmax(logits, temperature=0.5) if total > 0 else [1.0 / len(niveles)] * len(niveles)
        dist = {l: round(p, 4) for l, p in zip(niveles, probs)}
        nivel = max(niveles, key=lambda l: dist[l]) if total > 0 else None
        evidencia = sum(m.score for m in matches)
        conf = clamp01((dist[nivel] if nivel else 0.0) * (0.55 + 0.45 * min(1.0, evidencia)))
        return Dec(nivel=nivel, probabilidades=dist, confianza=conf, suficiente=evidencia >= umbral_evidencia,
                   dominios=_dominios_de_matches(matches), backend=self.nombre,
                   meta={"evidencia": round(evidencia, 3), "n_matches": len(matches)})


class DecisorLaya(DecisorBase):
    """Laya (modelo typesafe). Decide el nivel con probabilidades calibradas.

    Si `model_path` está definido, carga ESE checkpoint (p.ej. el afinado con datos
    de Integra) en vez del repo base; en ese caso usa las 9 opciones (como se entrenó).
    """
    nombre = "laya"

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
        if self.model_path:               # checkpoint afinado: se entrenó con las 9
            return list(range(1, 10))
        cand: set[int] = set(esperados or [])
        for m in matches:
            l = m.manifestacion["nivel"]
            cand.update({l - 1, l, l + 1})
        cand = {l for l in cand if 1 <= l <= 9}
        return sorted(cand) or list(range(1, 10))

    def decidir(self, texto, matches, edad_meses, esperados, umbral_evidencia=0.5) -> Dec:
        cand = self._candidatos(matches, esperados)
        crit = {str(l): marco.descripcion_nivel(l) for l in cand}
        state = {
            "observacion": (texto or "")[:2000],
            "edad_meses": f"{edad_meses}" if edad_meses is not None else "no informada",
            "banda_etaria_esperada": ", ".join(str(x) for x in (esperados or [])) or "sin referencia",
            "evidencia_detectada": " | ".join(m.manifestacion["texto"] for m in matches[:6]) or "sin coincidencias claras",
        }
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
            return Dec(nivel=nivel, probabilidades=probs, confianza=clamp01(conf), suficiente=suf,
                       dominios=_dominios_de_matches(matches), backend=self.nombre,
                       meta={"routing": res.get("routing"), "usage": res.get("usage"), "candidatos": cand})
        except Exception as e:
            d = DecisorHibrido().decidir(texto, matches, edad_meses, esperados, umbral_evidencia)
            d.meta["fallback"] = f"{self.nombre} error: {e!r}"
            return d


def construir_decisor(nombre: str | None = None) -> DecisorBase:
    nombre = (nombre or config.BACKEND_DECISION or "hibrido").lower()
    if nombre in ("laya-integra", "integra"):
        p = config.LAYA_MODEL_PATH
        if p:
            try:
                return DecisorLaya(model_path=p)
            except Exception:
                pass
        return DecisorHibrido()
    if nombre in ("laya", "auto"):
        try:
            return DecisorLaya()
        except Exception:
            return DecisorHibrido()
    return DecisorHibrido()
