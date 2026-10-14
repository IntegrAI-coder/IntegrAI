"""Canal WhatsApp: entrada/salida del agente.

Abstrae el canal (consola MOCK / Meta Cloud API / Twilio). El mensaje entrante
trae el contexto del dataset (niño/a, educadora, jardín, sala) + los adjuntos en
cualquier formato.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .procesadores import Entrada


@dataclass
class MensajeEntrante:
    de: str                                   # teléfono / id de la educadora
    texto: str = ""
    adjuntos: list[Entrada] = field(default_factory=list)
    ts: str = ""
    id_nino: str | None = None
    id_educadora: str | None = None
    formato: str = "texto"                     # formato declarado del mensaje


class Canal:
    def responder(self, de: str, texto: str) -> None:  # pragma: no cover
        raise NotImplementedError

    def recibir(self) -> MensajeEntrante | None:  # pragma: no cover
        raise NotImplementedError


class CanalConsola(Canal):
    def __init__(self) -> None:
        self.historial: list[dict[str, str]] = []

    def responder(self, de: str, texto: str) -> None:
        self.historial.append({"de": de, "texto": texto})
        print(f"\n🤖 → Respuesta WhatsApp a {de}:\n{texto}\n")


class CanalCloudAPI(Canal):
    """Adaptador (stub) para Meta WhatsApp Cloud API.
    webhook POST /webhook -> agente -> POST graph.facebook.com/{phone_id}/messages
    """
    def __init__(self, token: str | None = None, phone_id: str | None = None) -> None:
        self.token, self.phone_id = token, phone_id

    def responder(self, de: str, texto: str) -> None:  # pragma: no cover
        raise NotImplementedError("Conectar token de Meta Cloud API.")

    def parsear_webhook(self, payload: dict[str, Any]) -> MensajeEntrante | None:  # pragma: no cover
        raise NotImplementedError("Parseo de webhook pendiente de credenciales.")


def crear_canal(nombre: str) -> Canal:
    return CanalCloudAPI() if nombre == "cloud" else CanalConsola()
