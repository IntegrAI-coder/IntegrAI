"""Seguridad del webhook de WhatsApp Cloud API.

- verificar_firma: Meta firma cada POST con HMAC-SHA256 del cuerpo CRUDO usando el App Secret,
  en la cabecera `X-Hub-Signature-256: sha256=<hex>`. Sin esto, cualquiera puede inyectar
  mensajes falsos (Ley 21.459: la barrera técnica tiene que existir).
- telefono_autorizado: solo se procesan mensajes de educadoras registradas (whitelist).
  Un número desconocido se descarta sin responder y sin descargar sus medios.
- enmascarar: los teléfonos nunca se registran completos en logs.

Uso en FastAPI:
    raw = await request.body()
    if not verificar_firma(raw, request.headers.get("X-Hub-Signature-256"), secreto_app):
        raise HTTPException(401)
"""
from __future__ import annotations

import hashlib
import hmac
import re


def verificar_firma(cuerpo: bytes, cabecera: str | None, secreto_app: str) -> bool:
    """True solo si la cabecera es `sha256=<hex>` y coincide en tiempo constante."""
    if not cabecera or not secreto_app or not cabecera.startswith("sha256="):
        return False
    esperado = hmac.new(secreto_app.encode(), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, cabecera[len("sha256="):].strip().lower())


def normalizar_telefono(tel: str | None) -> str:
    """Solo dígitos, sin '+' (WhatsApp entrega 'from' así: 56912345678)."""
    return re.sub(r"\D", "", tel or "")


def telefono_autorizado(tel: str | None, whitelist: set[str] | frozenset[str]) -> bool:
    t = normalizar_telefono(tel)
    return bool(t) and t in {normalizar_telefono(w) for w in whitelist}


def enmascarar(tel: str | None) -> str:
    """'56912345678' -> '569*****678' (para logs)."""
    t = normalizar_telefono(tel)
    if len(t) <= 6:
        return "*" * len(t)
    return t[:3] + "*" * (len(t) - 6) + t[-3:]
