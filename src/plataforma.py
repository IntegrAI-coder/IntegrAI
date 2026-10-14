"""Plataforma de datos E-1: espeja el esquema del dataset del desafío.

Jerarquía: jardines › educadoras › niños/as › observaciones › manifestaciones.
Carga el dataset público para poblar el demo y permite registrar observaciones
nuevas (las que llegan por WhatsApp). En producción: Aurora/DynamoDB sin tocar
la interfaz.
"""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import Any

from . import config, marco, trayectoria as tray

ESQUEMA = """
CREATE TABLE IF NOT EXISTS jardines (
    id_jardin TEXT PRIMARY KEY, nombre_fantasia TEXT, comuna TEXT, region TEXT,
    numero_salas INTEGER, numero_educadoras INTEGER);
CREATE TABLE IF NOT EXISTS educadoras (
    id_educadora TEXT PRIMARY KEY, id_jardin TEXT, rol TEXT, anios_experiencia INTEGER);
CREATE TABLE IF NOT EXISTS ninos (
    id_nino TEXT PRIMARY KEY, fecha_nacimiento TEXT, sexo_registrado TEXT,
    id_jardin TEXT, sala_grupo TEXT, fecha_ingreso TEXT);
CREATE TABLE IF NOT EXISTS observaciones (
    id_observacion TEXT PRIMARY KEY, id_nino TEXT, id_educadora TEXT,
    fecha_observacion TEXT, formato_captura TEXT, nivel_estimado INTEGER,
    nota_breve TEXT, confianza REAL, dominios TEXT, origen TEXT DEFAULT 'dataset');
CREATE TABLE IF NOT EXISTS observacion_manifestaciones (
    id_observacion TEXT, id_manifestacion TEXT, PRIMARY KEY (id_observacion, id_manifestacion));
CREATE INDEX IF NOT EXISTS ix_obs_nino ON observaciones(id_nino);
CREATE INDEX IF NOT EXISTS ix_ninos_jardin ON ninos(id_jardin, sala_grupo);
"""


