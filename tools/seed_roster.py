#!/usr/bin/env python3
"""Siembra un ROSTER de demo (nombres) + educadora para hacer funcionar el resolver
en el jardín JAR-0001 (26 niños). Incluye un homónimo 'Sebastián' para demostrar la
regla de apellido. Idempotente."""
import sqlite3

DB = "/opt/integra/plataforma.db"
JARDIN = "JAR-0001"

# 26 nombres chilenos; dos "Sebastián" (homónimo) para el demo del apellido
NOMBRES = [
    ("Martina", "Soto"), ("Matías", "Rojas"), ("Sebastián", "Wagner"), ("Sebastián", "Pérez"),
    ("Josefa", "Muñoz"), ("Tomás", "González"), ("Emilia", "Contreras"), ("Agustín", "Silva"),
    ("Isidora", "Sepúlveda"), ("Benjamín", "Morales"), ("Antonia", "Fuentes"), ("Vicente", "Araya"),
    ("Catalina", "Riquelme"), ("Alonso", "Cáceres"), ("Florencia", "Vidal"), ("Gaspar", "Espinoza"),
    ("Amanda", "Tapia"), ("Lucas", "Bravo"), ("Trinidad", "Herrera"), ("Facundo", "Navarro"),
    ("Renata", "Cortés"), ("Ignacio", "Castillo"), ("Magdalena", "Vergara"), ("Thiago", "Rivas"),
    ("Colomba", "Orellana"), ("Damián", "Paredes"),
]

c = sqlite3.connect(DB)

def asegurar(tabla, col, tipo):
    cols = [r[1] for r in c.execute(f"PRAGMA table_info({tabla})")]
    if col not in cols:
        c.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} {tipo}")

asegurar("ninos", "nombre_pila", "TEXT")
asegurar("ninos", "apellidos", "TEXT")
asegurar("educadoras", "telefono_whatsapp", "TEXT")
c.execute("CREATE TABLE IF NOT EXISTS educadora_salas (id_educadora TEXT, sala_grupo TEXT, id_jardin TEXT, PRIMARY KEY (id_educadora, sala_grupo))")
c.execute("CREATE TABLE IF NOT EXISTS ninos_alias (id_nino TEXT, alias TEXT, PRIMARY KEY (id_nino, alias))")

ninos = [r[0] for r in c.execute("SELECT id_nino FROM ninos WHERE id_jardin=? ORDER BY id_nino", (JARDIN,))]
for idn, (n, a) in zip(ninos, NOMBRES):
    c.execute("UPDATE ninos SET nombre_pila=?, apellidos=? WHERE id_nino=?", (n, a, idn))

c.execute("INSERT OR REPLACE INTO educadoras (id_educadora,id_jardin,rol,telefono_whatsapp) "
          "VALUES ('EDU-DEMO',?, 'educadora_parvulos','+56900000000')", (JARDIN,))
c.execute("INSERT OR IGNORE INTO educadora_salas (id_educadora,sala_grupo,id_jardin) VALUES ('EDU-DEMO','SG-A',?)", (JARDIN,))
c.commit()

print(f"jardín {JARDIN}: {len(ninos)} niños con nombre sembrados")
for r in c.execute("SELECT id_nino, nombre_pila, apellidos FROM ninos WHERE id_jardin=? AND nombre_pila IS NOT NULL LIMIT 5", (JARDIN,)):
    print("  ", r)
