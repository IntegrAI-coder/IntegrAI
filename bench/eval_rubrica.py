"""Evalúa la clasificación con la rúbrica de Integra sobre bench/casos_rubrica.jsonl.

Variantes:
  solo_edad  nivel = posición de la edad dentro del tramo (sin leer la nota): mide cuánto "regala" la edad
  crudo      la nota tal cual → ClasificadorRubrica
  mm_v1      nota → conductas U2 (reglas originales) → ClasificadorRubrica
  mm_v2      nota → conductas U2 guiadas por la rúbrica (dicho del niño, apoyo, contexto) → ClasificadorRubrica
  juez       nota cruda → JuezRubrica (Claude lee la rúbrica del tramo; salida Pydantic)

En las paráfrasis se excluye del matcher el ancla de la que salió el caso (leave-one-out).

    python -m bench.eval_rubrica --variantes solo_edad,crudo,mm_v1,mm_v2
"""
from __future__ import annotations

import argparse
import collections
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace as N

from src.clasificador_rubrica import ClasificadorRubrica, JuezRubrica
from src.marcos import MarcoRubrica

AQUI = Path(__file__).parent
CACHE = AQUI / ".cache"


def _conductas(casos: list[dict], version: str) -> dict[str, str]:
    """Texto para el matcher según la versión del MM; cacheado por caso."""
    ruta = CACHE / f"conductas_rubrica_{version}.json"
    cache = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    from src.multimodal import normalizar_entradas
    guia = None
    if version == "mm_v2":
        from src.marcos import marco_activo
        guia = marco_activo()

    def uno(c: dict) -> tuple[str, str]:
        o = normalizar_entradas([N(tipo="texto", ref="", pie=c["nota"], texto_extraido="")], guia=guia)
        return c["caso"], o.texto_para_matcher()

    faltan = [c for c in casos if c["caso"] not in cache]
    with ThreadPoolExecutor(6) as ex:
        for k, v in ex.map(uno, faltan):
            cache[k] = v
    CACHE.mkdir(exist_ok=True)
    ruta.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return cache


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variantes", default="solo_edad,crudo,mm_v1")
    a = ap.parse_args()
    variantes = a.variantes.split(",")
    casos = [json.loads(l) for l in open(AQUI / "casos_rubrica.jsonl", encoding="utf-8")]
    m = MarcoRubrica()
    clf = ClasificadorRubrica(marco=m)
    juez = JuezRubrica(marco=m)
    textos = {"crudo": {c["caso"]: c["nota"] for c in casos}}
    for v in variantes:
        if v.startswith("mm_"):
            textos[v] = _conductas(casos, v)

    juez_res = {}
    if "juez" in variantes:
        textos["juez"] = textos["crudo"]
        ruta = CACHE / "juez_rubrica.json"
        juez_res = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
        def uno(c):
            excl = {c["ancla_origen"]} if c.get("ancla_origen") else None
            return c["caso"], juez.clasificar(c["nota"], edad_meses=c["edad_meses"], excluir=excl)
        with ThreadPoolExecutor(6) as ex:
            for k, r in ex.map(uno, [c for c in casos if c["caso"] not in juez_res]):
                juez_res[k] = r
        CACHE.mkdir(exist_ok=True); ruta.write_text(json.dumps(juez_res, ensure_ascii=False), encoding="utf-8")
    filas, confusion, detalle = [], {}, []
    for v in variantes:
        res = collections.defaultdict(lambda: [0, 0, 0])   # (grupo) -> [n, exacto, ±1]
        conf = collections.Counter()
        for c in casos:
            if v == "solo_edad":
                t = m.tramo(c["tramo"])
                pos = (c["edad_meses"] - t["edad_min_meses"]) / (t["edad_max_meses"] - t["edad_min_meses"])
                pred, rev = min(8, 1 + int(pos * 8)), False
            else:
                excl = {c["ancla_origen"]} if c.get("ancla_origen") else None
                if v == "juez":
                    r = juez_res[c["caso"]]
                else:
                    r = clf.clasificar(textos[v][c["caso"]], edad_meses=c["edad_meses"], excluir=excl)
                pred, rev = r["nivel"], r["requiere_revision"]
                detalle.append({"variante": v, "caso": c["caso"], "tramo": c["tramo"], "nivel": c["nivel"],
                                "pred": pred, "margen": r.get("margen"), "texto": textos[v][c["caso"]]})
            for g in ("total", c["tramo"], c["tipo"]):
                res[g][0] += 1; res[g][1] += pred == c["nivel"]; res[g][2] += pred is not None and abs(pred - c["nivel"]) <= 1
            if v != "solo_edad":
                res["_rev"][0] += 1; res["_rev"][1] += rev
                if not rev:
                    res["_acept"][0] += 1; res["_acept"][1] += pred == c["nivel"]
            conf[(c["tramo"], c["nivel"], pred)] += 1
        pct = lambda g, i: f"{100 * res[g][i] / res[g][0]:.0f} %" if res[g][0] else "—"
        filas.append(f"| {v} | {pct('total', 1)} | {pct('total', 2)} | {pct('sala_cuna', 1)} | {pct('nivel_medio', 1)} | "
                     f"{pct('transicion', 1)} | {pct('parafrasis', 1)} | {pct('nuevo', 1)} | "
                     f"{pct('_rev', 1) if v != 'solo_edad' else '—'} | "
                     f"{(str(res['_acept'][1]) + '/' + str(res['_acept'][0])) if v != 'solo_edad' else '—'} |")
        confusion[v] = conf
        print(filas[-1])

    md = [f"# Rúbrica Integra · Identidad y Autonomía · {len(casos)} casos "
          f"({sum(c['tipo'] == 'parafrasis' for c in casos)} paráfrasis leave-one-out, {sum(c['tipo'] == 'nuevo' for c in casos)} escenarios nuevos)\n",
          "| Variante | Exacto | ±1 | Exacto Sala Cuna | Exacto Nivel Medio | Exacto Transición | Exacto paráfrasis | Exacto nuevos | A revisión | Correctos en aceptados |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"] + filas
    mejor = [v for v in variantes if v != "solo_edad"][-1]
    for tramo in ("sala_cuna", "nivel_medio", "transicion"):
        md += [f"\n**Confusión `{mejor}` · {tramo}** (fila = nivel real, columna = predicho)\n",
               "| real \\ pred | " + " | ".join(str(i) for i in range(1, 9)) + " |", "|---" * 9 + "|"]
        for real in range(1, 9):
            md.append(f"| {real} | " + " | ".join(str(confusion[mejor][(tramo, real, p)] or "·") for p in range(1, 9)) + " |")
    (AQUI / "reporte_rubrica.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (AQUI / "detalle_rubrica.jsonl").write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in detalle), encoding="utf-8")
    print("reporte: bench/reporte_rubrica.md")


if __name__ == "__main__":
    main()
