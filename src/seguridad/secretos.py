"""Escáner de secretos para CUALQUIER salida del sistema (respuesta a la tía, BD, logs, reportes).

Si un modelo llegara a "obedecer" un post-it que pide las keys, esto lo detecta antes de que salga.
Además de patrones conocidos, compara contra los valores reales de los secretos del entorno.
"""
from __future__ import annotations

import os
import re

_PATRONES = [
    ("aws_access_key", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("aws_secret", re.compile(r"(?i)aws_secret_access_key\s*[:=]")),
    ("aws_session", re.compile(r"(?i)aws_session_token\s*[:=]|IQoJb3JpZ2lu")),
    ("meta_token", re.compile(r"\bEAA[A-Za-z0-9]{30,}\b")),
    ("clave_privada", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("anthropic_openai", re.compile(r"\bsk-(ant-)?[A-Za-z0-9_-]{20,}\b")),
]
_VARIABLES = ("INTEGRA_API_TOKEN", "WA_APP_SECRET", "WA_TOKEN", "WA_VERIFY_TOKEN", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN")


def escanear(texto: str) -> list[str]:
    """Tipos de secreto encontrados en el texto (vacío = limpio)."""
    texto = texto or ""
    hallados = [n for n, p in _PATRONES if p.search(texto)]
    for var in _VARIABLES:
        valor = os.getenv(var, "")
        if len(valor) >= 12 and valor in texto:
            hallados.append(f"valor_de_{var}")
    return hallados
