#!/usr/bin/env python3
"""Evalúa Laya (base y checkpoints afinados) en un **held-out LIMPIO**.

Motivación
----------
El reporte de `laya-train` advierte que el set de evaluación (`data/eval.jsonl`)
**se solapa con el de entrenamiento** (308 de 443 items): las métricas que reporta
NO son un held-out independiente. Este script:

  1. Detecta el solapamiento comparando el texto `state` de eval contra train.
  2. Construye el subconjunto **limpio** (items cuyo input no aparece en train).
  3. Evalúa cada modelo sobre ese subconjunto (exacto y ±1).

Uso (en la EC2, con el venv de Integra):
    /opt/integra/.venv/bin/python evaluar_laya_heldout.py
"""
from __future__ import annotations

import json
import statistics

import laya

EVAL = "/opt/integra/data/eval.jsonl"
TRAIN = "/opt/integra/data/train.jsonl"
OUT_CLEAN = "/opt/integra/data/eval_clean.jsonl"

MODELOS = [
    ("base(laya)", "/opt/integra/models/laya"),
    ("laya-integra2", "/opt/integra/models/laya-integra2"),
    ("laya-integra3", "/opt/integra/models/laya-integra3"),
]


def manifests(state: str) -> set[str]:
    """Extrae el conjunto de manifestaciones (oraciones) del `state`. Ojo: heurística."""
    s = state.replace("Conductas observadas: ", "").split(" Nota de la educadora:")[0]
    return {x.strip() for x in s.split(".") if x.strip()}


def main() -> None:
    ev = [json.loads(l) for l in open(EVAL)]
    tr = [json.loads(l) for l in open(TRAIN)]
    tr_states = {t["state"] for t in tr}
    clean = [e for e in ev if e["state"] not in tr_states]

    print(f"total eval: {len(ev)} | overlap exacto: {len(ev) - len(clean)} | CLEAN: {len(clean)}", flush=True)
    json.dump(clean, open(OUT_CLEAN, "w"), ensure_ascii=False)

    # Diagnóstico de fuga por manifestaciones (paraphrase leakage)
    tr_man: set[str] = set()
    for t in tr:
        tr_man |= manifests(t["state"])
    share = [len(manifests(e["state"]) & tr_man) / max(1, len(manifests(e["state"]))) for e in clean]
    print(f"manifest overlap medio clean/train: {statistics.mean(share):.3f} "
          f"(min {min(share):.2f} max {max(share):.2f}) | 100% nuevas: "
          f"{sum(1 for e in clean if not (manifests(e['state']) & tr_man))}", flush=True)

    for name, path in MODELOS:
        model = laya.load(path, device="cpu")
        ok = pm = 0
        for e in clean:
            r = model.predict(e["state"], e["questions"])
            pred = str(r["answers"]["nivel"].get("choice"))
            gold = str(e["expected"]["nivel"])
            if pred == gold:
                ok += 1
            try:
                if abs(int(pred) - int(gold)) <= 1:
                    pm += 1
            except ValueError:
                pass
        n = len(clean)
        print(f"{name}: exact={ok}/{n}={ok/n:.4f}  +-1={pm}/{n}={pm/n:.4f}", flush=True)


if __name__ == "__main__":
    main()
