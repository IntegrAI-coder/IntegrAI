"""Set de evaluación de la rúbrica de Integra (los 3 tramos, incluidos los que no tienen datos).

- parafrasis: por cada conducta y ejemplo de la rúbrica, 2 notas estilo tía chilena con otras palabras.
  `ancla_origen` permite excluir esa ancla del matcher (leave-one-out).
- nuevo: por cada nivel y tramo, 1 escenario escrito SOLO desde la descripción, sin ver los ejemplos.
- edad: aleatoria dentro del subtramo (meses al corte), para que el sistema derive el tramo.

    python -m bench.rubrica_casos      → bench/casos_rubrica.jsonl (NO se versiona: deriva de material de Integra)
"""
from __future__ import annotations

import json
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from bench.guiones import APODOS, MODELO
from src.marcos import MarcoRubrica
from src.multimodal._bedrock import converse

AQUI = Path(__file__).parent

P_PARAFRASIS = """Eres una educadora de párvulos chilena enviando una nota rápida por WhatsApp sobre un niño o niña.
Cuenta esta misma situación con OTRAS palabras (no copies frases), en 1 a 3 frases naturales, usando el apodo "{apodo}".
Mantén el contexto (rutina, juego, conflicto…), el grado de apoyo del adulto y, si el niño dice algo, una frase parecida entre comillas.
No menciones niveles ni evaluaciones. Responde solo con la nota.

Situación: {texto}"""

P_NUEVO = """Eres una educadora de párvulos chilena enviando una nota rápida por WhatsApp sobre un niño o niña del tramo {tramo}.
Escribe una situación NUEVA y concreta que hayas observado en la sala y que muestre esto: {descripcion}
No uses ninguna de estas situaciones: {ejemplos}
1 a 3 frases naturales, usa el apodo "{apodo}", y si corresponde incluye lo que dice el niño entre comillas.
No menciones niveles ni evaluaciones. Responde solo con la nota."""


def _edad(rnd: random.Random, tramo: dict) -> int:
    sub = rnd.choice(tramo["subtramos"])
    return rnd.randrange(sub["edad_min_meses"], sub["edad_max_meses"])


def main() -> None:
    rnd = random.Random(20261015)
    m = MarcoRubrica()
    trabajos = []
    for t in m.tramos():
        for l in t["niveles"]:
            base = f"IYA-{t['sigla']}-N{l['nivel']:02d}"
            semillas = [(f"{base}-C{i}", c) for i, c in enumerate(l["conductas"], 1)] + \
                       [(f"{base}-E{i}", e) for i, e in enumerate(l["ejemplos"], 1)]
            for ancla, texto in semillas:
                for k in range(2):
                    trabajos.append({"tipo": "parafrasis", "tramo": t["id"], "nivel": l["nivel"], "ancla_origen": ancla,
                                     "edad_meses": _edad(rnd, t), "apodo": rnd.choice(APODOS),
                                     "prompt": P_PARAFRASIS.format(apodo="{apodo}", texto=texto)})
            trabajos.append({"tipo": "nuevo", "tramo": t["id"], "nivel": l["nivel"], "ancla_origen": None,
                             "edad_meses": _edad(rnd, t), "apodo": rnd.choice(APODOS),
                             "prompt": P_NUEVO.format(tramo=t["nombre"], descripcion=l["descripcion"], apodo="{apodo}",
                                                      ejemplos=" | ".join(l["ejemplos"]))})

    def generar(w: dict) -> dict:
        w = dict(w)
        w["nota"] = converse(MODELO, [{"text": w.pop("prompt").replace("{apodo}", w["apodo"])}], max_tokens=300)["texto"]
        return w

    with ThreadPoolExecutor(8) as ex:
        casos = list(ex.map(generar, trabajos))
    with open(AQUI / "casos_rubrica.jsonl", "w", encoding="utf-8") as f:
        for i, c in enumerate(casos, 1):
            f.write(json.dumps({"caso": f"R{i:03d}", **c}, ensure_ascii=False) + "\n")
    print(f"{len(casos)} casos -> bench/casos_rubrica.jsonl")


if __name__ == "__main__":
    main()
