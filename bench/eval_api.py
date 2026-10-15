"""Evalúa el clasificador DESPLEGADO (POST /clasificar de integra-server) con los casos de bench/casos.jsonl.

Compara: ensemble con edad, ensemble sin edad, y la línea base "solo edad" (nivel más frecuente para
esa edad en el resto del dataset, sin mirar el texto). /clasificar no recibe niño ni teléfono:
no escribe en la plataforma.

    python -m bench.eval_api --url http://44.204.243.156:8000
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import urllib.parse
import urllib.request
from pathlib import Path

AQUI = Path(__file__).parent
DATA = AQUI.parent / "data"


def _edad(nac: str, obs: str) -> int:
    an, mn, dn = map(int, nac.split("-")); ao, mo, do = map(int, obs.split("-"))
    return 12 * (ao - an) + (mo - mn) - (do < dn)


def _clasificar(url: str, texto: str, edad: int | None) -> dict:
    q = {"texto": texto} | ({"edad_meses": edad} if edad is not None else {})
    req = urllib.request.Request(f"{url}/clasificar?{urllib.parse.urlencode(q)}", method="POST")
    return json.load(urllib.request.urlopen(req, timeout=90))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://44.204.243.156:8000")
    a = ap.parse_args()
    casos = [json.loads(l) for l in open(AQUI / "casos.jsonl", encoding="utf-8")]
    test = {c["id_observacion"] for c in casos}
    nac = {r["id_nino"]: r["fecha_nacimiento"] for r in csv.DictReader(open(DATA / "ninos.csv", encoding="utf-8"))}
    obs = list(csv.DictReader(open(DATA / "observaciones.csv", encoding="utf-8")))
    fobs = {r["id_observacion"]: r["fecha_observacion"] for r in obs}

    por_edad: dict[int, collections.Counter] = collections.defaultdict(collections.Counter)
    for r in obs:
        if r["id_observacion"] not in test:
            por_edad[_edad(nac[r["id_nino"]], r["fecha_observacion"])][int(r["nivel_estimado"])] += 1
    total = sum(sum(v.values()) for v in por_edad.values())
    techo_edad = sum(v.most_common(1)[0][1] for v in por_edad.values()) / total

    filas = []
    for nombre, usar_edad in (("solo edad (sin texto)", None), ("ensemble con edad", True), ("ensemble sin edad", False)):
        ex = pm1 = rev = ok_acept = n_acept = 0
        for c in casos:
            e = _edad(nac[c["id_nino"]], fobs[c["id_observacion"]])
            if usar_edad is None:
                pred, req_rev = por_edad[e].most_common(1)[0][0], False
            else:
                d = _clasificar(a.url, c["guion"], e if usar_edad else None)
                pred, req_rev = d["nivel"], d.get("requiere_revision", False)
            ex += pred == c["nivel"]; pm1 += pred is not None and abs(pred - c["nivel"]) <= 1; rev += req_rev
            if not req_rev:
                n_acept += 1; ok_acept += pred == c["nivel"]
        n = len(casos)
        filas.append(f"| {nombre} | {n} | {ex / n:.0%} | {pm1 / n:.0%} | {rev / n:.0%} | {ok_acept}/{n_acept} |")
        print(filas[-1])
    (AQUI / "reporte_api.md").write_text(
        f"# Clasificador desplegado ({a.url}) · {len(casos)} casos de bench/casos.jsonl\n\n"
        "| Variante | n | Nivel exacto | Nivel ±1 | A revisión | Exactos en aceptados |\n|---|---:|---:|---:|---:|---:|\n"
        + "\n".join(filas)
        + f"\n\nEn el dataset, el nivel más frecuente para cada edad acierta el {techo_edad:.1%} de las observaciones.\n",
        encoding="utf-8")


if __name__ == "__main__":
    main()
