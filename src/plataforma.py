"""Plataforma de datos E-1: espeja el esquema del dataset del desafío.

Jerarquía: jardines › educadoras › niños/as › observaciones › manifestaciones.
Carga el dataset público para poblar el demo y permite registrar observaciones
nuevas (las que llegan por WhatsApp). En producción: Aurora/DynamoDB sin tocar
la interfaz.

v2 (14-oct-2026) — arquitectura "WhatsApp solo-entrada":
  · roster de nombres (resolver nombre→id)   -> ninos.nombre_pila/apellidos + ninos_alias
  · educadora <-> WhatsApp <-> sala          -> educadoras.telefono_whatsapp + educadora_salas
  · estado de resolución en la observación   -> observaciones.metodo_resolucion/margen/estado/id_mensaje
  · human-in-the-loop                         -> evaluaciones_pendientes (staging) vs evaluaciones (canónica)
  · watermark del cron                         -> meta(clave,valor)
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

-- ==== v2: arquitectura WhatsApp solo-entrada ====
CREATE TABLE IF NOT EXISTS ninos_alias (
    id_nino TEXT, alias TEXT, PRIMARY KEY (id_nino, alias));
CREATE TABLE IF NOT EXISTS educadora_salas (
    id_educadora TEXT, sala_grupo TEXT, id_jardin TEXT,
    PRIMARY KEY (id_educadora, sala_grupo));
CREATE TABLE IF NOT EXISTS evaluaciones_pendientes (
    id_pendiente TEXT PRIMARY KEY, id_mensaje TEXT, id_nino_propuesto TEXT,
    candidatos TEXT, nivel_propuesto INTEGER, dominio TEXT, confianza REAL, margen REAL,
    motivo TEXT, evidencia TEXT, estado TEXT DEFAULT 'pendiente',
    creado_en TEXT, resuelto_en TEXT, resuelto_por TEXT, id_educadora TEXT);
CREATE TABLE IF NOT EXISTS evaluaciones (
    id_evaluacion TEXT PRIMARY KEY, id_nino TEXT, dominio TEXT, nivel INTEGER,
    confianza REAL, margen REAL, periodo TEXT, tendencia TEXT, alerta TEXT, generado_en TEXT);
CREATE TABLE IF NOT EXISTS meta (clave TEXT PRIMARY KEY, valor TEXT);
"""

# Migraciones idempotentes: (tabla, columna, tipo)
_MIGRACIONES = [
    ("ninos", "nombre_pila", "TEXT"),
    ("ninos", "apellidos", "TEXT"),
    ("educadoras", "telefono_whatsapp", "TEXT"),
    ("observaciones", "metodo_resolucion", "TEXT"),
    ("observaciones", "margen", "REAL"),
    ("observaciones", "estado", "TEXT DEFAULT 'auto'"),
    ("observaciones", "id_mensaje", "TEXT"),
    ("evaluaciones_pendientes", "id_educadora", "TEXT"),
]


