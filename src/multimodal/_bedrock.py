"""Helpers mínimos de Bedrock para U2 (converse con texto/imagen/video y tool forzada)."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from .. import config


@lru_cache(maxsize=1)
def cliente():
    import boto3
    return boto3.client("bedrock-runtime", region_name=config.AWS_REGION)


def _inference(modelo: str, max_tokens: int) -> dict[str, Any]:
    cfg: dict[str, Any] = {"maxTokens": max_tokens}
    # Claude Sonnet 5+ rechaza `temperature`; los demás usan 0 para ser deterministas.
    if "claude-sonnet-5" not in modelo and "claude-opus-5" not in modelo:
        cfg["temperature"] = 0
    return cfg


def converse(modelo: str, contenido: list[dict], system: str | None = None,
             max_tokens: int = 800, tool: dict | None = None) -> dict[str, Any]:
    """Devuelve {"texto": str} o, si se pasa `tool`, {"input": dict} de la tool forzada."""
    kw: dict[str, Any] = {"modelId": modelo, "messages": [{"role": "user", "content": contenido}],
                          "inferenceConfig": _inference(modelo, max_tokens)}
    if system:
        kw["system"] = [{"text": system}]
    if tool:
        kw["toolConfig"] = {"tools": [{"toolSpec": tool}],
                            "toolChoice": {"tool": {"name": tool["name"]}}}
    r = cliente().converse(**kw)
    bloques = r["output"]["message"]["content"]
    if tool:
        for b in bloques:
            if "toolUse" in b:
                return {"input": b["toolUse"]["input"], "usage": r.get("usage")}
        raise ValueError("el modelo no llamó a la tool")
    return {"texto": "".join(b.get("text", "") for b in bloques).strip(), "usage": r.get("usage")}


def _desanidar(valor):
    """Los modelos a veces devuelven un campo lista/objeto como STRING con JSON adentro: se decodifica."""
    import json
    if isinstance(valor, dict):
        return {k: _desanidar(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_desanidar(v) for v in valor]
    if isinstance(valor, str) and valor[:1] in "[{":
        try:
            dec = json.loads(valor)
            if isinstance(dec, dict) and len(dec) == 1 and isinstance(next(iter(dec.values())), list):
                dec = next(iter(dec.values()))          # {"conductas": [...]} dentro de "conductas"
            return _desanidar(dec)
        except ValueError:
            return valor
    return valor


def converse_tipado(modelo: str, contenido: list[dict], schema, system: str | None = None,
                    max_tokens: int = 1200, intentos: int = 3, nombre_tool: str = "registrar"):
    """Salida estructurada TYPESAFE: tool forzada con el JSON Schema de Pydantic + validación.

    Si la validación falla, se reintenta mostrándole al modelo el error exacto de Pydantic para que
    corrija (no se afloja el esquema). Lanza ValidationError si tras `intentos` sigue inválida.
    """
    from pydantic import ValidationError
    tool = {"name": nombre_tool, "description": "Registra la respuesta con el formato exacto pedido.",
            "inputSchema": {"json": schema.model_json_schema()}}
    mensaje = list(contenido)
    error = None
    for _ in range(intentos):
        r = converse(modelo, mensaje, system=system, tool=tool, max_tokens=max_tokens)
        try:
            return schema.model_validate(_desanidar(r["input"]))
        except ValidationError as e:
            error = e
            mensaje = list(contenido) + [{"text": (
                "\n\nTu respuesta anterior NO cumplió el esquema y fue rechazada. Error de validación:\n"
                f"{str(e)[:800]}\nVuelve a responder cumpliendo el esquema exactamente "
                "(listas como listas JSON, no como texto; respeta los largos máximos).")}]
    raise error


def formato_imagen(nombre: str) -> str:
    ext = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else "jpeg"
    return {"jpg": "jpeg"}.get(ext, ext if ext in ("jpeg", "png", "gif", "webp") else "jpeg")
