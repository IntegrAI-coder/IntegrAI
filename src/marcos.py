"""Marcos de evaluación intercambiables.

- MarcoRubrica ("integra_iya", PRINCIPAL): rúbrica oficial de Integra, núcleo Identidad y Autonomía,
  3 tramos (Sala Cuna, Nivel Medio, Transición) × 8 niveles (Comenzando … Profundizando).
  Se genera con tools/importar_rubrica.py (el JSON no se versiona: material de Integra).
- MarcoDatasetE1 ("dataset_e1"): los 9 niveles × 5 dominios del dataset sintético (src/marco.py),
  para regresión.

El tramo se define por la edad al 31 de marzo del año escolar (ChileAtiende, ficha 1786):
Sala Cuna 0–2 años, Nivel Medio 2–4, Transición 4–6. Dentro de un tramo la edad NO fija el nivel.
"""
from __future__ import annotations

import json
from datetime import date
from functools import lru_cache

from . import config

ARCHIVO_RUBRICA = config.DATA / "marcos" / "integra_identidad_autonomia.json"


# --------------------------------------------------------------------------- tramos
def _fecha(f: str | date) -> date:
    return f if isinstance(f, date) else date.fromisoformat(str(f)[:10])


def meses_entre(nac: date, ref: date) -> int:
    return 12 * (ref.year - nac.year) + (ref.month - nac.month) - (1 if ref.day < nac.day else 0)


def edad_al_corte(fecha_nac: str | date, fecha_obs: str | date) -> int:
    """Edad en meses al 31 de marzo del año escolar de la observación (el año escolar parte en marzo)."""
    nac, obs = _fecha(fecha_nac), _fecha(fecha_obs)
    anio = obs.year if obs.month >= 3 else obs.year - 1
    return meses_entre(nac, date(anio, 3, 31))


def tramo_por_meses(meses: int | None, marco: "Marco | None" = None) -> tuple[str, str] | None:
    """(tramo, subtramo) o None si la edad está fuera de 0–72 meses o es desconocida."""
    if meses is None or meses < 0:
        return None
    for t in (marco or marco_activo()).tramos():
        if t["edad_min_meses"] <= meses < t["edad_max_meses"]:
            sub = next((s["id"] for s in t.get("subtramos", []) if s["edad_min_meses"] <= meses < s["edad_max_meses"]), t["id"])
            return t["id"], sub
    return None


def tramo_por_edad(fecha_nac: str | date, fecha_obs: str | date, marco: "Marco | None" = None) -> tuple[str, str] | None:
    # nacido después del 31 de marzo del año escolar: ingresa a Sala Cuna Menor (edad al corte = 0)
    meses = edad_al_corte(fecha_nac, fecha_obs)
    if meses < 0 and _fecha(fecha_nac) <= _fecha(fecha_obs):
        meses = 0
    return tramo_por_meses(meses, marco)


# --------------------------------------------------------------------------- marcos
class Marco:
    id = "base"

    def tramos(self) -> list[dict]: ...
    def niveles(self, tramo: str) -> list[int]: ...
    def nombre_nivel(self, tramo: str, nivel: int) -> str: ...
    def descripcion_nivel(self, tramo: str, nivel: int) -> str: ...
    def anclas(self, tramo: str | None = None) -> list[dict]: ...
    def dimensiones_observables(self) -> list[str]: ...

    def tramo(self, tramo_id: str) -> dict:
        return next(t for t in self.tramos() if t["id"] == tramo_id)


