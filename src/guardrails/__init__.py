"""Guardrail preclasificador "Kiro" (seguridad de entrada, fail-closed)."""
from __future__ import annotations

from .esquema import CategoriaRiesgo, Veredicto
from .kiro import evaluar
from .prompt_kiro import SYSTEM_PROMPT

__all__ = ["evaluar", "Veredicto", "CategoriaRiesgo", "SYSTEM_PROMPT"]
