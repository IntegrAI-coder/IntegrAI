"""Etapa 1 · audio → texto con faster-whisper (CPU, EC2).

- Modelo configurable (`WHISPER_MODEL`, por defecto large-v3-turbo int8). FLEURS-es WER ≈ 3 %
  para large-v3 vs. bastante peor para `small` (línea base anterior).
- `initial_prompt` con vocabulario parvulario para sesgar la decodificación.
- Calidad 0–1 a partir de avg_logprob y no_speech_prob de los segmentos.
- faster-whisper decodifica con PyAV: acepta OGG/Opus de WhatsApp y la pista de audio
  de un MP4 sin ffmpeg externo.
"""
from __future__ import annotations

import logging
import math
from pathlib import Path

from .. import config
from .schema import Fuente, Segmento

PROMPT_VOCAB = ("Observación de una educadora de párvulos en Chile. Sala cuna, nivel medio, transición, "
                "la tía, el niño, la niña, gatea, balbucea, apila bloques, hace pinza, "
                "se para con apoyo, camina, señala, nombra, imita, juega, comparte, "
                "colación, babero, siesta, asamblea, espera su turno, se despide, "
                "dijo «mío», «lo logré», «mira lo que hice», sin recordatorio, solito.")

log = logging.getLogger(__name__)
_modelos: dict[str, object] = {}


def _modelo(nombre: str):
    if nombre not in _modelos:
        from faster_whisper import WhisperModel
        _modelos[nombre] = WhisperModel(nombre, device="cpu", compute_type="int8")
    return _modelos[nombre]


def _ffmpeg() -> str:
    import shutil
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg  # respaldo en máquinas sin ffmpeg instalado
    return imageio_ffmpeg.get_ffmpeg_exe()


def _decodificar_ffmpeg(path: str):
    """Audio de cualquier contenedor → float32 16 kHz mono (lo que espera Whisper)."""
    import subprocess
    import numpy as np
    r = subprocess.run([_ffmpeg(), "-nostdin", "-loglevel", "error", "-i", path, "-ac", "1", "-ar", "16000",
                        "-f", "s16le", "-"], capture_output=True, check=True, timeout=180)
    return np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768.0


def transcribir(path: str, fuente: Fuente = "audio", modelo: str | None = None,
                con_prompt: bool = True) -> Segmento:
    nombre = modelo or config.WHISPER_MODEL
    if not path or not Path(path).exists():
        return Segmento(fuente=fuente, texto="", calidad=0.0, advertencias=["audio no encontrado"], modelo=nombre)
    try:
        modelo_w = _modelo(nombre)
        kw = dict(language="es", vad_filter=True, beam_size=5, initial_prompt=PROMPT_VOCAB if con_prompt else None)
        try:
            segs = list(modelo_w.transcribe(path, **kw)[0])
        except TypeError:
            # PyAV ≥ 15 rompe la decodificación interna de faster-whisper (open(... metadata_errors=)):
            # se decodifica con ffmpeg a PCM 16 kHz mono y se transcribe el arreglo (sirve para ogg, mp3 y mp4).
            segs = list(modelo_w.transcribe(_decodificar_ffmpeg(path), **kw)[0])
    except Exception:  # noqa: BLE001
        log.exception("whisper falló")
        return Segmento(fuente=fuente, texto="", calidad=0.0, advertencias=["no se pudo transcribir el audio"], modelo=nombre)
    texto = " ".join(s.text.strip() for s in segs).strip()
    adv: list[str] = []
    if not segs or not texto:
        return Segmento(fuente=fuente, texto="", calidad=0.0, advertencias=["sin voz detectada"], modelo=nombre)
    # avg_logprob ~ -0.2 (muy seguro) .. -1.0 (dudoso); se pondera por duración.
    dur = sum(max(s.end - s.start, 0.01) for s in segs)
    lp = sum(s.avg_logprob * max(s.end - s.start, 0.01) for s in segs) / dur
    ns = max(s.no_speech_prob for s in segs)
    calidad = max(0.0, min(1.0, math.exp(lp))) * (1 - 0.5 * ns)
    if calidad < 0.5:
        adv.append("audio con baja confianza de transcripción (ruido o habla poco clara)")
    return Segmento(fuente=fuente, texto=texto, calidad=round(calidad, 3), advertencias=adv,
                    modelo=f"faster-whisper:{nombre}")
