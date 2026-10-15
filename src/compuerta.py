"""Compuerta de revisión humana: decide si una propuesta pasa directo o va a la tía.

Problema medido (docs/EVAL_ENSEMBLE.md §5): con solo `margen < 0.15`, el prior de edad le da
confianza alta a respuestas equivocadas justo cuando el niño/a no calza con su edad (rezago o
adelanto). La compuerta propuesta agrega una regla de DISCREPANCIA texto-vs-edad:

    revisar  si  margen < umbral_margen
            o   |nivel_solo_texto - nivel_tipico_edad| >= umbral_discrepancia

`nivel_solo_texto` es la predicción del mismo clasificador SIN edad (una segunda llamada barata).
Si el texto sugiere un nivel lejos de lo típico para la edad, la evidencia es la que importa y
la decisión no debe salir automática: es exactamente el caso de posible rezago.

Calibración (bench/reporte_compuerta.md, 90 casos): con la nota pasada a conductas (U2), la compuerta
de margen sola ya baja los rezagos que se escapan de 16/40 a 6/40. La discrepancia ≥ 2 solo los baja
a 5/40 y sube la revisión de 10 % a 13 % (casos al azar) y de 27 % a 50 % (casos contra la edad).
Por eso viene DESACTIVADA (umbral_discrepancia=None); activarla solo si Integra prefiere más
revisión a cambio de menos rezagos sin ver.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Compuerta:
    umbral_margen: float = 0.15
    umbral_discrepancia: int | None = None

    def revisar(self, margen: float, nivel_solo_texto: int | None, nivel_tipico_edad: int | None) -> tuple[bool, str]:
        """Devuelve (requiere_revision, motivo)."""
        if margen < self.umbral_margen:
            return True, f"margen bajo ({margen:.2f} < {self.umbral_margen})"
        if self.umbral_discrepancia is not None and nivel_solo_texto is not None and nivel_tipico_edad is not None:
            d = abs(nivel_solo_texto - nivel_tipico_edad)
            if d >= self.umbral_discrepancia:
                sentido = "bajo" if nivel_solo_texto < nivel_tipico_edad else "sobre"
                return True, f"la observación sugiere {d} niveles {sentido} lo típico para su edad"
        return False, "aceptado"