class Plataforma:
    def __init__(self, path: str | None = None) -> None:
        self.path = path or config.DB_PATH
        self.con = sqlite3.connect(self.path, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(ESQUEMA)
        self._migrar()
        self.con.commit()

    # ------------------------------------------------------------------
    def _migrar(self) -> None:
        """Agrega columnas v2 si faltan (idempotente)."""
        for tabla, col, tipo in _MIGRACIONES:
            cols = {r["name"] for r in self.con.execute(f"PRAGMA table_info({tabla})")}
            if col not in cols:
                self.con.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} {tipo}")
        # dedupe de mensajes de WhatsApp reenviados
        self.con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_obs_msg "
                         "ON observaciones(id_mensaje) WHERE id_mensaje IS NOT NULL")

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

    # ==================================================================
    # ROSTER + RUTEO WHATSAPP (para el resolver)
    # ==================================================================
    def roster_sala(self, id_jardin: str | None = None, sala_grupo: str | None = None) -> list[dict]:
        """Filas para el resolver: id_nino + nombre_pila + apellidos (+ alias)."""
        q = "SELECT id_nino, nombre_pila, apellidos FROM ninos WHERE 1=1"
        p: list[Any] = []
        if id_jardin: q += " AND id_jardin=?"; p.append(id_jardin)
        if sala_grupo: q += " AND sala_grupo=?"; p.append(sala_grupo)
        filas = [dict(r) for r in self.con.execute(q, p).fetchall()]
        # alias -> se agregan como "nombre_pila" extra para el resolver
        for f in filas:
            for a in self.con.execute("SELECT alias FROM ninos_alias WHERE id_nino=?", (f["id_nino"],)):
                filas.append({"id_nino": f["id_nino"], "nombre_pila": a["alias"], "apellidos": f.get("apellidos") or ""})
        return filas

    def definir_nombre(self, id_nino: str, nombre_pila: str, apellidos: str = "") -> None:
        self.con.execute("UPDATE ninos SET nombre_pila=?, apellidos=? WHERE id_nino=?",
                         (nombre_pila, apellidos, id_nino))
        self.con.commit()

    def salas_de_whatsapp(self, telefono: str) -> list[dict]:
        """Rutea un número de WhatsApp -> educadora(s) y su(s) sala(s)."""
        q = ("SELECT e.id_educadora, e.id_jardin, es.sala_grupo "
             "FROM educadoras e JOIN educadora_salas es ON es.id_educadora=e.id_educadora "
             "WHERE e.telefono_whatsapp=?")
        return [dict(r) for r in self.con.execute(q, (telefono,)).fetchall()]

    def vincular_whatsapp(self, id_educadora: str, telefono: str, salas: list[tuple[str, str]]) -> None:
        """salas = [(id_jardin, sala_grupo), ...]"""
        self.con.execute("UPDATE educadoras SET telefono_whatsapp=? WHERE id_educadora=?", (telefono, id_educadora))
        for id_jardin, sala in salas:
            self.con.execute("INSERT OR IGNORE INTO educadora_salas (id_educadora,sala_grupo,id_jardin) VALUES (?,?,?)",
                             (id_educadora, sala, id_jardin))
        self.con.commit()

    def educadoras_con_whatsapp(self) -> list[dict]:
        """Todas las educadoras con numero de WhatsApp registrado (+ sus salas)."""
        q = ("SELECT e.id_educadora, e.id_jardin, e.telefono_whatsapp, es.sala_grupo "
             "FROM educadoras e LEFT JOIN educadora_salas es ON es.id_educadora=e.id_educadora "
             "WHERE e.telefono_whatsapp IS NOT NULL AND TRIM(e.telefono_whatsapp)<>''")
        return [dict(r) for r in self.con.execute(q).fetchall()]

    def ruta_de_whatsapp(self, telefono: str) -> list[dict]:
        """Rutea un numero entrante -> educadora(s) y su(s) sala(s).

        Normaliza el telefono (solo digitos) y acepta coincidencia por sufijo
        (ultimos 9 digitos), para tolerar diferencias de prefijo pais (56) o formato (+).
        Si el numero no esta registrado devuelve [] (el llamador decide el fallback).
        """
        def _digits(s: str) -> str:
            return "".join(ch for ch in (s or "") if ch.isdigit())

        d = _digits(telefono)
        if not d:
            return []
        out: list[dict] = []
        for f in self.educadoras_con_whatsapp():
            fd = _digits(f.get("telefono_whatsapp") or "")
            if not fd:
                continue
            if fd == d or (len(fd) >= 8 and len(d) >= 8 and fd[-9:] == d[-9:]):
                out.append(f)
        return out

    def educadora_de_sala(self, id_jardin: str | None, sala_grupo: str | None) -> str | None:
        """Devuelve la educadora (tia) responsable de una sala -> a quien asignar la cola."""
        if not sala_grupo:
            return None
        r = self.con.execute(
            "SELECT id_educadora FROM educadora_salas WHERE id_jardin IS ? AND sala_grupo=? LIMIT 1",
            (id_jardin, sala_grupo)).fetchone()
        return r["id_educadora"] if r else None

    # ==================================================================
    # OBSERVACIONES (con estado de resolución + idempotencia)
    # ==================================================================
    def registrar_observacion(self, id_nino: str, id_educadora: str | None, fecha: str,
                              formato: str, nivel: int | None, nota: str,
                              dominios: list[str] | None = None, manifestaciones: list[str] | None = None,
                              confianza: float = 0.0, origen: str = "whatsapp",
                              metodo_resolucion: str | None = None, margen: float | None = None,
                              estado: str = "auto", id_mensaje: str | None = None) -> str:
        # Idempotencia: si el mensaje ya se procesó, devolver la observación existente.
        if id_mensaje:
            ex = self.con.execute("SELECT id_observacion FROM observaciones WHERE id_mensaje=?", (id_mensaje,)).fetchone()
            if ex:
                return ex["id_observacion"]
        base = self.con.execute("SELECT COUNT(*) c FROM observaciones").fetchone()["c"]
        oid = f"OBS-{9000000 + base + 1}"
        self.con.execute(
            "INSERT INTO observaciones (id_observacion,id_nino,id_educadora,fecha_observacion,formato_captura,"
            "nivel_estimado,nota_breve,confianza,dominios,origen,metodo_resolucion,margen,estado,id_mensaje) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (oid, id_nino, id_educadora, fecha, formato, nivel, (nota or "")[:280],
             confianza, ",".join(dominios or []), origen, metodo_resolucion, margen, estado, id_mensaje))
        for mid in manifestaciones or []:
            self.con.execute("INSERT OR IGNORE INTO observacion_manifestaciones (id_observacion,id_manifestacion) VALUES (?,?)", (oid, mid))
        self.con.commit()
        return oid

    def observaciones_nuevas(self, desde_rowid: int = 0) -> list[dict]:
        """Observaciones con rowid > watermark y estado apto (auto/verificado) para el cron."""
        rows = self.con.execute(
            "SELECT rowid AS _rid, * FROM observaciones "
            "WHERE rowid > ? AND COALESCE(estado,'auto') IN ('auto','verificado') "
            "ORDER BY rowid", (desde_rowid,)).fetchall()
        return [dict(r) for r in rows]

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

    # ==================================================================
    # HUMAN-IN-THE-LOOP: cola de verificación
    # ==================================================================
    def encolar_pendiente(self, id_nino_propuesto: str | None, candidatos: list[str] | None,
                          nivel_propuesto: int | None, dominio: str | None, confianza: float,
                          margen: float, motivo: str, evidencia: str,
                          id_mensaje: str | None = None, creado_en: str | None = None,
                          id_educadora: str | None = None) -> str:
        n = self.con.execute("SELECT COUNT(*) c FROM evaluaciones_pendientes").fetchone()["c"]
        pid = f"PEND-{90000 + n + 1}"
        import json as _json
        self.con.execute(
            "INSERT INTO evaluaciones_pendientes (id_pendiente,id_mensaje,id_nino_propuesto,candidatos,"
            "nivel_propuesto,dominio,confianza,margen,motivo,evidencia,estado,creado_en,id_educadora) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,'pendiente',?,?)",
            (pid, id_mensaje, id_nino_propuesto, _json.dumps(candidatos or []), nivel_propuesto,
             dominio, confianza, margen, motivo, evidencia, creado_en, id_educadora))
        self.con.commit()
        return pid

    def pendientes(self, estado: str = "pendiente") -> list[dict]:
        return [dict(r) for r in self.con.execute(
            "SELECT * FROM evaluaciones_pendientes WHERE estado=? ORDER BY creado_en", (estado,)).fetchall()]

    def pendientes_de(self, id_educadora: str, estado: str = "pendiente") -> list[dict]:
        """La cola POR VERIFICAR de UNA tía (lo que ella debe confirmar)."""
        return [dict(r) for r in self.con.execute(
            "SELECT * FROM evaluaciones_pendientes WHERE estado=? AND id_educadora=? ORDER BY creado_en",
            (estado, id_educadora)).fetchall()]

    def resolver_pendiente(self, id_pendiente: str, accion: str, resuelto_por: str,
                           id_nino: str | None = None, nivel: int | None = None,
                           dominio: str | None = None, cuando: str | None = None) -> None:
        """accion: aprobado | editado | rechazado. Si aprobado/editado y hay nivel -> entra a `evaluaciones`."""
        self.con.execute("UPDATE evaluaciones_pendientes SET estado=?, resuelto_en=?, resuelto_por=? "
                         "WHERE id_pendiente=?", (accion, cuando, resuelto_por, id_pendiente))
        if accion in ("aprobado", "editado") and nivel is not None and id_nino:
            self.guardar_evaluacion(id_nino, dominio or "global", nivel, 1.0, 1.0,
                                    periodo=(cuando or "")[:10], tendencia="—", alerta=None,
                                    generado_en=cuando)
        self.con.commit()

    # ==================================================================
    # EVALUACIÓN CANÓNICA + WATERMARK
    # ==================================================================
    def guardar_evaluacion(self, id_nino: str, dominio: str, nivel: int, confianza: float,
                           margen: float, periodo: str, tendencia: str, alerta: str | None,
                           generado_en: str | None = None) -> str:
        n = self.con.execute("SELECT COUNT(*) c FROM evaluaciones").fetchone()["c"]
        eid = f"EVAL-{90000 + n + 1}"
        self.con.execute(
            "INSERT INTO evaluaciones (id_evaluacion,id_nino,dominio,nivel,confianza,margen,periodo,"
            "tendencia,alerta,generado_en) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (eid, id_nino, dominio, nivel, confianza, margen, periodo, tendencia, alerta, generado_en))
        self.con.commit()
        return eid

    def ultima_evaluacion(self, id_nino: str, dominio: str = "global") -> dict | None:
        r = self.con.execute("SELECT * FROM evaluaciones WHERE id_nino=? AND dominio=? "
                             "ORDER BY generado_en DESC LIMIT 1", (id_nino, dominio)).fetchone()
        return dict(r) if r else None

    def get_meta(self, clave: str, default: str | None = None) -> str | None:
        r = self.con.execute("SELECT valor FROM meta WHERE clave=?", (clave,)).fetchone()
        return r["valor"] if r else default

    def set_meta(self, clave: str, valor: str) -> None:
        self.con.execute("INSERT OR REPLACE INTO meta (clave,valor) VALUES (?,?)", (clave, valor))
        self.con.commit()

    def ultimo_rowid(self) -> int:
        r = self.con.execute("SELECT COALESCE(MAX(rowid),0) m FROM observaciones").fetchone()
        return int(r["m"])

    # ------------------------------------------------------------------
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
        return {t: c(t) for t in ("jardines","educadoras","ninos","observaciones",
                                  "observacion_manifestaciones","evaluaciones","evaluaciones_pendientes")}
