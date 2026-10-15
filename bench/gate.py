"""Mide la compuerta de revisión por MARGEN (top1 − top2) del clasificador desplegado.

Recorre un set de casos (default: `casos_300.jsonl`, el benchmark interno de 300 notas
sintéticas), llama a `POST /clasificar` y barre el umbral de margen reportando, por umbral:

  · cobertura      → fracción que se **auto-registra** (margen ≥ umbral)
  · exactitud auto → acierto entre las auto-registradas
  · errores escap. → errores que pasan sin que los vea la tía
  · detecta_err    → fracción de TODOS los errores que la compuerta manda a revisión
  · exactitud esc. → acierto entre las escaladas (el trabajo que recibe la tía)

Cierra con el **muestreo de auditoría** de la cola auto-registrada: con la tasa de error
observada, cuántas muestras al azar hay que revisar para sostener una cota con 95 % de
confianza (regla de tres) o estimar la tasa con una precisión dada.

    python -m bench.gate                       # casos_300.jsonl (300)
    python -m bench.gate --casos casos.jsonl   # cualquier set con {guion, nivel, edad}
    python -m bench.gate --limite 20           # prueba rápida

No escribe en la plataforma: `/clasificar` no recibe niño ni teléfono.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from bench.eval_api import _clasificar

AQUI = Path(__file__).parent
CACHE = AQUI / ".cache" / "gate_respuestas.json"
UMBRALES = [0.0, 0.03, 0.05, 0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25, 0.30]


def _respuestas(url: str, casos: list[dict], limite: int | None) -> list[dict]:
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    recs = []
    for i, c in enumerate(casos[:limite] if limite else casos):
        texto, edad = c["guion"], c.get("edad")
        key = f"{c.get('id_observacion', i)}|{edad}"
        if key not in cache:
            d = _clasificar(url, texto, edad)
            cache[key] = {"nivel": d.get("nivel"), "margen": float(d.get("margen") or 0.0)}
        r = cache[key]
        recs.append({"ok": int(r["nivel"] == c["nivel"]), "margen": r["margen"],
                     "pred": r["nivel"], "gold": c["nivel"]})
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return recs


def _tabla(recs: list[dict]) -> tuple[str, dict]:
    n = len(recs)
    base = sum(x["ok"] for x in recs) / n
    errs = sum(1 - x["ok"] for x in recs)
    pm1 = sum(1 for x in recs if x["pred"] is not None and abs(x["pred"] - x["gold"]) <= 1) / n
    filas = ["| Umbral | Auto-registradas | Exact. auto | Errores escapados | Detecta errores | A revisión (tía) | Exact. final* |",
             "|---:|---:|---:|---:|---:|---:|---:|"]
    for t in UMBRALES:
        acc = [x for x in recs if x["margen"] >= t]
        esc = [x for x in recs if x["margen"] < t]
        if not acc:
            continue
        err_acc = sum(1 - x["ok"] for x in acc)
        detecta = 1 - (err_acc / errs if errs else 0.0)
        final = (n - err_acc) / n  # si la tía corrige el 100 % de la cola
        filas.append(f"| {t:.2f} | {len(acc)/n:.0%} | {sum(x['ok'] for x in acc)/len(acc):.1%} | "
                     f"{err_acc} | {detecta:.0%} | {len(esc)/n:.0%} | {final:.1%} |")
    return (f"casos={n} · exactitud exacta={base:.3f} ({sum(x['ok'] for x in recs)}/{n}) · "
            f"±1={pm1:.3f} · errores={errs}", {"filas": filas, "n": n, "base": base, "errs": errs})


def _auditoria(recs: list[dict], t: float) -> list[str]:
    n = len(recs)
    acc = [x for x in recs if x["margen"] >= t]
    err = sum(1 - x["ok"] for x in acc)
    p = err / len(acc) if acc else 0.0
    total_err = sum(1 - x["ok"] for x in recs)
    out = [f"Umbral operativo {t:.2f}: auto-registradas {len(acc)} ({len(acc)/n:.0%}), "
           f"errores {err} ({(err/total_err if total_err else 0):.0%} de todos), tasa de error {p:.2%}.",
           "",
           "Regla de tres (0 errores en n ⇒ cota superior 95 % = 3/n):",
           "| Cota buscada | n a auditar |", "|---:|---:|"]
    for cota in (0.10, 0.05, 0.03, 0.02):
        out.append(f"| ≤ {cota:.0%} | {math.ceil(3/cota)} |")
    out += ["", "Estimación con precisión ±e (n = 1,96²·p(1−p)/e²), con p observada:"]
    if 0 < p < 1:
        for e in (0.01, 0.02, 0.03):
            out.append(f"- ±{e:.0%} → n ≈ {math.ceil((1.96**2)*p*(1-p)/(e**2))}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://44.204.243.156:8000")
    ap.add_argument("--casos", default="casos_300.jsonl")
    ap.add_argument("--umbral", type=float, default=0.15)
    ap.add_argument("--limite", type=int, default=None)
    a = ap.parse_args()
    casos = [json.loads(l) for l in open(AQUI / a.casos, encoding="utf-8")]
    recs = _respuestas(a.url, casos, a.limite)
    resumen, meta = _tabla(recs)
    md = (f"# Compuerta de revisión por margen · `{a.casos}`\n\n{resumen}\n\n"
          + "\n".join(meta["filas"])
          + "\n\n\\* *Exactitud final* = si la tía corrige el 100 % de la cola «por verificar».\n\n"
          + "## Muestreo de auditoría\n\n" + "\n".join(_auditoria(recs, a.umbral)) + "\n")
    (AQUI / "reporte_gate.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
