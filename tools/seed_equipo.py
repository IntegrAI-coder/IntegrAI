#!/usr/bin/env python3
"""Siembra 4 CURSOS (uno por número del equipo) con 25-30 niños cada uno,
con nombres de pila REPETIDOS dentro de cada curso, para probar cómo el resolver
detecta homónimos y los diferencia por apellido.

- Jardín: JAR-EQUIPO ("Jardín Equipo — Demo")
- 4 salas: Sala Girasol / Mariposa / Estrella / Cometa
- 4 educadoras: EDU-EQ-1..4 (una por número de WhatsApp)
- Idempotente: re-crea el jardín desde cero cada vez.

Uso (en la EC2, con el venv):
    /opt/integra/.venv/bin/python tools/seed_equipo.py
"""
from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.getenv("INTEGRA_HOME", "/opt/integra"))
from src.plataforma import Plataforma  # noqa: E402

JARDIN = "JAR-EQUIPO"
NOMBRE_JARDIN = "Jardín Equipo — Demo"
SEED = 20261015

# (sala, id_educadora, teléfono)  — el orden sigue los números que pasó Wagner
CURSOS = [
    ("Sala Girasol",  "EDU-EQ-1", "+569 58947607"),       # Wagner
    ("Sala Mariposa", "EDU-EQ-2", "+569 41257056"),       # equipo 1
    ("Sala Estrella", "EDU-EQ-3", "+549 381 209 0006"),   # equipo 2 (AR)
    ("Sala Cometa",   "EDU-EQ-4", "+569 56433264"),       # equipo 3
]
TAMANOS = {"Sala Girasol": 28, "Sala Mariposa": 26, "Sala Estrella": 30, "Sala Cometa": 27}

PILA = [
    "Sofía", "Matías", "Emilia", "Mateo", "Isidora", "Benjamín", "Antonia", "Vicente",
    "Catalina", "Alonso", "Florencia", "Gaspar", "Amanda", "Lucas", "Trinidad", "Facundo",
    "Renata", "Ignacio", "Magdalena", "Thiago", "Colomba", "Damián", "Josefa", "Tomás",
    "Martina", "Agustín", "Valentina", "Sebastián", "Javiera", "Maximiliano", "Fernanda",
    "Cristóbal", "Constanza", "Diego", "Rocío", "Joaquín", "Paz", "Bruno", "Amparo", "Elías",
]
APE = [
    "Soto", "Rojas", "Muñoz", "González", "Contreras", "Silva", "Sepúlveda", "Morales",
    "Fuentes", "Araya", "Riquelme", "Cáceres", "Vidal", "Espinoza", "Tapia", "Bravo",
    "Herrera", "Navarro", "Cortés", "Castillo", "Vergara", "Rivas", "Orellana", "Paredes",
    "Salazar", "Castro", "Figueroa", "Godoy", "Núñez", "Reyes", "Álvarez", "Pinto",
    "Carrasco", "Sandoval", "Vargas", "Molina", "Farías", "Zúñiga", "Bustos", "Guzmán",
]


def generar_curso(n: int, rnd: random.Random) -> list[tuple[str, str]]:
    """Devuelve n (nombre_pila, apellido) con ~20-22 nombres únicos y el resto
    repeticiones de pila (homónimos), cada apellido único dentro del curso."""
    usados_ape: set[str] = set()

    def nuevo_ape() -> str:
        for _ in range(500):
            a = rnd.choice(APE)
            if a not in usados_ape:
                usados_ape.add(a)
                return a
        a = f"{rnd.choice(APE)} {rnd.choice(APE)}"   # fallback: dos apellidos
        usados_ape.add(a)
        return a

    base = rnd.sample(PILA, min(22, len(PILA)))
    kids = [(p, nuevo_ape()) for p in base]
    # repetir algunos nombres de pila (homónimos) hasta llegar a n
    repeticiones = [p for p in base[: min(len(base), 8)]]
    i = 0
    while len(kids) < n:
        kids.append((repeticiones[i % len(repeticiones)], nuevo_ape()))
        i += 1
    rnd.shuffle(kids)
    return kids


def main() -> None:
    rnd = random.Random(SEED)
    p = Plataforma()
    c = p.con

    # limpiar el jardín de pruebas (idempotente)
    ids = [r["id_nino"] for r in c.execute("SELECT id_nino FROM ninos WHERE id_jardin=?", (JARDIN,))]
    for idn in ids:
        c.execute("DELETE FROM ninos_alias WHERE id_nino=?", (idn,))
        c.execute("DELETE FROM observaciones WHERE id_nino=?", (idn,))
    c.execute("DELETE FROM ninos WHERE id_jardin=?", (JARDIN,))
    c.execute("DELETE FROM educadora_salas WHERE id_jardin=?", (JARDIN,))
    c.execute("DELETE FROM educadoras WHERE id_jardin=?", (JARDIN,))
    c.execute("DELETE FROM jardines WHERE id_jardin=?", (JARDIN,))

    c.execute("INSERT OR REPLACE INTO jardines (id_jardin,nombre_fantasia,comuna,region,numero_salas,numero_educadoras) "
              "VALUES (?,?,?,?,?,?)", (JARDIN, NOMBRE_JARDIN, "Providencia", "Metropolitana", len(CURSOS), len(CURSOS)))

    total = 0
    homonimos_todos = []
    for sala, edu, tel in CURSOS:
        kids = generar_curso(TAMANOS[sala], rnd)
        c.execute("INSERT OR REPLACE INTO educadoras (id_educadora,id_jardin,rol,anios_experiencia,telefono_whatsapp) "
                  "VALUES (?,?,?,?,?)", (edu, JARDIN, "educadora_parvulos", rnd.randint(2, 15), tel))
        c.execute("INSERT OR IGNORE INTO educadora_salas (id_educadora,sala_grupo,id_jardin) VALUES (?,?,?)", (edu, sala, JARDIN))

        por_pila: dict[str, list[str]] = {}
        for i, (pila, ape) in enumerate(kids, 1):
            idn = f"NINO-{edu[-1]}C-{i:02d}"          # ej NINO-1C-07
            sexto = rnd.choice(["F", "M"])
            anio = rnd.randint(2021, 2023)
            mes = rnd.randint(1, 12)
            c.execute("INSERT OR REPLACE INTO ninos (id_nino,fecha_nacimiento,sexo_registrado,id_jardin,sala_grupo,fecha_ingreso,nombre_pila,apellidos) "
                      "VALUES (?,?,?,?,?,?,?,?)",
                      (idn, f"{anio}-{mes:02d}-15", sexto, JARDIN, sala, "2026-03-01", pila, ape))
            por_pila.setdefault(pila, []).append(f"{pila} {ape}")
        total += len(kids)
        reps = {k: v for k, v in por_pila.items() if len(v) > 1}
        homonimos_todos.append((sala, tel, len(kids), reps))

    c.commit()

    print(f"✅ {JARDIN} · {NOMBRE_JARDIN} · {total} niños en {len(CURSOS)} cursos\n")
    for sala, tel, n, reps in homonimos_todos:
        print(f"  ▸ {sala}  ({n} niños)  ← {tel}")
        for nombre, quienes in sorted(reps.items()):
            print(f"       ⚠️  homónimo '{nombre}': " + " | ".join(quienes))
    print("\nEducadoras⇄WhatsApp:")
    for r in p.educadoras_con_whatsapp():
        if r["id_jardin"] == JARDIN:
            print(f"  {r['telefono_whatsapp']:>18} -> {r['id_educadora']} ({r['sala_grupo']})")


if __name__ == "__main__":
    main()
