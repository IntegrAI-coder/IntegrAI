#!/usr/bin/env python3
"""Unifica el dataset sintético E-1 con las divisiones por edad de Integra.

Para cada observación calcula tramo y subtramo con la regla del 31 de marzo y un nivel de rúbrica
TENTATIVO (crosswalk), y reporta la cobertura por tramo. No requiere la rúbrica (solo los tramos).

    python tools/unificar_dataset.py   → bench/dataset_tramos.csv + data/marcos/crosswalk_e1_integra.json

Crosswalk (tentativo, validar con Integra): los 9 niveles E-1 son una progresión por edad de 0 a 36 meses.
  - Sala Cuna:   E-1 L1..L8 → rúbrica 1..8 (ambas recorren el primer tramo en orden).
  - Nivel Medio: E-1 L7, L8 → 1 · L9 → 2 (el dataset solo alcanza el inicio del Medio Menor).
  - Transición: sin datos.
"""
from __future__ import annotations

import collections
import csv
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(RAIZ))

from src import config  # noqa: E402
from src.marcos import edad_al_corte, tramo_por_meses  # noqa: E402
from tools.importar_rubrica import TRAMOS  # noqa: E402


class _SoloTramos:
    """Marco mínimo con los tramos oficiales (sin necesitar el JSON de la rúbrica)."""
    def tramos(self):
        return TRAMOS


def nivel_rubrica(tramo: str, nivel_e1: int) -> int | None:
    if tramo == "sala_cuna":
        return min(nivel_e1, 8)
    if tramo == "nivel_medio":
        return max(1, min(nivel_e1 - 7, 3))
    return None


def main() -> None:
    d = config.datos_dir()
    nac = {r["id_nino"]: r["fecha_nacimiento"] for r in csv.DictReader(open(d / "ninos.csv", encoding="utf-8"))}
    filas, cobertura, cruce = [], collections.Counter(), collections.Counter()
    for r in csv.DictReader(open(d / "observaciones.csv", encoding="utf-8")):
        meses = max(edad_al_corte(nac[r["id_nino"]], r["fecha_observacion"]), 0)
        t = tramo_por_meses(meses, _SoloTramos())
        tramo, sub = t if t else ("fuera_de_rango", "")
        n_e1 = int(r["nivel_estimado"])
        n_r = nivel_rubrica(tramo, n_e1)
        filas.append({"id_observacion": r["id_observacion"], "id_nino": r["id_nino"], "fecha": r["fecha_observacion"],
                      "edad_corte_meses": meses, "tramo": tramo, "subtramo": sub,
                      "nivel_e1": n_e1, "nivel_rubrica_tentativo": n_r if n_r else ""})
        cobertura[(tramo, sub)] += 1
        cruce[(tramo, n_e1, n_r)] += 1
    out = RAIZ / "bench" / "dataset_tramos.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0])); w.writeheader(); w.writerows(filas)
    xw = {"version": "tentativo-1", "nota": "validar con Integra; ver docstring de tools/unificar_dataset.py",
          "cobertura": [{"tramo": t, "subtramo": s, "observaciones": n} for (t, s), n in sorted(cobertura.items())],
          "cruce": [{"tramo": t, "nivel_e1": a, "nivel_rubrica": b, "observaciones": n} for (t, a, b), n in sorted(cruce.items())]}
    (RAIZ / "data" / "marcos").mkdir(parents=True, exist_ok=True)
    (RAIZ / "data" / "marcos" / "crosswalk_e1_integra.json").write_text(json.dumps(xw, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Cobertura del dataset por tramo de Integra:")
    for (t, s), n in sorted(cobertura.items()):
        print(f"  {t:12s} {s:16s} {n:5d}")
    for t in ("nivel_medio/medio_mayor", "transicion"):
        if not any(k[0] == t.split('/')[0] and (len(t.split('/')) == 1 or k[1] == t.split('/')[1]) for k in cobertura):
            print(f"  {t}: SIN DATOS en el dataset -> se evalúa solo con casos de la rúbrica")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
