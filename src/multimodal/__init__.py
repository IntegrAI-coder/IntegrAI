"""U2 · Ingesta multimodal: texto, post-it, foto, audio y video → ObservacionNormalizada.

Puente de texto en dos etapas:
  1. transcripción fiel por modalidad (audio.py, imagen.py, video.py)
  2. normalización conductual con citas verificadas (conductas.py)
El resultado alimenta Matcher.matchear() vía ObservacionNormalizada.texto_para_matcher().
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from .schema import Conducta, ObservacionNormalizada, Segmento

log = logging.getLogger(__name__)
_CATEGORIA = {"audio": "audio", "imagen": "imagen", "foto": "imagen", "video": "video"}


def _medio_seguro(tipo: str, ref: str) -> tuple[str | None, str | None]:
    """(ruta validada, None) o (None, advertencia segura para el usuario)."""
    from ..seguridad.archivos import MedioInvalido, ruta_segura, validar_medio
    try:
        p = ruta_segura(ref)
        validar_medio(p, _CATEGORIA[tipo])
        return str(p), None
    except MedioInvalido as e:
        log.warning("medio rechazado (%s): %s", tipo, e)
        return None, str(e)

__all__ = ["normalizar_entradas", "ObservacionNormalizada", "Conducta", "Segmento"]


def _etapa1(tipo: str, ref: str, pie: str, texto_extraido: str) -> list[Segmento]:
    t = (tipo or "").lower()
    if t in _CATEGORIA and ref:
        ref, adv = _medio_seguro(t, ref)
        if adv:
            segs = [Segmento(fuente="texto", texto=pie, modelo="directo")] if pie else []
            return segs + [Segmento(fuente="texto", texto="", calidad=0.0, advertencias=[adv])]
    if t in ("texto", "nota"):
        txt = pie or texto_extraido
        return [Segmento(fuente="texto", texto=txt, modelo="directo")] if txt else []
    if t == "audio":
        from .audio import transcribir
        seg = transcribir(ref)
        if not seg.texto and texto_extraido:
            seg = Segmento(fuente="audio", texto=texto_extraido, calidad=0.5, advertencias=["transcripción provista"])
        return [seg]
    if t in ("imagen", "foto"):
        from .imagen import procesar_imagen
        segs = [procesar_imagen(ref)] if ref else []
        if pie:
            segs.insert(0, Segmento(fuente="texto", texto=pie, modelo="directo"))
        return segs
    if t == "video":
        from .video import procesar_video
        segs = procesar_video(ref) if ref else []
        if pie:
            segs.insert(0, Segmento(fuente="texto", texto=pie, modelo="directo"))
        return segs
    txt = pie or texto_extraido
    return [Segmento(fuente="texto", texto=txt, modelo="directo")] if txt else []


def normalizar_entradas(entradas, etapa2: bool = True, guia=None) -> ObservacionNormalizada:
    """entradas: iterable con atributos tipo, ref, pie, texto_extraido (procesadores.Entrada)."""
    t0 = time.perf_counter()
    segmentos: list[Segmento] = []
    for e in entradas:
        segmentos.extend(_etapa1(e.tipo, e.ref, e.pie, e.texto_extraido))
    segmentos = [s for s in segmentos if s.texto or s.advertencias]
    transcripcion = "\n".join(s.texto for s in segmentos if s.texto)
    adv = [a for s in segmentos for a in s.advertencias]
    modelos = {s.fuente: s.modelo for s in segmentos if s.modelo}
    conductas: list[Conducta] = []
    nino = None
    if etapa2 and transcripcion:
        from .. import config
        from .conductas import extraer
        conductas, nino, adv2 = extraer([(s.fuente, s.texto) for s in segmentos if s.texto], guia=guia)
        adv += adv2
        modelos["conductas"] = config.MODELO_CONDUCTAS
    con_texto = [s for s in segmentos if s.texto]
    calidad = min((s.calidad for s in con_texto), default=0.0)
    return ObservacionNormalizada(
        transcripcion=transcripcion, conductas=conductas, nino_mencionado=nino,
        calidad=round(calidad, 3), advertencias=adv, modelos=modelos,
        latencia_ms=int((time.perf_counter() - t0) * 1000), segmentos=segmentos)
