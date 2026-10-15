"""Plan B Laya — ¿mejora el ensemble el modelo afinado (`laya-integra3`)? **No.**

Mide, sobre el benchmark interno de 300 notas (`casos_300.jsonl`), con el ensemble
desplegado (`0,6 · híbrido ⊕ 0,4 · Laya`):

  1) los motores y los dos ensembles (con Laya **base** vs **afinado**);
  2) la **sensibilidad de entrada** del modelo afinado: la misma nota servida como
     manifestaciones GOLD (las del dataset = las del entrenamiento), como las que detecta
     el MATCHER (pipeline real) o como la NOTA cruda.

El modelo afinado se alimenta con el `state`/`criteria` EXACTOS del fine-tune
("Conductas observadas: … Nota de la educadora: …" + criteria "Nivel l: …").

    python -m bench.eval_laya_planb                          # requiere el entorno de integra-server
    python -m bench.eval_laya_planb --modelo-integra /opt/integra/models/laya-integra3 --limite 50

⚠️ Requiere la librería `laya` y el checkpoint afinado (solo viven en integra-server). El
   fine-tune se entrenó con datos derivados del MISMO dataset que el benchmark → sus números
   están INFLADOS; el script sirve para comparar, no como verdad de campo.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import laya

from src import marco
from src.backend_decision import Dec, DecisorHibrido, DecisorLaya, _dominios_de_matches, _norm9
from src.clasificador import Clasificador
from src.modelo_decision import clamp01

AQUI = Path(__file__).parent
DATA = AQUI.parent / "data"
NIVELES = list(range(1, 10))
W = 0.6                       # peso del híbrido en el ensemble (como en producción)
INSTR = ("Segun las conductas observadas de un nino o nina de educacion parvularia, "
         "a que nivel de la ruta de desarrollo corresponde?")


def _criteria() -> dict[str, str]:
    out = {}
    for l in NIVELES:
        i = marco.nivel_info()[l]
        out[str(l)] = (f'Nivel {l}: {i["nombre_nivel"]} '
                       f'({i["edad_min_meses"]}-{i["edad_max_meses"]} meses). {i["descripcion"]}')
    return out


def cargar_casos(archivo: str) -> list[dict]:
    man = {r["id_manifestacion"]: r["texto_observable"]
           for r in csv.DictReader(open(DATA / "manifestaciones.csv", encoding="utf-8"))}
    links: dict[str, list[str]] = {}
    for r in csv.DictReader(open(DATA / "observacion_manifestaciones.csv", encoding="utf-8")):
        links.setdefault(r["id_observacion"], []).append(r["id_manifestacion"])
    raw = (AQUI / archivo).read_text(encoding="utf-8").strip()
    items = json.loads(raw) if raw.startswith("[") else [json.loads(l) for l in raw.splitlines() if l.strip()]
    casos = []
    for c in items:
        gold = " ".join(man[m] for m in links.get(c.get("id_observacion"), []) if m in man)
        casos.append({"guion": c["guion"], "nivel": c["nivel"], "edad": c.get("edad"),
                      "man": gold or c["guion"]})
    return casos


class DecisorLayaFine(DecisorLaya):
    """Laya afinado: construye el state/criteria EXACTOS del fine-tune."""

    def _state_fine(self, manif: str, nota: str) -> str:
        s = "Conductas observadas: " + (manif or "")
        return s + (f" Nota de la educadora: {nota}" if nota else "")

    def predecir(self, manif: str, nota: str) -> int | None:
        q = {"nivel": {"type": "choice", "instructions": INSTR, "criteria": _criteria()}}
        try:
            r = self._pred(self._state_fine(manif, nota), q)
            return int(r["answers"]["nivel"]["choice"])
        except Exception:  # noqa: BLE001
            return None


def _acc(pares: list, tol: int = 0) -> float:
    return sum(1 for p, g in pares if p is not None and abs(p - g) <= tol) / len(pares)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--casos", default="casos_300.jsonl")
    ap.add_argument("--modelo-integra", default="/opt/integra/models/laya-integra3")
    ap.add_argument("--limite", type=int, default=None)
    a = ap.parse_args()

    casos = cargar_casos(a.casos)
    if a.limite:
        casos = casos[:a.limite]

    hib = DecisorHibrido()
    laya_base = DecisorLaya()
    laya_fine = DecisorLayaFine(model_path=a.modelo_integra, nombre="laya-integra3")
    matcher = Clasificador(backend="hibrido").matcher

    motores = {k: [] for k in ("hibrido", "base", "integra3", "ens_base", "ens_integra3")}
    sens = {k: [] for k in ("gold", "matcher", "nota")}   # sensibilidad de entrada del afinado

    for c in casos:
        nota, edad, gold_lvl = c["guion"], c["edad"], c["nivel"]
        matches = matcher.matchear(nota)
        esperados = marco.niveles_esperados_por_edad(edad) if edad is not None else []
        man_matcher = " ".join(dict.fromkeys(m.manifestacion["texto"] for m in matches))

        d_h = hib.decidir(nota, matches, edad, esperados)
        d_b = laya_base.decidir(nota, matches, edad, esperados)
        p1, p2b = _norm9(d_h.probabilidades), _norm9(d_b.probabilidades)
        comb_b = {l: W * p1[l] + (1 - W) * p2b[l] for l in NIVELES}
        n_b = max(NIVELES, key=lambda l: comb_b[l])

        # afinado alimentado con el pipeline REAL (manifestaciones del matcher + nota)
        q = {"nivel": {"type": "choice", "instructions": INSTR, "criteria": _criteria()}}
        pred_f, p2f = None, {l: 0.0 for l in NIVELES}
        try:
            ans = laya_fine._pred(laya_fine._state_fine(man_matcher, nota), q)["answers"]["nivel"]
            pred_f = int(ans["choice"])
            p2f = _norm9({int(k): float(v) for k, v in (ans.get("probabilities") or {}).items()})
        except Exception:  # noqa: BLE001
            pass
        comb_f = {l: W * p1[l] + (1 - W) * p2f[l] for l in NIVELES}
        n_f = max(NIVELES, key=lambda l: comb_f[l])

        motores["hibrido"].append((d_h.nivel, gold_lvl))
        motores["base"].append((d_b.nivel, gold_lvl))
        motores["integra3"].append((pred_f, gold_lvl))
        motores["ens_base"].append((n_b, gold_lvl))
        motores["ens_integra3"].append((n_f, gold_lvl))

        sens["gold"].append((laya_fine.predecir(c["man"], nota), gold_lvl))
        sens["matcher"].append((pred_f, gold_lvl))
        sens["nota"].append((laya_fine.predecir(nota, ""), gold_lvl))

    print(f"casos={len(casos)} · ensemble {W:.1f}·híbrido ⊕ {1-W:.1f}·Laya\n")
    print(f"{'motor':16} {'exacto':>8} {'±1':>8}")
    print("-" * 34)
    for k in ("hibrido", "base", "integra3", "ens_base", "ens_integra3"):
        print(f"{k:16} {_acc(motores[k]):>8.3f} {_acc(motores[k], 1):>8.3f}")
    print(f"\nlaya-integra3 · sensibilidad de entrada\n{'entrada':10} {'exacto':>8} {'±1':>8}")
    print("-" * 28)
    for k in ("gold", "matcher", "nota"):
        print(f"{k:10} {_acc(sens[k]):>8.3f} {_acc(sens[k], 1):>8.3f}")


if __name__ == "__main__":
    main()
