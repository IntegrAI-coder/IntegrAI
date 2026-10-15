"""Procesadores de formatos -> texto (esto es lo que hoy hace la tía a mano).

- texto : directo.
- audio : transcripción con Whisper (faster-whisper, CPU). Fallback: texto provisto.
- imagen: descripción con visión de Bedrock (Nova). Fallback: pie de foto.
- video : audio -> Whisper + (opcional) frame -> visión. Fallback: texto provisto.

Devuelve un texto unificado (nota + transcripciones + descripciones) listo para
el matcher, más el detalle por formato.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import config


@dataclass
class Entrada:
    tipo: str            # texto | audio | imagen | video
    ref: str = ""        # ruta o id
    pie: str = ""        # nota de la educadora
    texto_extraido: str = ""  # transcripción/descripción (provista o calculada)


def _whisper() -> Any | None:
    try:
        from faster_whisper import WhisperModel
        return WhisperModel("small", device="cpu", compute_type="int8")
    except Exception:
        return None


_MODELO_WHISPER = None


def _decode_audio_np(path: str):
    """Decodifica audio a float32 16k mono con ffmpeg (evita la incompatibilidad av/faster_whisper)."""
    import subprocess, tempfile, wave
    import numpy as np
    wav = tempfile.mktemp(suffix=".wav")
    try:
        r = subprocess.run(["ffmpeg", "-y", "-i", path, "-ac", "1", "-ar", "16000", "-f", "wav", wav],
                           capture_output=True, timeout=300)
        if not Path(wav).exists() or Path(wav).stat().st_size < 100:
            print(f"[whisper] ffmpeg fallo: {r.stderr[-300:]!r}", flush=True)
            return None
        with wave.open(wav, "rb") as w:
            frames = w.readframes(w.getnframes())
        return np.frombuffer(frames, dtype=np.int16).astype("float32") / 32768.0
    finally:
        Path(wav).unlink(missing_ok=True)


def transcribir_audio(path: str) -> str:
    global _MODELO_WHISPER
    if not path or not Path(path).exists():
        return ""
    if _MODELO_WHISPER is None:
        _MODELO_WHISPER = _whisper()
    if _MODELO_WHISPER is None:
        print("[whisper] modelo no disponible", flush=True)
        return ""
    audio = _decode_audio_np(path)
    if audio is None or audio.size == 0:
        return ""
    try:
        segs, _ = _MODELO_WHISPER.transcribe(audio, language="es", vad_filter=True)
        return " ".join(s.text.strip() for s in segs).strip()
    except Exception as e:  # noqa: BLE001
        print(f"[whisper] error: {e!r}", flush=True)
        return ""


def extraer_audio_video(path: str) -> str:
    """Extrae la pista de audio de un video con ffmpeg y la transcribe."""
    import subprocess, tempfile
    if not path or not Path(path).exists():
        return ""
    out = tempfile.mktemp(suffix=".wav")
    try:
        subprocess.run(["ffmpeg", "-y", "-i", path, "-ac", "1", "-ar", "16000", out],
                       capture_output=True, timeout=180)
        return transcribir_audio(out)
    except Exception:
        return ""
    finally:
        Path(out).unlink(missing_ok=True)


def describir_imagen(path: str, pie: str = "") -> str:
    """Visión con Bedrock (Nova). Si no hay, devuelve el pie."""
    if config.usar_mock() or not path or not Path(path).exists():
        return ""
    try:
        import boto3, base64, json
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        fmt = Path(path).suffix.lstrip(".").lower() or "jpeg"
        cliente = boto3.client("bedrock-runtime", region_name=config.AWS_REGION)
        prompt = ("Describe en español qué aprendizajes de un niño/a de educación parvularia "
                  f"se observan en esta imagen, en 2-3 frases. Contexto de la educadora: {pie}")
        r = cliente.converse(modelId=config.MODELO_VISION, messages=[{"role": "user", "content": [
            {"image": {"format": fmt if fmt in ("jpeg","png","gif","webp") else "jpeg", "source": {"bytes": base64.b64decode(b64)}}},
            {"text": prompt}]}], inferenceConfig={"maxTokens": 300})
        return r["output"]["message"]["content"][0]["text"]
    except Exception:
        return ""


class Procesador:
    def procesar(self, entradas: list[Entrada]) -> tuple[str, list[dict[str, Any]]]:
        if config.U2_PIPELINE == "v2" and not config.usar_mock():
            return self._procesar_v2(entradas)
        partes, detalle = [], []
        for e in entradas:
            t = (e.tipo or "").lower()
            texto = ""
            if t in ("texto", "nota"):
                texto = e.pie or e.texto_extraido
            elif t in ("audio",):
                texto = transcribir_audio(e.ref) or e.texto_extraido or e.pie
            elif t in ("imagen", "foto"):
                desc = describir_imagen(e.ref, e.pie) if e.ref else ""
                texto = (e.pie + " " + desc).strip() or e.texto_extraido
            elif t in ("video",):
                texto = extraer_audio_video(e.ref) or e.texto_extraido or e.pie
            else:
                texto = e.pie or e.texto_extraido
            texto = (texto or "").strip()
            if texto:
                partes.append(texto)
                detalle.append({"tipo": t, "ref": e.ref, "texto": texto})
        return " ".join(partes).strip(), detalle

    def _procesar_v2(self, entradas: list[Entrada]) -> tuple[str, list[dict[str, Any]]]:
        """U2 v2 (src/multimodal): misma firma; `detalle` incluye la ObservacionNormalizada."""
        from .multimodal import normalizar_entradas
        obs = normalizar_entradas(entradas)
        detalle = [{"tipo": s.fuente, "texto": s.texto, "calidad": s.calidad, "modelo": s.modelo,
                    "advertencias": s.advertencias} for s in obs.segmentos]
        # nino_mencionado (nombre/apodo) solo sirve para resolver el ID: no se expone ni se guarda
        detalle.append({"tipo": "observacion_normalizada", **obs.model_dump(exclude={"segmentos", "nino_mencionado"}),
                        "nino_identificado": obs.nino_mencionado is not None})
        return obs.texto_para_matcher(), detalle
