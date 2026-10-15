#!/usr/bin/env python3
"""Backfill: agrega EVIDENCIA (manifestaciones) a las observaciones que NO la tienen,
eligiéndola del catálogo según su (nivel, dominio). Idempotente (INSERT OR IGNORE).

Uso (EC2):
    /opt/integra/.venv/bin/python tools/backfill_manifestaciones.py [JARDIN]
"""
from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.getenv("INTEGRA_HOME", "/opt/integra"))
from src.plataforma import Plataforma  # noqa: E402
from catalogo_manifestaciones import elegir, indice  # noqa: E402

JARDIN = sys.argv[1] if len(sys.argv) > 1 else os.getenv("BACKFILL_JARDIN", "JAR-EQUIPO")


def main() -> None:
    p = Plataforma()
    c = p.con
    idx = indice()
    rnd = random.Random(20261015)
    obs = c.execute(
        "SELECT o.id_observacion, o.nivel_estimado, o.dominios FROM observaciones o "
        "JOIN ninos n ON n.id_nino = o.id_nino "
        "WHERE n.id_jardin = ? AND NOT EXISTS ("
        "  SELECT 1 FROM observacion_manifestaciones om WHERE om.id_observacion = o.id_observacion)",
        (JARDIN,)).fetchall()
    total = 0
    for r in obs:
        dom = (r["dominios"] or "").split(",")[0].strip() or None
        for mid in elegir(idx, r["nivel_estimado"], dom, k=2, rnd=rnd):
            c.execute("INSERT OR IGNORE INTO observacion_manifestaciones (id_observacion, id_manifestacion) "
                      "VALUES (?, ?)", (r["id_observacion"], mid))
            total += 1
    c.commit()
    print(f"✅ backfill {JARDIN}: {len(obs)} obs sin evidencia → {total} manifestaciones agregadas")


if __name__ == "__main__":
    main()
