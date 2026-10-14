"""Trayectoria de aprendizaje de un niño/a + alertas de rezago.

Convierte la serie de observaciones (cada una con un nivel estimado) en:
  - la trayectoria temporal (nivel por fecha),
  - la tendencia (sube / estable / baja acotada),
  - alertas (rezago etario, estancamiento).
Esto es lo que hoy no existe: pasar de "documentar" a "detectar a tiempo".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import marco


@dataclass
class Trayectoria:
    id_nino: str
    puntos: list[dict]          # [{fecha, edad_meses, nivel, nombre_nivel, formato}]
    nivel_inicial: int | None
    nivel_actual: int | None
    tendencia: str              # subiendo | estable | baja_acotada | sin_datos
    n_observaciones: int
    alertas: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id_nino": self.id_nino, "puntos": self.puntos,
            "nivel_inicial": self.nivel_inicial, "nivel_actual": self.nivel_actual,
            "tendencia": self.tendencia, "n_observaciones": self.n_observaciones,
            "alertas": self.alertas,
        }


def construir(id_nino: str, observaciones: list[dict],
              edad_meses_actual: int | None = None) -> Trayectoria:
    """observaciones: [{fecha, nivel, formato, edad_meses?}] ordenadas o no."""
    obs = [o for o in observaciones if o.get("nivel")]
    obs.sort(key=lambda o: o["fecha"])
    puntos = [{"fecha": o["fecha"], "edad_meses": o.get("edad_meses"),
               "nivel": o["nivel"], "nombre_nivel": marco.nombre_nivel(o["nivel"]),
               "formato": o.get("formato")} for o in obs]

    nivel_inicial = obs[0]["nivel"] if obs else None
    nivel_actual = obs[-1]["nivel"] if obs else None

    # tendencia: comparar el último tercio contra el primero
    if len(obs) >= 3:
        k = max(1, len(obs) // 3)
        inicial = sum(o["nivel"] for o in obs[:k]) / k
        final = sum(o["nivel"] for o in obs[-k:]) / k
        if final - inicial >= 1:
            tendencia = "subiendo"
        elif inicial - final >= 1:
            tendencia = "baja_acotada"
        else:
            tendencia = "estable"
    else:
        tendencia = "sin_datos" if not obs else "estable"

    alertas: list[str] = []
    # 1) rezago persistente: nivel actual muy por debajo de lo esperado por edad
    if edad_meses_actual is not None and nivel_actual is not None:
        esperados = marco.niveles_esperados_por_edad(edad_meses_actual)
        if esperados and nivel_actual < min(esperados) - 1:
            alertas.append(f"Nivel actual {nivel_actual} por debajo de la banda etaria esperada {esperados} (posible rezago).")
    # 2) estancamiento: 4+ observaciones sin cambio
    if len(obs) >= 4 and len({o["nivel"] for o in obs[-4:]}) == 1:
        alertas.append("Cuatro observaciones consecutivas en el mismo nivel (estancamiento).")
    # 3) poca evidencia
    if len(obs) <= 1:
        alertas.append("Evidencia insuficiente: menos de 2 observaciones registradas.")

    return Trayectoria(id_nino=id_nino, puntos=puntos, nivel_inicial=nivel_inicial,
                       nivel_actual=nivel_actual, tendencia=tendencia,
                       n_observaciones=len(obs), alertas=alertas)
