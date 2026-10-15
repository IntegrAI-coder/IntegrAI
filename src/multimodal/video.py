"""Etapa 1 · video → texto: pista de audio (Whisper) + lo visual (Pegasus 1.2, fallback Nova 2 Lite).

Antes solo se usaba el audio; pero la mitad del catálogo es motora/socioemocional y
se ve, no se escucha. Los videos de WhatsApp pesan ≤ 16 MB, así que se envían inline
(base64) sin necesidad de bucket.
"""
from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

from .. import config
from ._bedrock import cliente, converse
from .audio import transcribir
from .schema import Segmento

PROMPT_VIDEO = ("Eres una educadora de párvulos. Describe SOLO las conductas observables del niño o niña "
                "en este video, en frases cortas en presente y tercera persona, cada una precedida por el "
                "segundo aproximado entre corchetes, por ejemplo: '[3s] Se pone de pie apoyándose en una silla.' "
                "Incluye postura, desplazamiento, manipulación de objetos, mirada, gestos, vocalizaciones e "
                "interacción con otros. No nombres a nadie, no describas rasgos físicos ni ropa, no estimes edad ni nivel.")

MAX_INLINE = 25 * 1024 * 1024


def _pegasus(path: str) -> str:
    body = {"inputPrompt": PROMPT_VIDEO, "temperature": 0,
            "mediaSource": {"base64String": base64.b64encode(Path(path).read_bytes()).decode()}}
    r = cliente().invoke_model(modelId=config.MODELO_VIDEO, body=json.dumps(body))
    return json.loads(r["body"].read())["message"]


def _nova(path: str) -> str:
    fmt = Path(path).suffix.lstrip(".").lower() or "mp4"
    contenido = [{"video": {"format": fmt if fmt in ("mp4", "mov", "webm", "mkv") else "mp4",
                            "source": {"bytes": Path(path).read_bytes()}}},
                 {"text": PROMPT_VIDEO}]
    return converse(config.MODELO_VIDEO_FALLBACK, contenido, max_tokens=700)["texto"]


def describir_video(path: str) -> Segmento:
    adv: list[str] = []
    for nombre, fn, modelo in (("pegasus", _pegasus, config.MODELO_VIDEO),
                               ("nova", _nova, config.MODELO_VIDEO_FALLBACK)):
        try:
            texto = fn(path).strip()
            if texto:
                return Segmento(fuente="video_visual", texto=texto, calidad=0.8, modelo=modelo,
                                advertencias=adv + ["descripción visual generada por modelo: revisar"])
        except Exception:  # noqa: BLE001
            logging.getLogger(__name__).exception("descripción de video con %s falló", nombre)
            adv.append("descripción visual no disponible")
    return Segmento(fuente="video_visual", texto="", calidad=0.0, advertencias=adv or ["sin descripción visual"])


def procesar_video(path: str) -> list[Segmento]:
    if not path or not Path(path).exists():
        return [Segmento(fuente="video_visual", texto="", calidad=0.0, advertencias=["video no encontrado"])]
    if Path(path).stat().st_size > MAX_INLINE:
        return [transcribir(path, fuente="video_audio"),
                Segmento(fuente="video_visual", texto="", calidad=0.0,
                         advertencias=["video > 25 MB: solo se procesó el audio"])]
    return [transcribir(path, fuente="video_audio"), describir_video(path)]
