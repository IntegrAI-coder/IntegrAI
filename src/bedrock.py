"""Gateway de modelos (Amazon Bedrock) con degradación a MOCK.

Cumple el rol de "gateway multi-modelo" del diseño: enruta por tarea
(simple -> Nova Lite, razonamiento -> Nova Pro, visión -> Nova Pro) y expone
una sola interfaz. Sin credenciales, responde con plantillas deterministas
para que el flujo end-to-end sea demostrable igual.

El harness propio (agente + decision model + plataforma) vive ENCIMA de esta
capa: Bedrock aporta el músculo de lenguaje/visión, no la lógica del negocio.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import config


@dataclass
class RespuestaModelo:
    texto: str
    modelo: str
    tarea: str
    mock: bool


class GatewayModelos:
    def __init__(self) -> None:
        self.mock = config.usar_mock()
        self._cliente = None
        if not self.mock:
            try:
                import boto3  # type: ignore

                self._cliente = boto3.client("bedrock-runtime", region_name=config.AWS_REGION)
            except Exception:
                self.mock = True

    @property
    def disponible(self) -> bool:
        return not self.mock and self._cliente is not None

    def modelo_para(self, tarea: str) -> str:
        return {
            "simple": config.MODELO_SIMPLE,
            "razonamiento": config.MODELO_RAZONAMIENTO,
            "vision": config.MODELO_VISION,
        }.get(tarea, config.MODELO_SIMPLE)

    # ------------------------------------------------------------------
    def generar(self, prompt: str, tarea: str = "simple", system: str | None = None) -> RespuestaModelo:
        modelo = self.modelo_para(tarea)
        if self.disponible:
            try:
                texto = self._converse(prompt, modelo, system)
                return RespuestaModelo(texto, modelo, tarea, mock=False)
            except Exception as e:  # noqa: BLE001
                texto = f"[Bedrock falló ({e}); respuesta MOCK]\n" + self._mock(prompt, tarea)
                return RespuestaModelo(texto, modelo, tarea, mock=True)
        return RespuestaModelo(self._mock(prompt, tarea), modelo, tarea, mock=True)

    def _converse(self, prompt: str, modelo: str, system: str | None) -> str:
        mensajes = [{"role": "user", "content": [{"text": prompt}]}]
        kwargs: dict[str, Any] = {"modelId": modelo, "messages": mensajes,
                                  "inferenceConfig": {"maxTokens": 1024, "temperature": 0.2}}
        if system:
            kwargs["system"] = [{"text": system}]
        r = self._cliente.converse(**kwargs)
        return r["output"]["message"]["content"][0]["text"]

    def _mock(self, prompt: str, tarea: str) -> str:
        return (
            f"(MOCK · tarea={tarea}) No hay credenciales de Bedrock configuradas. "
            "Esta es una respuesta plantilla; con AWS el texto lo redacta el modelo real."
        )
