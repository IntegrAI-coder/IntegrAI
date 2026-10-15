"""Redacción de datos personales en la transcripción, ANTES del LLM y de guardar.

Una educadora puede escribir (o fotografiar un post-it con) un RUT, un teléfono o un correo.
Nada de eso es una conducta observable y no debe viajar al modelo ni quedar en la BD
(Ley 21.719: minimización; Ley 21.430: datos de niños/as).
"""
from __future__ import annotations

import re

_PATRONES = [
    ("rut", re.compile(r"\b\d{1,2}\.?\d{3}\.?\d{3}\s*-\s*[\dkK]\b")),
    ("correo", re.compile(r"\b[\w.+-]+@[\w-]+(\.[\w-]+)+\b")),
    ("url", re.compile(r"\b(?:https?://|www\.)\S+", re.I)),
    ("telefono", re.compile(r"(?<!\d)(?:\+?56[\s-]?)?9[\s-]?\d{4}[\s-]?\d{4}(?!\d)")),
]


def redactar(texto: str) -> tuple[str, list[str]]:
    """Devuelve (texto redactado, tipos encontrados). Ej: '12.345.678-9' -> '[RUT]'."""
    encontrados: list[str] = []
    for tipo, patron in _PATRONES:
        texto, n = patron.subn(f"[{tipo.upper()}]", texto)
        if n:
            encontrados.append(tipo)
    return texto, encontrados
