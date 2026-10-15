#!/usr/bin/env python3
"""Puebla la COLA "POR VERIFICAR" de los 4 cursos del equipo (JAR-EQUIPO).

Para cada curso (Sala Girasol/Mariposa/Estrella/Cometa) siembra observaciones de
**nivel variado** sobre algunos niños/as, de modo que la consolidación del cron
quede con **margen bajo** y entre a `evaluaciones_pendientes`, asignada a la
**tía de la sala** (`educadora_de_sala`). Así cada miembro del equipo ve su propia
cola al consultar `GET /pendientes?from=<su número>`.

Idempotente: borra las observaciones de origen `demo_cola` y los pendientes de
JAR-EQUIPO antes de re-sembrar. Retrocede el watermark del cron al mínimo de lo
sembrado — necesario porque SQLite REUTILIZA rowids al borrar+insertar, y si no,
el cron creería que las observaciones nuevas "ya se procesaron". NO corre el cron.

Uso (en la EC2, con el venv):
    /opt/integra/.venv/bin/python tools/seed_cola_equipo.py
    /opt/integra/.venv/bin/python -m src.evaluacion_periodica   # genera los pendientes
"""
from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.getenv("INTEGRA_HOME", "/opt/integra"))
from src.plataforma import Plataforma  # noqa: E402
from catalogo_manifestaciones import elegir, indice  # noqa: E402

MANIF = indice()
_RND = random.Random(20261015)

JARDIN = "JAR-EQUIPO"
FECHA = "2026-10-15"
ORIGEN = "demo_cola"
POR_CURSO = 6     # niños sembrados por curso

CURSOS = [
    ("Sala Girasol",  "EDU-EQ-1"),
    ("Sala Mariposa", "EDU-EQ-2"),
    ("Sala Estrella", "EDU-EQ-3"),
    ("Sala Cometa",   "EDU-EQ-4"),
]


def _niveles(i: int) -> tuple[int, int]:
    """Nivel base por niño sembrado (i=1..POR_CURSO) → reparte 2..7; la 2ª obs va a base+1."""
    base = 2 + (i - 1) * 6 // POR_CURSO
    return base, base + 1


def _nota(nombre: str, nivel: int) -> str:
    frases = {
        2: "Responde con la mirada cuando se le habla y se calma con la voz de la tía.",
        3: "Toma objetos cercanos y los lleva a la boca; sostiene la cabeza estable.",
        4: "Se sienta sin apoyo y pasa un objeto de una mano a otra.",
        5: "Gatea para alcanzar un juguete y balbucea sonidos de dos sílabas.",
        6: "Camina con apoyo y señala para pedir lo que quiere.",
        7: "Corre y sube escalones alternando los pies; dice sus primeras palabras.",
        8: "Arma torres de tres cubos y juega a dar de comer a un muñeco.",
        9: "Comparte un juguete y sigue instrucciones de dos pasos en el juego.",
    }
    return f"{nombre}: {frases.get(nivel, 'Muestra una conducta del nivel observado.')}"


def main() -> None:
    p = Plataforma()
    c = p.con

    # --- idempotencia: limpiar lo sembrado antes ---
    c.execute("DELETE FROM observaciones WHERE origen=?", (ORIGEN,))
    c.execute("DELETE FROM evaluaciones_pendientes WHERE id_nino_propuesto IN "
              "(SELECT id_nino FROM ninos WHERE id_jardin=?)", (JARDIN,))
    c.commit()

    total_obs = 0
    sembrados: list[tuple[str, str, str, int, int]] = []
    for sala, edu in CURSOS:
        ninos = p.ninos_de(JARDIN, sala)[:POR_CURSO]
        for i, nin in enumerate(ninos, 1):
            idn = nin["id_nino"]
            nombre = (nin.get("nombre_pila") or "").strip() or idn
            a, b = _niveles(i)
            # dos observaciones de niveles distintos y confianza parecida → margen bajo
            p.registrar_observacion(idn, edu, FECHA, "texto", a, _nota(nombre, a),
                                    dominios=["cognitivo"], manifestaciones=elegir(MANIF, a, "cognitivo", rnd=_RND),
                                    confianza=0.55, origen=ORIGEN, metodo_resolucion="demo")
            p.registrar_observacion(idn, edu, FECHA, "texto", b, _nota(nombre, b),
                                    dominios=["motor_fino"], manifestaciones=elegir(MANIF, b, "motor_fino", rnd=_RND),
                                    confianza=0.50, origen=ORIGEN, metodo_resolucion="demo")
            total_obs += 2
            sembrados.append((sala, idn, nombre, a, b))

    c.commit()

    # --- retroceder el watermark del cron para que PROCESE lo sembrado ---
    min_rid = c.execute("SELECT MIN(rowid) m FROM observaciones WHERE origen=?", (ORIGEN,)).fetchone()["m"]
    if min_rid is not None:
        p.set_meta("cron_watermark_rowid", str(int(min_rid) - 1))

    print(f"✅ Sembradas {total_obs} observaciones (origen={ORIGEN}) en {len(CURSOS)} cursos"
          f" · cron_watermark_rowid → {int(min_rid) - 1 if min_rid else '—'}")
    for sala, edu in CURSOS:
        hijos = [s for s in sembrados if s[0] == sala]
        print(f"  ▸ {sala:15} ({edu}) → {len(hijos)} niños · niveles " +
              ", ".join(f"{a}/{b}" for _, _, _, a, b in hijos))
    print("\nSiguiente paso: correr el cron para generar los pendientes →")
    print("  /opt/integra/.venv/bin/python -m src.evaluacion_periodica")


if __name__ == "__main__":
    main()
