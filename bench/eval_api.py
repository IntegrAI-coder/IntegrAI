"""Evalúa el clasificador DESPLEGADO (POST /clasificar de integra-server).

Variantes: "solo edad" (nivel más frecuente para la edad, sin leer la nota), ensemble con edad,
ensemble sin edad y, con --conductas, ensemble con edad sobre la nota normalizada por la etapa 2
de U2. /clasificar no recibe niño ni teléfono: no escribe en la plataforma.

Métricas: exacto, ±1, % a revisión, exactos entre aceptados y, si el caso trae `es_rezago`,
recall y precisión de la alerta de rezago (pred < nivel típico de la edad).

    python -m bench.eval_api                                   # bench/casos.jsonl
    python -m bench.eval_api --casos casos_contra_edad.jsonl --conductas
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


def _pct(a: int, b: int) -> str:
    return f"{a / b:.0%}" if b else "—"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://44.204.243.156:8000")
    ap.add_argument("--casos", default="casos.jsonl")
    ap.add_argument("--conductas", action="store_true", help="agrega la variante nota → conductas (etapa 2 de U2)")
    a = ap.parse_args()
    casos = [json.loads(l) for l in open(AQUI / a.casos, encoding="utf-8")]
    excluir = {c.get("id_observacion") for c in casos}
    nac = {r["id_nino"]: r["fecha_nacimiento"] for r in csv.DictReader(open(DATA / "ninos.csv", encoding="utf-8"))}
    obs = list(csv.DictReader(open(DATA / "observaciones.csv", encoding="utf-8")))
    fobs = {r["id_observacion"]: r["fecha_observacion"] for r in obs}
    por_edad: dict[int, collections.Counter] = collections.defaultdict(collections.Counter)
    for r in obs:
        if r["id_observacion"] not in excluir:
            por_edad[_edad(nac[r["id_nino"]], r["fecha_observacion"])][int(r["nivel_estimado"])] += 1
    tipico = {e: c.most_common(1)[0][0] for e, c in por_edad.items()}
    for c in casos:
        c.setdefault("edad", _edad(nac[c["id_nino"]], fobs[c["id_observacion"]]) if "id_nino" in c else None)
        c.setdefault("nivel_tipico_edad", tipico.get(c["edad"]))
        c.setdefault("tipo", "aleatorio")

    variantes = [("solo edad (sin texto)", "edad"), ("ensemble con edad", "con"), ("ensemble sin edad", "sin")]
    if a.conductas:
        from types import SimpleNamespace as N
        from src.multimodal import normalizar_entradas
        for c in casos:
            c["texto_conductas"] = normalizar_entradas([N(tipo="texto", ref="", pie=c["guion"], texto_extraido="")]).texto_para_matcher()
        variantes.append(("ensemble con edad + conductas U2", "cond"))

    preds: dict[str, list[tuple]] = {}
    for nombre, modo in variantes:
        filas = []
        for c in casos:
            if modo == "edad":
                pred, rev = c["nivel_tipico_edad"], False
            else:
                texto = c["texto_conductas"] if modo == "cond" else c["guion"]
                d = _clasificar(a.url, texto, None if modo == "sin" else c["edad"])
                pred, rev = d["nivel"], bool(d.get("requiere_revision"))
            filas.append((c, pred, rev))
        preds[nombre] = filas
        print(nombre, "listo")

    tipos = sorted({c["tipo"] for c in casos})
    lineas = ["| Variante | Exacto | ±1 | A revisión | Exactos en aceptados | "
              + " | ".join(f"Exacto `{t}`" for t in tipos) + " | Recall alerta rezago | Precisión alerta |",
              "|---" * (7 + len(tipos)) + "|"]
    for nombre, filas in preds.items():
        n = len(filas)
        ex = sum(p == c["nivel"] for c, p, _ in filas)
        pm = sum(p is not None and abs(p - c["nivel"]) <= 1 for c, p, _ in filas)
        rv = sum(r for *_, r in filas)
        acc = [(c, p) for c, p, r in filas if not r]
        por_tipo = []
        for t in tipos:
            ft = [(c, p) for c, p, _ in filas if c["tipo"] == t]
            por_tipo.append(_pct(sum(p == c["nivel"] for c, p in ft), len(ft)))
        con_rezago = [(c, p) for c, p, _ in filas if "es_rezago" in c]
        tp = sum(c["es_rezago"] and p is not None and p < c["nivel_tipico_edad"] for c, p in con_rezago)
        pos = sum(c["es_rezago"] for c, _ in con_rezago)
        alert = sum(p is not None and p < c["nivel_tipico_edad"] for c, p in con_rezago)
        lineas.append(f"| {nombre} | {_pct(ex, n)} | {_pct(pm, n)} | {_pct(rv, n)} | "
                      f"{sum(p == c['nivel'] for c, p in acc)}/{len(acc)} | " + " | ".join(por_tipo)
                      + f" | {_pct(tp, pos)} | {_pct(tp, alert)} |")
    cuenta = collections.Counter(c["tipo"] for c in casos)
    md = (f"# Clasificador desplegado · `{a.casos}` · {len(casos)} casos "
          f"({', '.join(f'{t}: {n}' for t, n in sorted(cuenta.items()))})\n\n"
          + "\n".join(lineas) + "\n\nAlerta de rezago = nivel predicho bajo el nivel típico de la edad.\n")
    out = AQUI / f"reporte_api_{Path(a.casos).stem}.md"
    out.write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
