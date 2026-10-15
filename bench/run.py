"""Runner del benchmark IntegrAI-MM: compara pipelines de ingesta midiendo el resultado final.

Pipelines:
  oraculo           guion tipeado (techo: lo mejor que puede hacer el matcher)
  oraculo+conductas guion → etapa 2 (¿la normalización conductual ayuda al matcher?)
  postit_legacy     Nova Pro "describe aprendizajes" (procesadores.py original)
  postit_v2         Claude literal + verificación Nova 2 Lite (+ etapa 2)
  audio_small       Whisper small (línea base original)
  audio_v2          Whisper large-v3-turbo + prompt de vocabulario (+ etapa 2)

Métricas: WER/CER de la etapa 1 vs. guion · Recall@5 del matcher sobre los ids verdaderos ·
exactitud de nivel exacta y ±1 (decisor configurado en BACKEND_DECISION) · latencia.

    python -m bench.run --medios sint --pipelines oraculo,postit_v2,audio_v2
    python -m bench.run --medios equipo --pipelines all
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from types import SimpleNamespace as N

from src.clasificador import Clasificador
from src.multimodal import normalizar_entradas
from src.multimodal.audio import transcribir
from src.multimodal.imagen import cer, leer_post_it
from src.multimodal.schema import normalizar

AQUI = Path(__file__).parent
TODOS = ["oraculo", "oraculo+conductas", "postit_legacy", "postit_v2", "audio_small", "audio_v2"]


def wer(ref: str, hip: str) -> float:
    r, h = normalizar(ref).split(), normalizar(hip).split()
    if not r:
        return 0.0
    prev = list(range(len(h) + 1))
    for i, a in enumerate(r, 1):
        cur = [i]
        for j, b in enumerate(h, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a != b)))
        prev = cur
    return prev[-1] / len(r)


def _medio(base: Path, tipo: str, caso: str) -> Path | None:
    for ext in ((".jpg", ".jpeg", ".png") if tipo == "postit" else (".ogg", ".opus", ".mp3", ".m4a", ".wav")):
        p = base / tipo / f"{caso}{ext}"
        if p.exists():
            return p
    return None


def correr(pipeline: str, caso: dict, base: Path) -> dict | None:
    """Devuelve {etapa1, texto_matcher} o None si falta el medio."""
    g = caso["guion"]
    if pipeline == "oraculo":
        return {"etapa1": g, "texto": g}
    if pipeline == "oraculo+conductas":
        o = normalizar_entradas([N(tipo="texto", ref="", pie=g, texto_extraido="")])
        return {"etapa1": g, "texto": o.texto_para_matcher()}
    tipo = "postit" if pipeline.startswith("postit") else "audio"
    p = _medio(base, tipo, caso["caso"])
    if not p:
        return None
    if pipeline == "postit_legacy":
        from src.procesadores import describir_imagen
        t = describir_imagen(str(p))
        return {"etapa1": t, "texto": t}
    if pipeline == "postit_v2":
        s = leer_post_it(str(p))
        o = normalizar_entradas([N(tipo="texto", ref="", pie=s.texto, texto_extraido="")])
        return {"etapa1": s.texto, "texto": o.texto_para_matcher()}
    if pipeline == "audio_small":
        s = transcribir(str(p), modelo="small", con_prompt=False)
        return {"etapa1": s.texto, "texto": s.texto}
    if pipeline == "audio_v2":
        s = transcribir(str(p))
        o = normalizar_entradas([N(tipo="texto", ref="", pie=s.texto, texto_extraido="")])
        return {"etapa1": s.texto, "texto": o.texto_para_matcher()}
    raise ValueError(pipeline)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--medios", default="sint", help="subcarpeta de bench/medios (sint | equipo)")
    ap.add_argument("--pipelines", default="oraculo,oraculo+conductas,postit_v2,audio_v2")
    ap.add_argument("--max", type=int, default=0)
    a = ap.parse_args()
    pipelines = TODOS if a.pipelines == "all" else a.pipelines.split(",")
    base = AQUI / "medios" / a.medios
    casos = [json.loads(l) for l in open(AQUI / "casos.jsonl", encoding="utf-8")]
    if a.max:
        casos = casos[:a.max]
    clf = Clasificador()
    filas, detalle = [], []
    for pl in pipelines:
        m = {"err1": [], "r5": [], "exacto": [], "pm1": [], "lat": []}
        for c in casos:
            t0 = time.perf_counter()
            try:
                r = correr(pl, c, base)
            except Exception as e:  # noqa: BLE001
                detalle.append({"pipeline": pl, "caso": c["caso"], "error": repr(e)}); continue
            if r is None:
                continue
            res = clf.clasificar(r["texto"])
            lat = time.perf_counter() - t0
            top5 = [x.manifestacion["id"] for x in res.matches[:5]]
            verdad = set(c["ids_manifestacion"])
            m["err1"].append(cer(c["guion"], r["etapa1"]) if pl.startswith("postit") else wer(c["guion"], r["etapa1"]))
            m["r5"].append(len(verdad & set(top5)) / len(verdad))
            m["exacto"].append(int(res.nivel == c["nivel"]))
            m["pm1"].append(int(res.nivel is not None and abs(res.nivel - c["nivel"]) <= 1))
            m["lat"].append(lat)
            detalle.append({"pipeline": pl, "caso": c["caso"], "nivel": c["nivel"], "pred": res.nivel,
                            "top5": top5, "etapa1": r["etapa1"], "texto": r["texto"]})
        n = len(m["r5"])
        if not n:
            filas.append(f"| {pl} | 0 | — | — | — | — | — |"); continue
        p = lambda xs: f"{100 * statistics.mean(xs):.0f} %"
        lat = sorted(m["lat"])
        filas.append(f"| {pl} | {n} | {p(m['err1'])} | {p(m['r5'])} | {p(m['exacto'])} | {p(m['pm1'])} | "
                     f"{statistics.median(lat):.1f} s / {lat[int(0.95 * (n - 1))]:.1f} s |")
        print(filas[-1])
    out = AQUI / f"reporte_{a.medios}.md"
    out.write_text(
        f"# IntegrAI-MM · medios `{a.medios}` · decisor `{clf.decisor.nombre}`\n\n"
        "| Pipeline | n | Error etapa 1 (WER audio / CER post-it) | Recall@5 manifestaciones | Nivel exacto | Nivel ±1 | Latencia p50 / p95 |\n"
        "|---|---:|---:|---:|---:|---:|---:|\n" + "\n".join(filas) + "\n", encoding="utf-8")
    (AQUI / f"detalle_{a.medios}.jsonl").write_text(
        "\n".join(json.dumps(d, ensure_ascii=False) for d in detalle), encoding="utf-8")
    print("reporte:", out)


if __name__ == "__main__":
    main()