class Plataforma:
    def __init__(self, path: str | None = None) -> None:
        self.path = path or config.DB_PATH
        self.con = sqlite3.connect(self.path, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(ESQUEMA)
        self.con.commit()

    # ------------------------------------------------------------------
    def cargar_dataset(self, datos_dir: str | Path) -> dict[str, int]:
        d = Path(datos_dir)
        if self.con.execute("SELECT COUNT(*) c FROM ninos").fetchone()["c"] > 0:
            return self.resumen()  # ya cargado
        def insert(tabla, archivo, cols):
            rows = list(csv.DictReader(open(d / archivo, encoding="utf-8")))
            ph = ",".join("?" for _ in cols)
            self.con.executemany(f"INSERT OR REPLACE INTO {tabla} ({','.join(cols)}) VALUES ({ph})",
                                 [[r.get(c) for c in cols] for r in rows])
            return len(rows)
        insert("jardines", "jardines.csv", ["id_jardin","nombre_fantasia","comuna","region","numero_salas","numero_educadoras"])
        insert("educadoras", "educadoras.csv", ["id_educadora","id_jardin","rol","anios_experiencia"])
        insert("ninos", "ninos.csv", ["id_nino","fecha_nacimiento","sexo_registrado","id_jardin","sala_grupo","fecha_ingreso"])
        insert("observaciones", "observaciones.csv",
               ["id_observacion","id_nino","id_educadora","fecha_observacion","formato_captura","nivel_estimado","nota_breve"])
        insert("observacion_manifestaciones", "observacion_manifestaciones.csv",
               ["id_observacion","id_manifestacion"])
        self.con.commit()
        return self.resumen()

    # ------------------------------------------------------------------
    def _nuevo_id_observacion(self) -> str:
        n = self.con.execute("SELECT COUNT(*) c FROM observaciones").fetchone()["c"] + 1
        return f"OBS-{n:07d}-APP" if any(r["id_observacion"].endswith("-APP") for r in []) else f"OBS-9{n:06d}"

    def registrar_observacion(self, id_nino: str, id_educadora: str | None, fecha: str,
                              formato: str, nivel: int | None, nota: str,
                              dominios: list[str] | None = None, manifestaciones: list[str] | None = None,
                              confianza: float = 0.0, origen: str = "whatsapp") -> str:
        base = self.con.execute("SELECT COUNT(*) c FROM observaciones").fetchone()["c"]
        oid = f"OBS-{9000000 + base + 1}"
        self.con.execute(
            "INSERT INTO observaciones (id_observacion,id_nino,id_educadora,fecha_observacion,formato_captura,"
            "nivel_estimado,nota_breve,confianza,dominios,origen) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (oid, id_nino, id_educadora, fecha, formato, nivel, (nota or "")[:280],
             confianza, ",".join(dominios or []), origen))
        for mid in manifestaciones or []:
            self.con.execute("INSERT OR IGNORE INTO observacion_manifestaciones (id_observacion,id_manifestacion) VALUES (?,?)", (oid, mid))
        self.con.commit()
        return oid

    # ------------------------------------------------------------------
    def nino(self, id_nino: str) -> dict | None:
        r = self.con.execute("SELECT * FROM ninos WHERE id_nino=?", (id_nino,)).fetchone()
        return dict(r) if r else None

    def observaciones_de(self, id_nino: str) -> list[dict]:
        nin = self.nino(id_nino) or {}
        rows = self.con.execute(
            "SELECT * FROM observaciones WHERE id_nino=? ORDER BY fecha_observacion, id_observacion", (id_nino,)).fetchall()
        out = []
        for r in rows:
            d = dict(r); d["formato"] = d.pop("formato_captura")
            d["nivel"] = d.pop("nivel_estimado")
            d["fecha"] = d["fecha_observacion"]
            if nin.get("fecha_nacimiento"):
                d["edad_meses"] = marco.edad_meses(nin["fecha_nacimiento"], d["fecha_observacion"])
            out.append(d)
        return out

    def trayectoria(self, id_nino: str, fecha_ref: str | None = None) -> dict:
        nin = self.nino(id_nino)
        if not nin:
            return {}
        obs = self.observaciones_de(id_nino)
        ref = fecha_ref or (obs[-1]["fecha_observacion"] if obs else nin["fecha_nacimiento"])
        edad_actual = marco.edad_meses(nin["fecha_nacimiento"], ref)
        t = tray.construir(id_nino, obs, edad_actual)
        d = t.to_dict(); d["nino"] = nin
        return d

    def ninos_de(self, id_jardin: str | None = None, sala_grupo: str | None = None) -> list[dict]:
        q = "SELECT * FROM ninos WHERE 1=1"; p: list[Any] = []
        if id_jardin: q += " AND id_jardin=?"; p.append(id_jardin)
        if sala_grupo: q += " AND sala_grupo=?"; p.append(sala_grupo)
        return [dict(r) for r in self.con.execute(q + " ORDER BY id_nino", p).fetchall()]

    def panorama(self, id_jardin: str | None = None, sala_grupo: str | None = None,
                 fecha_ref: str = "2026-10-13", solo_alertas: bool = False) -> list[dict]:
        filas = []
        for n in self.ninos_de(id_jardin, sala_grupo):
            t = self.trayectoria(n["id_nino"], fecha_ref)
            filas.append({
                "id_nino": n["id_nino"], "id_jardin": n["id_jardin"], "sala_grupo": n["sala_grupo"],
                "nivel_actual": t.get("nivel_actual"), "nombre_nivel": marco.nombre_nivel(t["nivel_actual"]) if t.get("nivel_actual") else "—",
                "tendencia": t.get("tendencia"), "n_observaciones": t.get("n_observaciones"),
                "alertas": t.get("alertas", []), "edad_meses": None,
            })
            nin = self.nino(n["id_nino"])
            if nin and nin.get("fecha_nacimiento"):
                filas[-1]["edad_meses"] = marco.edad_meses(nin["fecha_nacimiento"], fecha_ref)
        if solo_alertas:
            filas = [f for f in filas if f["alertas"]]
        return filas

    def jardines(self) -> list[dict]:
        return [dict(r) for r in self.con.execute("SELECT * FROM jardines ORDER BY id_jardin").fetchall()]

    def resumen(self) -> dict[str, int]:
        def c(t): return self.con.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
        return {t: c(t) for t in ("jardines","educadoras","ninos","observaciones","observacion_manifestaciones")}
