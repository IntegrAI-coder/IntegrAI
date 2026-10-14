"""Marco de evaluación E-1: la ruta de niveles + catálogo de manifestaciones.

Fuente: dataset público del desafío (ruta_niveles.csv, manifestaciones.csv, dominios).
Es la "verdad" del dominio: 9 niveles, 5 dominios y 90 conductas observables.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any
from datetime import date
import json

from . import config

# --- stopwords mínimas español (para el matcher léxico) ---
STOPWORDS = {
    "de", "la", "el", "los", "las", "un", "una", "unos", "unas", "y", "o", "u",
    "que", "con", "por", "para", "en", "al", "del", "se", "su", "sus", "lo",
    "es", "fue", "ha", "han", "como", "más", "mas", "durante", "cuando", "donde",
    "a", "e", "i", "ni", "sin", "sobre", "entre", "tras", "hacia", "desde",
    "me", "te", "le", "les", "nos", "mi", "tu", "esta", "este", "esto", "esa",
}


@lru_cache(maxsize=1)
def ruta_niveles() -> tuple[dict, ...]:
    d = json.loads((config.DATA / "ruta_niveles.json").read_text(encoding="utf-8"))
    return tuple(d)


@lru_cache(maxsize=1)
def manifestaciones() -> tuple[dict, ...]:
    d = json.loads((config.DATA / "manifestaciones.json").read_text(encoding="utf-8"))
    return tuple(d)


@lru_cache(maxsize=1)
def dominios() -> tuple[dict, ...]:
    return tuple(json.loads((config.DATA / "dominios.json").read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def man_por_id() -> dict[str, dict]:
    return {m["id"]: m for m in manifestaciones()}


@lru_cache(maxsize=1)
def nivel_info() -> dict[int, dict]:
    return {n["nivel"]: n for n in ruta_niveles()}


def nombre_nivel(nivel: int) -> str:
    n = nivel_info().get(int(nivel))
    return n["nombre_nivel"] if n else f"Nivel {nivel}"


def nombre_dominio(did: str) -> str:
    for d in dominios():
        if d["id"] == did:
            return d["nombre"]
    return did


# --------------------------------------------------------------------------
# Edad y holgura etaria
# --------------------------------------------------------------------------
def edad_meses(fecha_nac: str, fecha_obs: str) -> int:
    """Meses completos (fórmula del dataset)."""
    an, mn, dn = (int(x) for x in fecha_nac.split("-"))
    ao, mo, do = (int(x) for x in fecha_obs.split("-"))
    return 12 * (ao - an) + (mo - mn) - (1 if do < dn else 0)


def niveles_esperados_por_edad(edad: int) -> list[int]:
    """Niveles cuya banda etaria orientativa contiene (o roza) la edad dada."""
    esperados = []
    for n in ruta_niveles():
        if n["edad_min_meses"] <= edad <= n["edad_max_meses"]:
            esperados.append(n["nivel"])
    if not esperados:
        # holgura: el más cercano
        esperados = [min(ruta_niveles(), key=lambda n: abs((n["edad_min_meses"] + n["edad_max_meses"]) / 2 - edad))["nivel"]]
    return esperados


def descripcion_nivel(nivel: int) -> str:
    """Texto rico de un nivel, para las 'criteria' del decision model (Laya)."""
    i = nivel_info().get(int(nivel))
    if not i:
        return f"Nivel {nivel}"
    return f'{i["nombre_nivel"]} ({i["edad_min_meses"]}-{i["edad_max_meses"]}m): {i["descripcion"]}'


def resumen_marco() -> dict[str, int]:
    return {"niveles": len(ruta_niveles()), "manifestaciones": len(manifestaciones()),
            "dominios": len(dominios())}
