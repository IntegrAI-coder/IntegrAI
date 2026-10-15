"""Evaluación periódica (el CRON) — IntegrAI · Desafío E-1.

Corre una vez al día (configurable) y, a partir de las observaciones ACUMULADAS
en la base, produce evaluaciones consolidadas por niño/a y detecta
**avance / retroceso / estancamiento**.

Diseño:
  · Watermark por `rowid`: solo procesa observaciones NUEVAS (idempotente y barato).
  · Solo usa observaciones con estado 'auto' o 'verificado' (nunca las 'por_verificar').
  · Consolida el nivel del período (media ponderada por confianza) y su MARGEN.
  · Gate: si el margen < GATE_MARGEN -> va a `evaluaciones_pendientes` (ojo de la tía).
          si el margen es alto       -> entra directo a `evaluaciones` (canónica).
  · Compara con la última evaluación del niño -> tendencia. Retroceso => alerta.

Uso:
    python -m src.evaluacion_periodica           # corre el cron
    python -m src.evaluacion_periodica --dry-run # no escribe, solo reporta
"""
from __future__ import annotations

import argparse
from datetime import datetime
from typing import Any

from . import config
from .plataforma import Plataforma

WATERMARK_KEY = "cron_watermark_rowid"


def _consolidar(obs: list[dict]) -> tuple[int | None, float, dict[int, float]]:
    """Nivel consolidado del período (media ponderada por confianza) + margen top1-top2."""
    pesos: dict[int, float] = {}
    for o in obs:
        l = o.get("nivel") if o.get("nivel") is not None else o.get("nivel_estimado")
        if not l:
            continue
        pesos[l] = pesos.get(l, 0.0) + max(float(o.get("confianza") or 0.5), 0.01)
    if not pesos:
        return None, 0.0, {}
    total = sum(pesos.values())
    dist = {l: round(v / total, 4) for l, v in pesos.items()}
    orden = sorted(dist.values(), reverse=True)
    margen = (orden[0] - orden[1]) if len(orden) > 1 else 1.0
    nivel = max(dist, key=lambda l: dist[l])
    return nivel, round(margen, 4), dist


def _tendencia(nuevo: int, previo: int | None) -> str:
    if previo is None:
        return "sin_historial"
    d = nuevo - previo
    if d >= 1:
        return "avance"
    if d <= -1:
        return "retroceso"
    return "estable"


def ejecutar(plataforma: Plataforma | None = None, dry_run: bool = False,
             ahora: str | None = None) -> dict[str, Any]:
    p = plataforma or Plataforma()
    ahora = ahora or datetime.now().isoformat(timespec="seconds")
    fecha = ahora[:10]

    wm = int(p.get_meta(WATERMARK_KEY, "0") or 0)
    nuevas = p.observaciones_nuevas(desde_rowid=wm)
    if not nuevas:
        return {"ok": True, "observaciones_nuevas": 0, "ninos": 0,
                "evaluaciones": 0, "pendientes": 0, "alertas": 0, "watermark": wm}

    # agrupar por niño
    por_nino: dict[str, list[dict]] = {}
    max_rid = wm
    for o in nuevas:
        por_nino.setdefault(o["id_nino"], []).append(o)
        max_rid = max(max_rid, int(o["_rid"]))

    n_eval = n_pend = n_alertas = 0
    detalle: list[dict] = []

    for id_nino, obs in por_nino.items():
        nivel, margen, dist = _consolidar(obs)
        if nivel is None:
            continue
        tray = p.trayectoria(id_nino) or {}
        prev = p.ultima_evaluacion(id_nino, "global")
        tend = _tendencia(nivel, prev["nivel"] if prev else None)
        alerta = None
        if tend == "retroceso":
            alerta = f"Retroceso: {prev['nivel']} -> {nivel} (período {fecha})."
        elif tray.get("alertas"):
            alerta = "; ".join(tray["alertas"])

        umbral = getattr(config, "GATE_MARGEN", 0.15)
        doms = sorted({d for o in obs for d in (o.get("dominios") or "").split(",") if d})
        evidencia = f"{len(obs)} obs nuevas · dominios: {', '.join(doms) or '—'} · dist={dist}"

        # ¿A QUÉ TÍA se asigna la cola? La de la sala del niño; si no, quien registró.
        nin = p.nino(id_nino) or {}
        tia = p.educadora_de_sala(nin.get("id_jardin"), nin.get("sala_grupo")) or obs[-1].get("id_educadora")

        if margen < umbral:
            n_pend += 1
            if not dry_run:
                p.encolar_pendiente(id_nino, [str(l) for l in dist], nivel, "global",
                                    confianza=dist.get(nivel, 0.0), margen=margen,
                                    motivo="margen_bajo", evidencia=evidencia, creado_en=ahora,
                                    id_educadora=tia)
            detalle.append({"id_nino": id_nino, "accion": "pendiente", "nivel": nivel,
                            "margen": margen, "tendencia": tend, "tia": tia})
        else:
            n_eval += 1
            if not dry_run:
                p.guardar_evaluacion(id_nino, "global", nivel, dist.get(nivel, 0.0),
                                     margen, periodo=fecha, tendencia=tend, alerta=alerta,
                                     generado_en=ahora)
            detalle.append({"id_nino": id_nino, "accion": "evaluacion", "nivel": nivel,
                            "margen": margen, "tendencia": tend, "alerta": alerta})
        if alerta:
            n_alertas += 1

    if not dry_run:
        p.set_meta(WATERMARK_KEY, str(max_rid))

    return {"ok": True, "observaciones_nuevas": len(nuevas), "ninos": len(por_nino),
            "evaluaciones": n_eval, "pendientes": n_pend, "alertas": n_alertas,
            "watermark": max_rid, "detalle": detalle}


def main() -> None:  # pragma: no cover
    ap = argparse.ArgumentParser(description="Evaluación periódica IntegrAI (cron)")
    ap.add_argument("--dry-run", action="store_true", help="no escribe, solo reporta")
    args = ap.parse_args()
    r = ejecutar(dry_run=args.dry_run)
    modo = "(dry-run) " if args.dry_run else ""
    print(f"🧠 Cron {modo}-> nuevas: {r['observaciones_nuevas']} · niños: {r['ninos']} · "
          f"evaluaciones: {r['evaluaciones']} · por_verificar: {r['pendientes']} · "
          f"alertas: {r['alertas']} · watermark: {r['watermark']}")
    for d in r.get("detalle", []):
        print("  ", d)


if __name__ == "__main__":  # pragma: no cover
    main()
