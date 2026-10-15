"""Set de evaluación "contra la edad": casos donde la edad NO basta para acertar el nivel.

En el dataset, el nivel más frecuente para la edad acierta el 98,5 % de las observaciones, así que
un set aleatorio premia mirar solo la edad. Este set mezcla:

  real_bajo   observaciones reales cuyo nivel_estimado ≠ nivel típico de su edad (en el dataset
              todas son exactamente 1 nivel bajo lo típico)
  rezago      sintético: niño/a de edad E con conductas de 2–3 niveles bajo lo típico
  adelanto    sintético: conductas de 1–2 niveles sobre lo típico
  control     sintético: conductas del nivel típico (para medir falsas alarmas)

Cada caso guarda edad, nivel típico de esa edad, nivel verdadero y si es rezago (nivel < típico).
La nota se genera con Haiku 4.5 desde 2–3 manifestaciones del nivel verdadero (dominios distintos).

    python -m bench.contra_edad                # → bench/casos_contra_edad.jsonl
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import random
from pathlib import Path

from bench.guiones import APODOS, MODELO, PROMPT
from src import config
from src.multimodal._bedrock import converse

AQUI = Path(__file__).parent


def _csv(nombre: str) -> list[dict]:
    with open(config.datos_dir() / nombre, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _edad(nac: str, obs: str) -> int:
    an, mn, dn = map(int, nac.split("-")); ao, mo, do = map(int, obs.split("-"))
    return 12 * (ao - an) + (mo - mn) - (do < dn)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", type=int, default=20)
    ap.add_argument("--rezago", type=int, default=20)
    ap.add_argument("--adelanto", type=int, default=10)
    ap.add_argument("--control", type=int, default=10)
    ap.add_argument("--seed", type=int, default=20261015)
    a = ap.parse_args()
    rnd = random.Random(a.seed)

    man = _csv("manifestaciones.csv")
    man_id = {m["id_manifestacion"]: m for m in man}
    man_nivel: dict[int, list[dict]] = collections.defaultdict(list)
    for m in man:
        man_nivel[int(m["nivel"])].append(m)
    nac = {r["id_nino"]: r["fecha_nacimiento"] for r in _csv("ninos.csv")}
    obs = _csv("observaciones.csv")
    links: dict[str, list[str]] = collections.defaultdict(list)
    for l in _csv("observacion_manifestaciones.csv"):
        links[l["id_observacion"]].append(l["id_manifestacion"])
    por_edad: dict[int, collections.Counter] = collections.defaultdict(collections.Counter)
    for r in obs:
        por_edad[_edad(nac[r["id_nino"]], r["fecha_observacion"])][int(r["nivel_estimado"])] += 1
    tipico = {e: c.most_common(1)[0][0] for e, c in por_edad.items()}
    edades = [e for e, c in por_edad.items() if sum(c.values()) >= 20]

    casos: list[dict] = []
    # 1) reales discordantes
    reales = [r for r in obs if int(r["nivel_estimado"]) != tipico[_edad(nac[r["id_nino"]], r["fecha_observacion"])]
              and len(links[r["id_observacion"]]) >= 2]
    for r in rnd.sample(reales, min(a.real, len(reales))):
        casos.append({"tipo": "real_bajo", "edad": _edad(nac[r["id_nino"]], r["fecha_observacion"]),
                      "nivel": int(r["nivel_estimado"]), "ids_manifestacion": links[r["id_observacion"]],
                      "id_observacion": r["id_observacion"]})

    # 2) sintéticos: edad real del dataset + nivel desplazado
    def sintetico(tipo: str, desplazamientos: tuple[int, ...]) -> dict:
        while True:
            e = rnd.choice(edades)
            nivel = tipico[e] + rnd.choice(desplazamientos)
            if 1 <= nivel <= 9:
                break
        elegidas = rnd.sample(man_nivel[nivel], 3)
        doms = {m["dominio"] for m in elegidas}
        if len(doms) < 2:
            elegidas = elegidas[:2]
        return {"tipo": tipo, "edad": e, "nivel": nivel, "ids_manifestacion": [m["id_manifestacion"] for m in elegidas]}

    casos += [sintetico("rezago", (-2, -3)) for _ in range(a.rezago)]
    casos += [sintetico("adelanto", (1, 2)) for _ in range(a.adelanto)]
    casos += [sintetico("control", (0,)) for _ in range(a.control)]

    with open(AQUI / "casos_contra_edad.jsonl", "w", encoding="utf-8") as f:
        for i, c in enumerate(casos, 1):
            apodo = APODOS[i % len(APODOS)]
            conductas = "\n".join(f"- {man_id[x]['texto_observable']}" for x in c["ids_manifestacion"])
            c["guion"] = converse(MODELO, [{"text": PROMPT.format(apodo=apodo, conductas=conductas)}], max_tokens=300)["texto"]
            c |= {"caso": f"E{i:02d}", "apodo": apodo, "nivel_tipico_edad": tipico[c["edad"]],
                  "es_rezago": c["nivel"] < tipico[c["edad"]]}
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
            print(c["caso"], c["tipo"], f"edad={c['edad']} típico={c['nivel_tipico_edad']} verdad={c['nivel']}")


if __name__ == "__main__":
    main()
