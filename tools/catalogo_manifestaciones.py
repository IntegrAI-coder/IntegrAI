"""Catálogo de manifestaciones (conductas observables) → índices por (nivel, dominio).

Se usa para que las observaciones sintéticas (y el backfill) queden con EVIDENCIA
(manifestaciones), igual que las de WhatsApp.
"""
from __future__ import annotations

import csv
import json
import os
import random
from pathlib import Path


def _ruta() -> Path:
    bases = [Path(os.getenv("INTEGRA_HOME", "/opt/integra")), Path("."),
             Path(__file__).resolve().parent.parent]
    for base in bases:
        for nombre in ("manifestaciones.json", "manifestaciones.csv"):
            p = base / "data" / nombre
            if p.exists():
                return p
    raise FileNotFoundError("no encontré data/manifestaciones.(json|csv)")


def _cargar() -> list[tuple[str, int, str]]:
    p = _ruta()
    if p.suffix == ".json":
        data = json.loads(p.read_text(encoding="utf-8"))
        return [(m.get("id") or m.get("id_manifestacion"), int(m["nivel"]), m["dominio"]) for m in data]
    with p.open(encoding="utf-8") as fh:
        return [(r["id_manifestacion"], int(r["nivel"]), r["dominio"]) for r in csv.DictReader(fh)]


def indice() -> dict[tuple[int, str], list[str]]:
    """{(nivel, dominio): [id_manifestacion, ...]}"""
    idx: dict[tuple[int, str], list[str]] = {}
    for idm, nivel, dominio in _cargar():
        idx.setdefault((nivel, dominio), []).append(idm)
    return idx


def elegir(idx: dict, nivel, dominio: str | None = None, k: int = 1,
           rnd: random.Random | None = None) -> list[str]:
    """Devuelve hasta `k` ids del catálogo para (nivel, dominio); si no hay del dominio,
    cae a cualquier manifestación de ese nivel."""
    r = rnd or random
    lvl = max(1, min(9, int(nivel or 1)))
    cands = list(idx.get((lvl, dominio)) or [])
    if not cands:
        cands = [mid for (n, _d), mids in idx.items() if n == lvl for mid in mids]
    if not cands:
        return []
    r.shuffle(cands)
    return cands[:max(1, k)]
