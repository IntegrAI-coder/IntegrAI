#!/usr/bin/env python3
"""Prueba end-to-end la COLA "POR VERIFICAR" (human-in-the-loop) del equipo.

  · Muestra la cola de cada tía del equipo (EDU-EQ-1..4) consultando la API por su
    número de WhatsApp (`GET /pendientes?from=<número>`).
  · Con `--resolver`, resuelve un pendiente de esa tía (`POST /pendiente/resolver`)
    y verifica el resultado: aprobar/editar ESCRIBE en `evaluaciones`; rechazar, no.

Uso (en la EC2, con el venv):
    /opt/integra/.venv/bin/python tools/test_cola_htl.py
    /opt/integra/.venv/bin/python tools/test_cola_htl.py --resolver EDU-EQ-1 --accion aprobado
    /opt/integra/.venv/bin/python tools/test_cola_htl.py --resolver EDU-EQ-1 --accion editado --nivel 9
    /opt/integra/.venv/bin/python tools/test_cola_htl.py --resolver EDU-EQ-1 --accion rechazado
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import urllib.request

DB = os.getenv("DB_PATH", "/opt/integra/plataforma.db")


def _hdr() -> dict:
    tok = os.getenv("INTEGRA_API_TOKEN", "")
    return {"x-api-key": tok} if tok else {}


def _get(url: str, path: str) -> dict:
    req = urllib.request.Request(url + path, headers=_hdr())
    return json.load(urllib.request.urlopen(req, timeout=30))


def _post(url: str, path: str, body: dict) -> dict:
    req = urllib.request.Request(url + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **_hdr()}, method="POST")
    return json.load(urllib.request.urlopen(req, timeout=30))


def _tias_equipo() -> list[tuple[str, str]]:
    """(id_educadora, telefono) de EDU-EQ-* presentes en la base."""
    c = sqlite3.connect(DB)
    rows = c.execute("SELECT id_educadora, telefono_whatsapp FROM educadoras "
                     "WHERE id_educadora LIKE 'EDU-EQ-%' AND telefono_whatsapp IS NOT NULL "
                     "ORDER BY id_educadora").fetchall()
    return [(r[0], "".join(ch for ch in r[1] if ch.isdigit())) for r in rows]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--resolver", default=None, help="id_educadora a resolver (ej EDU-EQ-1)")
    ap.add_argument("--accion", default="aprobado", choices=["aprobado", "editado", "rechazado"])
    ap.add_argument("--nivel", type=int, default=None, help="nivel (requerido si accion=editado)")
    a = ap.parse_args()

    tias = _tias_equipo()
    print("=== Cola por verify de cada tía del equipo (GET /pendientes?from=) ===")
    colas: dict[str, dict] = {}
    for edu, num in tias:
        r = _get(a.url, f"/pendientes?from={num}")
        colas[edu] = r
        print(f"  {edu} (from={num}) -> educadora={r['educadora']}  n={r['n']}")
        for it in r["pendientes"][:3]:
            print(f"      {it['id_pendiente']}  nivel={it['nivel_propuesto']}  margen={it['margen']:.3f}")

    if not a.resolver:
        print("\n(sin --resolver: solo consulta. Añade --resolver EDU-EQ-1 para probar la resolución.)")
        return

    pends = colas.get(a.resolver, {}).get("pendientes", [])
    if not pends:
        print(f"\n⚠️ {a.resolver} no tiene pendientes para resolver.")
        return
    p = pends[0]
    c = sqlite3.connect(DB)
    antes = c.execute("SELECT count(*) FROM evaluaciones").fetchone()[0]
    body = {"id_pendiente": p["id_pendiente"], "accion": a.accion,
            "resuelto_por": a.resolver, "nivel": a.nivel}
    print(f"\n=== Resolviendo {p['id_pendiente']} como '{a.accion}' "
          f"{('nivel=' + str(a.nivel)) if a.nivel else ''} ===")
    print("  respuesta:", _post(a.url, "/pendiente/resolver", body))
    despues = sqlite3.connect(DB).execute("SELECT count(*) FROM evaluaciones").fetchone()[0]
    print(f"  evaluaciones: {antes} -> {despues} "
          f"({'✅ +1 (escrita)' if despues == antes + 1 else '— sin escritura (rechazado)'})")
    q2 = _get(a.url, f"/pendientes?from={dict(tias)[a.resolver]}")
    print(f"  cola de {a.resolver} después: n={q2['n']}")


if __name__ == "__main__":
    main()
