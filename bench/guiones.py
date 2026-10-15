"""Genera los casos del benchmark IntegrAI-MM desde el dataset.

Elige N observaciones estratificadas por nivel (1–9) y, con Claude Haiku 4.5, escribe un
guion estilo tía chilena a partir de sus manifestaciones vinculadas. El guion es el ground
truth de la etapa 1 (WER/CER); los ids de manifestación y el nivel son el de la etapa final.

    python -m bench.guiones --n 30            # → bench/casos.jsonl
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

from src import config
from src.multimodal._bedrock import converse

AQUI = Path(__file__).parent
MODELO = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

PROMPT = """Eres una educadora de párvulos chilena enviando una nota rápida por WhatsApp sobre un niño o niña.
Escribe 2 a 3 frases naturales (como hablarías, con algún chilenismo suave) que cuenten que observaste
estas conductas, SIN copiarlas textualmente y sin mencionar niveles ni dominios. Usa el apodo "{apodo}".
Responde solo con la nota.

Conductas observadas:
{conductas}"""

APODOS = ["la Sofi", "el Benja", "la Martu", "el Agustín", "la Isi", "el Mati", "la Emi", "el Tomás", "la Flo", "el Vicho"]


def _csv(nombre: str) -> list[dict]:
    with open(config.datos_dir() / nombre, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20261015)
    ap.add_argument("--out", default=str(AQUI / "casos.jsonl"))
    a = ap.parse_args()
    rnd = random.Random(a.seed)

    man = {m["id_manifestacion"]: m for m in _csv("manifestaciones.csv")}
    links: dict[str, list[str]] = defaultdict(list)
    for l in _csv("observacion_manifestaciones.csv"):
        links[l["id_observacion"]].append(l["id_manifestacion"])
    por_nivel: dict[int, list[dict]] = defaultdict(list)
    for o in _csv("observaciones.csv"):
        if len(links[o["id_observacion"]]) >= 2:
            por_nivel[int(o["nivel_estimado"])].append(o)

    elegidas: list[dict] = []
    niveles = sorted(por_nivel)
    while len(elegidas) < a.n:
        for nv in niveles:
            if len(elegidas) < a.n:
                elegidas.append(por_nivel[nv].pop(rnd.randrange(len(por_nivel[nv]))))

    with open(a.out, "w", encoding="utf-8") as f:
        for i, o in enumerate(elegidas, 1):
            ids = links[o["id_observacion"]]
            apodo = APODOS[i % len(APODOS)]
            conductas = "\n".join(f"- {man[x]['texto_observable']}" for x in ids)
            guion = converse(MODELO, [{"text": PROMPT.format(apodo=apodo, conductas=conductas)}], max_tokens=300)["texto"]
            caso = {"caso": f"C{i:02d}", "id_observacion": o["id_observacion"], "id_nino": o["id_nino"],
                    "nivel": int(o["nivel_estimado"]), "ids_manifestacion": ids, "apodo": apodo, "guion": guion}
            f.write(json.dumps(caso, ensure_ascii=False) + "\n")
            print(caso["caso"], caso["nivel"], guion[:80])


if __name__ == "__main__":
    main()
