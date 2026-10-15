#!/usr/bin/env python3
"""Analiza el GATE: qué señal separa mejor los ACIERTOS de los ERRORES.

Prueba varias señales (confianza del ensemble, margen top1-top2, verificación de Laya
y una combinada) y barre umbrales reportando cobertura vs exactitud en los aceptados.

    python3 evaluar_gate.py 300
"""
from __future__ import annotations

import json
import sys

from src.clasificador import Clasificador
from src.backend_decision import DecisorLaya
from evaluar_pipeline import build_cases


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    cache = json.load(open("eval_notas.json", encoding="utf-8"))
    cases = build_cases(n, 20261014)
    cl = Clasificador(backend="ensemble")
    ver = DecisorLaya()

    recs = []
    for c in cases:
        nota = cache.get(c["id_obs"], "") or c["man"]
        r = cl.clasificar(nota, c["edad"])
        vals = sorted(r.probabilidades.values(), reverse=True)
        margin = (vals[0] - vals[1]) if len(vals) > 1 else 0.0
        verp = ver.verificar(nota, r.nivel) if r.nivel else 0.0
        recs.append({"ok": int(r.nivel == c["nivel"]), "conf": float(r.confianza),
                     "margin": float(margin), "ver": float(verp)})

    N = len(recs)
    base = sum(x["ok"] for x in recs) / N
    print(f"casos={N} | exactitud global={base:.3f} | errores={sum(1-x['ok'] for x in recs)}")
    print(f"{'señal':>10} {'umbral':>7} {'cobertura':>10} {'exact_acept':>12} {'errores_esc':>12}")

    def sweep(key, ths):
        for t in ths:
            sel = [x for x in recs if x[key] >= t]
            esc = [x for x in recs if x[key] < t]
            if not sel:
                continue
            cov = len(sel) / N
            acc = sum(x["ok"] for x in sel) / len(sel)
            err_esc = (sum(1 - x["ok"] for x in esc) / len(esc)) if esc else 0.0
            print(f"{key:>10} {t:>7.2f} {cov:>10.2f} {acc:>12.3f} {err_esc:>12.3f}")

    sweep("conf", [0, 0.3, 0.35, 0.4, 0.45, 0.5, 0.6, 0.7])
    sweep("margin", [0, 0.05, 0.08, 0.1, 0.15, 0.2, 0.3])
    sweep("ver", [0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
    for x in recs:
        x["comb"] = 0.5 * x["ver"] + 0.5 * x["conf"]
    sweep("comb", [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
    json.dump(recs, open("gate_recs.json", "w"))
    print("\n(guardado gate_recs.json)")


if __name__ == "__main__":
    main()
