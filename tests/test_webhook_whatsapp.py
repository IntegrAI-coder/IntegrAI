"""Tests del receptor webhook/server.py: firma fail-closed, whitelist y logs sin PII."""
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path

import pytest

RUTA = Path(__file__).resolve().parent.parent / "webhook" / "server.py"


def cargar(monkeypatch, **env):
    for k in ("WA_APP_SECRET", "WA_ALLOW_UNSIGNED", "WA_WHITELIST", "WA_VERIFY_TOKEN", "INTEGRA_BACKEND"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    spec = importlib.util.spec_from_file_location("wa_server", RUTA)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def firmar(secreto: str, cuerpo: bytes) -> str:
    return "sha256=" + hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()


def test_sin_secreto_rechaza(monkeypatch):
    s = cargar(monkeypatch)
    assert not s.firma_valida(b"{}", None)                       # fail-closed
    s = cargar(monkeypatch, WA_ALLOW_UNSIGNED="1")
    assert s.firma_valida(b"{}", None)                           # solo con opt-in explícito


def test_firma(monkeypatch):
    s = cargar(monkeypatch, WA_APP_SECRET="x1")
    assert s.firma_valida(b"{}", firmar("x1", b"{}"))
    assert not s.firma_valida(b"{}", firmar("otro", b"{}"))
    assert not s.firma_valida(b"{} ", firmar("x1", b"{}"))


def test_whitelist_y_mascara(monkeypatch):
    s = cargar(monkeypatch, WA_WHITELIST="+56 9 1111 2222, 56933334444")
    assert s.autorizado("56911112222") and s.autorizado("56933334444")
    assert not s.autorizado("56900000000")
    assert s.mask("56911112222") == "569*****222"
    assert not cargar(monkeypatch).autorizado("56911112222")      # whitelist vacía = nadie


def test_remitente_desconocido_no_se_procesa(monkeypatch, capsys):
    import asyncio
    s = cargar(monkeypatch, WA_APP_SECRET="x1", WA_WHITELIST="56911112222")
    llamado = []
    s.procesar_texto = lambda de, t: llamado.append(de) or "ok"
    async def no_enviar(de, t): llamado.append(("envio", de))
    s.enviar_texto = no_enviar
    cuerpo = {"entry": [{"changes": [{"value": {"messages": [
        {"id": "m1", "from": "56900000000", "type": "text", "text": {"body": "la Martina gateó"}},
        {"id": "m2", "from": "56911112222", "type": "text", "text": {"body": "la Martina gateó"}}]}}]}]}
    asyncio.run(s.procesar(json.dumps(cuerpo).encode(), "x", ""))
    assert llamado == ["56911112222", ("envio", "56911112222")]
    salida = capsys.readouterr().out
    assert "Martina" not in salida and "56900000000" not in salida   # sin PII en logs
