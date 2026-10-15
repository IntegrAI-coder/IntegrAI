"""Contrato de salida del guardrail "Kiro" (JSON estricto, tipado con Pydantic)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Categorías del prompt. "INDETERMINADO" es interno: solo se usa para fail-closed
# cuando el guardrail no pudo evaluar (modelo caído, JSON inválido, texto vacío).
CategoriaRiesgo = Literal[
    "NINGUNA",
    "PROMPT_INJECTION",
    "VIOLENCIA_EXTREMA",
    "PII_REAL",
    "INDETERMINADO",
]


class Veredicto(BaseModel):
    """Resultado del guardrail. Única estructura que cruza hacia el clasificador."""

    permitido: bool
    categoria_riesgo: CategoriaRiesgo
    confianza: float = Field(ge=0.0, le=1.0)
    razon: str

    def to_dict(self) -> dict:
        return self.model_dump()

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)
