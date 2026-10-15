"""Guardrail preclasificador "Kiro".

Flujo:
    texto
      -> prefiltrar()            (Tier 0 determinista, ≈ costo cero)
      -> modelo (Bedrock)        (Tier 1, prompt estricto -> JSON)
      -> Veredicto               (tipado; fail-closed ante cualquier fallo)

Se ejecuta ANTES del clasificador pedagógico (src/clasificador.py). Es una
barrera de entrada: si el veredicto trae permitido=False, el texto no debe
llegar al clasificador.
"""
from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from ..bedrock import GatewayModelos
from . import patrones
from .esquema import Veredicto
from .prompt_kiro import SYSTEM_PROMPT


def _bloqueo(categoria: str, razon: str, confianza: float = 0.0) -> Veredicto:
    return Veredicto(
        permitido=False,
        categoria_riesgo=categoria,  # type: ignore[arg-type]
        confianza=confianza,
        razon=razon,
    )


def _extraer_json(salida: str) -> dict[str, Any] | None:
    """Acepta JSON puro o envuelto en ```json ... ```; devuelve None si no hay."""
    t = (salida or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    ini, fin = t.find("{"), t.rfind("}")
    if ini == -1 or fin < ini:
        return None
    try:
        datos = json.loads(t[ini : fin + 1])
    except json.JSONDecodeError:
        return None
    return datos if isinstance(datos, dict) else None


def _interpretar(salida: str) -> Veredicto:
    datos = _extraer_json(salida)
    if datos is None:
        return _bloqueo("INDETERMINADO", "Fail-closed: el modelo no devolvió JSON válido.")
    try:
        return Veredicto.model_validate(datos)
    except ValidationError as e:
        return _bloqueo("INDETERMINADO", f"Fail-closed: veredicto fuera de esquema ({e.error_count()} errores).")


def evaluar(texto: str, gateway: Any | None = None) -> Veredicto:
    """Evalúa un texto y devuelve el Veredicto. `gateway` es inyectable (tests)."""
    texto = (texto or "").strip()
    if not texto:
        return _bloqueo("INDETERMINADO", "Fail-closed: texto vacío.")

    determinista = patrones.prefiltrar(texto)
    if determinista is not None:
        return determinista

    if gateway is None:
        gateway = GatewayModelos()
        # Sin Bedrock (MOCK): no hay Tier 1. Operamos solo con la capa determinista
        # para no bloquear todo el flujo de demo offline.
        if getattr(gateway, "mock", True):
            return Veredicto(
                permitido=True,
                categoria_riesgo="NINGUNA",
                confianza=0.3,
                razon="MODO MOCK (sin Bedrock): aprobado solo por la capa determinista.",
            )

    try:
        respuesta = gateway.generar(texto, tarea="simple", system=SYSTEM_PROMPT)
    except Exception as e:  # noqa: BLE001
        return _bloqueo("INDETERMINADO", f"Fail-closed: error al invocar el modelo ({type(e).__name__}).")

    return _interpretar(getattr(respuesta, "texto", "") or "")
