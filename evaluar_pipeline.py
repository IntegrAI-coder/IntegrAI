#!/usr/bin/env python3
"""Evalúa el pipeline (matcher -> decisor) sobre el dataset E-1.

Genera NOTAS SINTÉTICAS realistas (lenguaje de la tía, con Bedrock) a partir de las
manifestaciones de cada observación, las pasa por el clasificador y mide exactitud
exacta y ±1 contra `nivel_estimado`.

    python3 evaluar_pipeline.py --n 300 --backend hibrido
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from src import config, marco
from src.clasificador import Clasificador


def build_cases(n: int, seed: int) -> list[dict]:
    D = config.datos_dir()
    man = {r["id_manifestacion"]: r for r in csv.DictReader(open(D / "manifestaciones.csv", encoding="utf-8"))}
    links = defaultdict(list)
    for r in csv.DictReader(open(D / "observacion_manifestaciones.csv", encoding="utf-8")):
        links[r["id_observacion"]].append(r["id_manifestacion"])
    ninos = {r["id_nino"]: r for r in csv.DictReader(open(D / "ninos.csv", encoding="utf-8"))}
    obs = list(csv.DictReader(open(D / "observaciones.csv", encoding="utf-8")))
    random.seed(seed); random.shuffle(obs)
    cases = []
    for o in obs[:n]:
        ms = [man[m]["texto_observable"] for m in links.get(o["id_observacion"], []) if m in man]
        if not ms:
            continue
        nin = ninos.get(o["id_nino"], {})
        edad = marco.edad_meses(nin["fecha_nacimiento"], o["fecha_observacion"]) if nin.get("fecha_nacimiento") else None
        cases.append({"id_obs": o["id_observacion"], "man": " ".join(ms), "nivel": int(o["nivel_estimado"]),
                      "edad": edad})
    return cases


def gen_note(case: dict, gateway) -> str:
    prompt = ("Eres una educadora de parvulos de Fundacion Integra. En 1 o 2 frases, con tus "
              "PROPIAS palabras y lenguaje natural y cercano, escribe una nota observando a un "
              "nino/a que muestra estas conductas: " + case["man"] + ". No copies literal.")
    try:
        return gateway.generar(prompt, tarea="simple").texto.strip()
    except Exception:
        return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--backend", default="hibrido")
    ap.add_argument("--seed", type=int, default=20261014)
    ap.add_argument("--cache", default="eval_notas.json")
    ap.add_argument("--gate", action="store_true", help="usa Laya como gate (escala si duda)")
    ap.add_argument("--gate_umbral", type=float, default=0.5)
    a = ap.parse_args()

    from src.bedrock import GatewayModelos
    gw = GatewayModelos()
    cases = build_cases(a.n, a.seed)
    print(f"casos: {len(cases)} | bedrock disponible: {gw.disponible}")

    cache: dict[str, str] = {}
    if os.path.exists(a.cache):
        cache = json.load(open(a.cache, encoding="utf-8"))
    todo = [c for c in cases if c["id_obs"] not in cache]
    if todo:
        print(f"generando {len(todo)} notas sinteticas...")
        with ThreadPoolExecutor(max_workers=8) as ex:
            for c, nota in zip(todo, ex.map(lambda x: gen_note(x, gw), todo)):
                cache[c["id_obs"]] = nota
        json.dump(cache, open(a.cache, "w", encoding="utf-8"), ensure_ascii=False)

    cl = Clasificador(backend=a.backend)
    verificador = None
    if a.gate:
        from src.backend_decision import DecisorLaya
        verificador = DecisorLaya()

    n = exact = pm = 0
    confs, por_nivel = [], defaultdict(lambda: [0, 0])
    # métricas del gate
    acc_ok = acc_esc = 0; n_ok = n_esc = 0
    for c in cases:
        nota = cache.get(c["id_obs"], "") or c["man"]
        r = cl.clasificar(nota, c["edad"])
        n += 1
        ok = (r.nivel == c["nivel"])
        exact += ok
        pm += (r.nivel is not None and abs(r.nivel - c["nivel"]) <= 1)
        confs.append(r.confianza)
        por_nivel[c["nivel"]][0] += 1
        por_nivel[c["nivel"]][1] += ok
        if verificador is not None and r.nivel is not None:
            p = verificador.verificar(nota, r.nivel)
            if p >= a.gate_umbral:
                n_ok += 1; acc_ok += ok
            else:
                n_esc += 1; acc_esc += ok

    print(f"\n=== RESULTADO (backend={a.backend}, {n} casos) ===")
    print(f"  exactitud EXACTA : {exact/n:.3f}")
    print(f"  exactitud +-1    : {pm/n:.3f}")
    print(f"  confianza media  : {sum(confs)/len(confs):.3f}")
    print("  por nivel (n, ok):", {k: f"{v[1]}/{v[0]}" for k, v in sorted(por_nivel.items())})
    if verificador is not None and (n_ok + n_esc) > 0:
        print(f"  GATE (umbral {a.gate_umbral}): acepta {n_ok} ({n_ok/(n_ok+n_esc):.0%}), escala {n_esc}")
        if n_ok: print(f"    exactitud en ACEPTADOS : {acc_ok/n_ok:.3f}")
        if n_esc: print(f"    exactitud en ESCALADOS : {acc_esc/n_esc:.3f} (ideal: baja)")


if __name__ == "__main__":
    main()
