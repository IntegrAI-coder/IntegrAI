#!/usr/bin/env python3
"""Demo end-to-end del agente IntegraAI sobre el dataset E-1.

    python3 demo_cli.py                 # escenario con un niño real del dataset
    python3 demo_cli.py NINO-00002      # otro niño/a
"""
from __future__ import annotations

import sys
from pathlib import Path

from src import config, marco
from src.agente import AgenteIntegra
from src.plataforma import Plataforma
from src.whatsapp import CanalConsola, MensajeEntrante

SEP = "=" * 72
DATOS = config.datos_dir()


def main() -> None:
    id_nino = sys.argv[1] if len(sys.argv) > 1 else "NINO-00002"

    canal = CanalConsola()
    pl = Plataforma(path=":memory:")
    if DATOS.exists():
        pl.cargar_dataset(DATOS)
    agente = AgenteIntegra(canal=canal, plataforma=pl)

    nin = pl.nino(id_nino)
    print(SEP); print(f"🧒 {id_nino} · jardín {nin['id_jardin']} · sala {nin['sala_grupo']} · nace {nin['fecha_nacimiento']}"); print(SEP)

    # Una "nota" sintética que la tía mandaría por WhatsApp
    nota = ("Hoy la observé durante el juego libre: se sacó y guardó sus zapatos solo, "
            "armó una torre y contó hasta cinco bloques. Conversó con una compañera y "
            "compartió los materiales por turnos.")
    print("📲 MENSAJE ENTRANTE (texto)\n  " + nota + "\n")

    msg = MensajeEntrante(de="+56 9 1234 5678", texto=nota, ts="2026-10-13",
                          id_nino=id_nino, id_educadora="EDU-0002", formato="texto")
    res = agente.procesar_mensaje(msg)

    cl = res["clasificacion"]
    print(SEP); print("🧠 DECISIÓN TIPADA (matcher híbrido + prior etario)"); print(SEP)
    print(f"  Nivel estimado : {cl['nivel']} · {cl['nombre_nivel']}")
    print(f"  Confianza      : {int(cl['confianza']*100)}%  |  evidencia suficiente: {cl['evidencia_suficiente']}")
    print(f"  Edad           : {cl['edad_meses']} meses  (banda esperada: {cl['niveles_esperados']})")
    print(f"  Dominios       : {[marco.nombre_dominio(d) for d in cl['dominios']]}")
    if cl['alerta_rezago']:
        print("  ⚠️ ALERTA       : nivel por debajo de la banda etaria")
    print("\n  Manifestaciones detectadas:")
    for m in cl["manifestaciones"]:
        print(f"    · [{m['id']}] (L{m['nivel']}/{m['dominio']}) score={m['score']}  {m['texto'][:70]}")

    print(SEP); print("🗄️ PLATAFORMA"); print(SEP)
    print("  Resumen:", pl.resumen())
    t = res["trayectoria"]
    print(f"  Trayectoria NINO {id_nino}: nivel {t['nivel_inicial']}→{t['nivel_actual']} · tendencia {t['tendencia']} · {t['n_observaciones']} obs.")
    for a in t["alertas"]:
        print("   ⚠️", a)
    print("\n  Puntos:", [(p['fecha'], p['nivel']) for p in t['puntos']])


if __name__ == "__main__":
    main()
