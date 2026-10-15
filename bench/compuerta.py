"""Calibra la compuerta de revisión sobre respuestas reales del clasificador desplegado.

1. Llama a POST /clasificar con y sin edad, sobre la nota original y sobre las conductas U2,
   para los dos sets (aleatorio y contra la edad). Cachea en bench/.cache/api_respuestas.json.
2. Evalúa reglas de compuerta offline y reporta, por set: % a revisión, exactitud en aceptados y
   "rezagos que se escapan" (rezago verdadero, aceptado sin alerta).

    python -m bench.compuerta
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace as N

from bench.eval_api import _clasificar
from src.compuerta import Compuerta

AQUI = Path(__file__).parent
CACHE = AQUI / ".cache" / "api_respuestas.json"
URL = os.getenv("INTEGRAI_API_URL", "")


def _cargar_casos() -> list[dict]:
    import csv
    nac = {r["id_nino"]: r["fecha_nacimiento"] for r in csv.DictReader(open(AQUI.parent / "data" / "ninos.csv", encoding="utf-8"))}
    fobs = {r["id_observacion"]: r["fecha_observacion"] for r in csv.DictReader(open(AQUI.parent / "data" / "observaciones.csv", encoding="utf-8"))}
    from bench.eval_api import _edad
    casos = []
    for archivo, set_ in (("casos.jsonl", "aleatorio"), ("casos_contra_edad.jsonl", "contra_edad")):
        for l in open(AQUI / archivo, encoding="utf-8"):
            c = json.loads(l) | {"set": set_}
            if "edad" not in c:
                c["edad"] = _edad(nac[c["id_nino"]], fobs[c["id_observacion"]])
            casos.append(c)
    return casos


def _respuestas(casos: list[dict]) -> dict:
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    from src.multimodal import normalizar_entradas
    for c in casos:
        k = c["caso"]
        r = cache.setdefault(k, {})
        if "conductas" not in r:
            r["conductas"] = normalizar_entradas([N(tipo="texto", ref="", pie=c["guion"], texto_extraido="")]).texto_para_matcher()
        for texto_k, texto in (("guion", c["guion"]), ("cond", r["conductas"])):
            for edad_k, edad in (("con", c["edad"]), ("sin", None)):
                key = f"{texto_k}_{edad_k}"
                if key not in r:
                    d = _clasificar(URL, texto, edad)
                    r[key] = {"nivel": d["nivel"], "margen": d.get("margen", 0.0), "rev": d.get("requiere_revision")}
        CACHE.parent.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return cache


def main() -> None:
    import collections, csv
    if not URL and not CACHE.exists():
        raise SystemExit("define la variable INTEGRAI_API_URL")
    casos = _cargar_casos()
    resp = _respuestas(casos)
    # nivel típico por edad (todo el dataset)
    from bench.eval_api import _edad
    nac = {r["id_nino"]: r["fecha_nacimiento"] for r in csv.DictReader(open(AQUI.parent / "data" / "ninos.csv", encoding="utf-8"))}
    pe = collections.defaultdict(collections.Counter)
    for r in csv.DictReader(open(AQUI.parent / "data" / "observaciones.csv", encoding="utf-8")):
        pe[_edad(nac[r["id_nino"]], r["fecha_observacion"])][int(r["nivel_estimado"])] += 1
    tipico = {e: c.most_common(1)[0][0] for e, c in pe.items()}

    configs = [("actual: margen<0.15 · nota original", "guion", Compuerta(0.15, None)),
               ("actual: margen<0.15 · conductas U2", "cond", Compuerta(0.15, None))]
    for ud in (1, 2, 3):
        configs.append((f"propuesta: margen<0.15 o discrepancia≥{ud} · conductas U2", "cond", Compuerta(0.15, ud)))
    lineas = ["| Compuerta | Set | A revisión | Exactos en aceptados | Rezagos que se escapan |", "|---|---|---:|---:|---:|"]
    for nombre, tk, comp in configs:
        for set_ in ("aleatorio", "contra_edad"):
            cs = [c for c in casos if c["set"] == set_]
            rev = ok = acept = escapan = rezagos = 0
            for c in cs:
                r = resp[c["caso"]]
                con, sin = r[f"{tk}_con"], r[f"{tk}_sin"]
                t = c.get("nivel_tipico_edad") or tipico[c["edad"]]
                revisar, _ = comp.revisar(con["margen"], sin["nivel"], t)
                es_rezago = c["nivel"] < t
                rezagos += es_rezago
                if revisar:
                    rev += 1
                else:
                    acept += 1; ok += con["nivel"] == c["nivel"]
                    escapan += es_rezago and not (con["nivel"] is not None and con["nivel"] < t)
            lineas.append(f"| {nombre} | {set_} ({len(cs)}) | {rev / len(cs):.0%} | {ok}/{acept} ({ok / max(acept, 1):.0%}) | {escapan}/{rezagos} |")
    md = "# Calibración de la compuerta de revisión\n\n" + "\n".join(lineas) + (
        "\n\n*Rezago que se escapa* = el niño/a está bajo lo típico para su edad, el sistema lo acepta sin revisión "
        "y además no lo marca bajo lo típico (la tía nunca se entera).\n")
    (AQUI / "reporte_compuerta.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
