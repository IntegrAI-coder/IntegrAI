"""Capa determinista del guardrail (Tier 0): regex baratas y explicables.

Atrapa los casos evidentes SIN llamar al modelo (≈ costo cero) y actúa como red
de seguridad si Bedrock no está disponible. Si no hay coincidencia, devuelve
None y se delega al modelo (Tier 1).

Importante (excepción pedagógica): los patrones de violencia NO incluyen
conductas cotidianas de sala ("lloró", "mordió", "empujó", "se cayó",
"berrinche", "rabia", "pataleta"). Solo armas, odio/abuso real y amenazas
explícitas de muerte.
"""
from __future__ import annotations

import re

from .esquema import Veredicto

_INYECCION = [
    r"\bolvida\s+(tus|las|todas\s+las)\s+(reglas|instrucciones|indicaciones)",
    r"\bignora\s+(las\s+|todas\s+las\s+)?(instrucciones|reglas|indicaciones|restricciones)",
    r"\bact[úu]a\s+como\b",
    r"\b(imprime|revela|muestra|dame|repite|filtra)\s+el\s+(prompt|system\s*prompt|mensaje\s+de\s+sistema|system)",
    r"\b(system\s*prompt|prompt\s+del\s+sistema|prompt\s+de\s+sistema)\b",
    r"\baccede\s+a\s+(la\s+)?(base\s+de\s+datos|bd|db|archivos)",
    r"\b(drop\s+table|delete\s+from|select\s+\*?\s*from|or\s+1\s*=\s*1)\b",
    r"\bjailbreak\b",
    r"\bdo\s+anything\s+now\b|\bDAN\s*(mode|modo)?\b",
    r"\b(sos|eres|ahora\s+sos)\s+(un|una)\s+(asistente|modelo|IA)\s+sin\b",
    r"\bsimula\s+(ser|un|una)\b",
]

_VIOLENCIA = [
    r"\b(armas?|pistolas?|rev[óo]lver(es)?|cuchillos?|navajas?|machetes?|rifles?|disparos?|balas?)\b",
    r"\b(amenazas?\s+de\s+muerte|te\s+voy\s+a\s+matar|voy\s+a\s+matar(te|lo|la)?)\b",
    r"\b(abuso\s+sexual|violaci[óo]n|violar)\b",
    r"\b(odio\s+(racial|a\s+los|a\s+las)|muerte\s+a\s+los)\b",
]

_PII = [
    r"\b\d{1,2}\.?\d{3}\.?\d{3}-[\dkK]\b",           # RUN chileno con/sin puntos
    r"\b(?:\d{4}[ -]?){3}\d{4}\b",                    # tarjeta de crédito
    r"\b(?:cuenta[\s-]?(?:rut|corriente|vista)|cvv|c[óo]digo\s+de\s+tarjeta)\b",
    r"\b(?:direcci[óo]n\s+(?:exacta\s+)?(?:es\s+)?)[A-ZÁÉÍÓÚÑ][\wáéíóúñ]+\s+\d{2,}\b",
]

_COMPILADOS = [
    ("PROMPT_INJECTION", 0.99, re.compile("|".join(_INYECCION), re.IGNORECASE)),
    ("VIOLENCIA_EXTREMA", 0.95, re.compile("|".join(_VIOLENCIA), re.IGNORECASE)),
    ("PII_REAL", 0.98, re.compile("|".join(_PII), re.IGNORECASE)),
]


def prefiltrar(texto: str) -> Veredicto | None:
    """Devuelve un Veredicto de bloqueo si hay coincidencia; si no, None."""
    for categoria, confianza, patron in _COMPILADOS:
        if patron.search(texto):
            return Veredicto(
                permitido=False,
                categoria_riesgo=categoria,  # type: ignore[arg-type]
                confianza=confianza,
                razon=f"Regla determinista: se detectó {categoria}.",
            )
    return None
