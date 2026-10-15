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


def formato_imagen(nombre: str) -> str:
    ext = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else "jpeg"
    return {"jpg": "jpeg"}.get(ext, ext if ext in ("jpeg", "png", "gif", "webp") else "jpeg")
