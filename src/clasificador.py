"""Clasificador tipado E-1: evidencia -> nivel de la ruta (1-9) + dominios.

    texto
      -> Matcher           (¿qué manifestaciones aparecen? = la evidencia)
      -> Decisor           (híbrido | Laya typesafe -> nivel + confianza calibrada)
      -> Clasificacion     (resultado tipado y auditable)

El decisor es intercambiable (ver backend_decision.py): "el matcher propone,
el decision model decide".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import config, marco
from .backend_decision import DecisorBase, construir_decisor
from .matcher import Match, Matcher


@dataclass
class Clasificacion:
    texto: str
    nivel: int | None
    probabilidades: dict[int, float]
    confianza: float
    evidencia_suficiente: bool
    dominios: list[str]
    matches: list[Match] = field(default_factory=list)
    edad_meses: int | None = None
    niveles_esperados: list[int] = field(default_factory=list)
    alerta_rezago: bool = False
    backend: str = "hibrido"
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nivel": self.nivel,
            "nombre_nivel": marco.nombre_nivel(self.nivel) if self.nivel else None,
            "probabilidades": self.probabilidades,
            "confianza": round(self.confianza, 3),
            "evidencia_suficiente": self.evidencia_suficiente,
            "dominios": self.dominios,
            "edad_meses": self.edad_meses,
            "niveles_esperados": self.niveles_esperados,
            "alerta_rezago": self.alerta_rezago,
            "backend": self.backend,
            "manifestaciones": [m.to_dict() for m in self.matches],
            "meta": self.meta,
        }


class Clasificador:
    def __init__(self, matcher: Matcher | None = None, decisor: DecisorBase | None = None,
                 backend: str | None = None) -> None:
        self.matcher = matcher or Matcher()
        self.decisor = decisor or construir_decisor(backend or config.BACKEND_DECISION)

    def clasificar(self, texto: str, edad_meses: int | None = None,
                   umbral_evidencia: float = 0.5) -> Clasificacion:
        matches = self.matcher.matchear(texto)
        esperados = marco.niveles_esperados_por_edad(edad_meses) if edad_meses is not None else []

        dec = self.decisor.decidir(texto, matches, edad_meses, esperados, umbral_evidencia)

        # alerta de rezago: nivel observado por debajo de la banda etaria esperada
        alerta = bool(edad_meses is not None and dec.nivel is not None and esperados
                      and dec.nivel < min(esperados))

        return Clasificacion(
            texto=texto, nivel=dec.nivel, probabilidades=dec.probabilidades,
            confianza=dec.confianza, evidencia_suficiente=dec.suficiente,
            dominios=dec.dominios, matches=matches, edad_meses=edad_meses,
            niveles_esperados=esperados, alerta_rezago=alerta,
            backend=dec.backend, meta=dec.meta,
        )
