#!/usr/bin/env python3
"""Vincula un número de WhatsApp a una educadora y sus salas (mapeo tía -> sala).

Con esto el webhook deja de usar la sala fija: cada mensaje se rutea a la sala de
la educadora dueña de ese número.

uso:
  python3 tools/vincular_whatsapp.py --list
  python3 tools/vincular_whatsapp.py +569XXXXXXXX EDU-DEMO SG-A JAR-0001
  python3 tools/vincular_whatsapp.py --desvincular +569XXXXXXXX

En la EC2 (integra-server), correr desde /opt/integra con el venv del proyecto.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.getenv("INTEGRA_HOME", "/opt/integra"))

from src.plataforma import Plataforma  # noqa: E402

DB = os.getenv("INTEGRA_DB", "/opt/integra/plataforma.db")


def main() -> None:
    args = sys.argv[1:]
    plat = Plataforma(path=DB)

    if not args or args[0] in ("-l", "--list"):
        print("Educadoras con WhatsApp registrado:")
        for r in plat.educadoras_con_whatsapp():
            print(f"  {r['telefono_whatsapp']:>16}  ->  {r['id_educadora']}  ({r['id_jardin']}/{r.get('sala_grupo')})")
        return

    if args[0] == "--desvincular":
        tel = args[1]
        rows = plat.ruta_de_whatsapp(tel)
        for r in rows:
            plat.con.execute("UPDATE educadoras SET telefono_whatsapp=NULL WHERE id_educadora=?", (r["id_educadora"],))
        plat.con.commit()
        print(f"desvinculado {tel} ({len(rows)} educadora(s))")
        return

    tel = args[0]
    id_educadora = args[1] if len(args) > 1 else "EDU-DEMO"
    salas_arg = args[2] if len(args) > 2 else "SG-A"      # "SG-A" o "SG-A,SG-B"
    jardin = args[3] if len(args) > 3 else "JAR-0001"

    salas = [(jardin, s.strip()) for s in salas_arg.split(",") if s.strip()]
    plat.vincular_whatsapp(id_educadora, tel, salas)
    print(f"✅ {tel} -> {id_educadora} ({jardin}/{salas_arg})")
    for r in plat.ruta_de_whatsapp(tel):
        print(f"   verificado: {r}")


if __name__ == "__main__":
    main()