class MarcoRubrica(Marco):
    id = "integra_iya"

    def __init__(self, data: dict | None = None) -> None:
        if data is None:
            if not ARCHIVO_RUBRICA.exists():
                raise FileNotFoundError(f"falta {ARCHIVO_RUBRICA}: ejecuta tools/importar_rubrica.py <rúbrica.docx>")
            data = json.loads(ARCHIVO_RUBRICA.read_text(encoding="utf-8"))
        self.data = data
        self._nivel = {(t["id"], l["nivel"]): l for t in data["tramos"] for l in t["niveles"]}

    def tramos(self) -> list[dict]:
        return self.data["tramos"]

    def niveles(self, tramo: str) -> list[int]:
        return [l["nivel"] for l in self.tramo(tramo)["niveles"]]

    def nombre_nivel(self, tramo: str, nivel: int) -> str:
        return self._nivel[(tramo, nivel)]["nombre"]

    def descripcion_nivel(self, tramo: str, nivel: int) -> str:
        """Criterio para el decisor: descripción + conducta observable (sin los ejemplos)."""
        l = self._nivel[(tramo, nivel)]
        return f"{l['descripcion']} Conducta observable: {' '.join(l['conductas'])}"

    def anclas(self, tramo: str | None = None) -> list[dict]:
        """Textos de referencia por nivel para el matcher: descripción, conductas y ejemplos."""
        out = []
        for t in self.tramos():
            if tramo and t["id"] != tramo:
                continue
            for l in t["niveles"]:
                base = f"IYA-{t['sigla']}-N{l['nivel']:02d}"
                textos = [("D", l["descripcion"])] + [(f"C{i}", c) for i, c in enumerate(l["conductas"], 1)] \
                         + [(f"E{i}", e) for i, e in enumerate(l["ejemplos"], 1)]
                for suf, texto in textos:
                    out.append({"id": f"{base}-{suf}", "nivel": l["nivel"], "tramo": t["id"],
                                "dominio": self.data["nucleo"]["id"], "tipo": suf[0], "texto": texto})
        return out

    def dimensiones_observables(self) -> list[str]:
        return ["expresión de emociones (llanto, sonrisa, enojo) y cómo se regula",
                "separación del adulto y confianza ante situaciones nuevas",
                "autonomía en rutinas: alimentación, siesta, higiene, vestirse, guardar sus cosas",
                "grado de apoyo: con ayuda del adulto, con recordatorio, solo, por iniciativa propia",
                "reconocimiento de sí mismo: su nombre, su imagen en el espejo, sus características",
                "preferencias, elecciones y posesión ('mío')",
                "turnos, acuerdos del grupo, conflictos y cómo los resuelve",
                "juego simbólico, proyectos y perseverancia ante la dificultad",
                "lo que el niño o niña DICE, textual"]


class MarcoDatasetE1(Marco):
    """Los 9 niveles × 5 dominios del dataset (0–36 meses) como un único tramo, para regresión."""
    id = "dataset_e1"

    def __init__(self) -> None:
        from . import marco as m
        self.m = m

    def tramos(self) -> list[dict]:
        return [{"id": "e1", "nombre": "Dataset E-1", "sigla": "E1", "edad_min_meses": 0, "edad_max_meses": 37,
                 "niveles": [{"nivel": n["nivel"], "nombre": n["nombre_nivel"]} for n in self.m.ruta_niveles()]}]

    def niveles(self, tramo: str) -> list[int]:
        return [n["nivel"] for n in self.m.ruta_niveles()]

    def nombre_nivel(self, tramo: str, nivel: int) -> str:
        return self.m.nombre_nivel(nivel)

    def descripcion_nivel(self, tramo: str, nivel: int) -> str:
        return self.m.descripcion_nivel(nivel)

    def anclas(self, tramo: str | None = None) -> list[dict]:
        return [{**x, "tramo": "e1", "tipo": "M"} for x in self.m.manifestaciones()]

    def dimensiones_observables(self) -> list[str]:
        return ["postura y control de cabeza y tronco", "desplazamiento (con o sin apoyo)", "uso de las manos",
                "comunicación y lenguaje", "interacción y emociones", "exploración y resolución de problemas"]


@lru_cache(maxsize=4)
def obtener(marco_id: str) -> Marco:
    return {"integra_iya": MarcoRubrica, "dataset_e1": MarcoDatasetE1}[marco_id]()


def marco_activo() -> Marco:
    return obtener(config.MARCO)
