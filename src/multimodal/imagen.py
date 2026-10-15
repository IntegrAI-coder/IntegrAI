"""Etapa 1 · imagen → texto.

1. Router: ¿es un post-it/nota manuscrita, una escena (niño/a haciendo algo) u otra cosa?
2. Post-it: transcripción LITERAL con Claude (no interpreta, marca [ilegible]) y una
   segunda lectura independiente con Nova 2 Lite. El CER entre ambas da la calidad:
   si discrepan > 15 %, se avisa para que la tía confirme el texto. (Los VLM tienden a
   "corregir" lo que no leen — OmniHandwritingOCR, 2026 — por eso se verifica.)
3. Escena: solo conductas observables, sin nombres, rasgos físicos ni juicios de nivel.
"""
from __future__ import annotations

import logging
from pathlib import Path

from .. import config
from ._bedrock import converse, formato_imagen
from .schema import Segmento, normalizar

PROMPT_ROUTER = ("Clasifica esta imagen en UNA palabra: 'post_it' si muestra texto escrito a mano "
                 "(nota, post-it, cuaderno, papel), 'escena' si muestra a una o más personas "
                 "haciendo algo, u 'otro'. Responde solo la palabra.")

PROMPT_LITERAL = ("Transcribe EXACTAMENTE el texto manuscrito de la imagen, en español, palabra por palabra. "
                  "No corrijas ortografía, no completes palabras, no agregues nada. "
                  "Conserva abreviaturas tal cual. Si una palabra no se lee, escribe [ilegible]. "
                  "Responde solo con la transcripción.")

PROMPT_ESCENA = ("Eres una educadora de párvulos observando esta imagen. Describe en 2 a 4 frases cortas, "
                 "en presente y tercera persona, SOLO las conductas observables del niño o niña "
                 "(postura, movimiento, manipulación de objetos, mirada, interacción, comunicación). "
                 "No nombres a nadie, no describas rasgos físicos ni ropa, no estimes edad ni nivel.")


def _bytes(path: str) -> bytes:
    return Path(path).read_bytes()


def _llamar_imagen(modelo: str, path: str, prompt: str, max_tokens: int = 500) -> str:
    contenido = [{"image": {"format": formato_imagen(path), "source": {"bytes": _bytes(path)}}},
                 {"text": prompt}]
    return converse(modelo, contenido, max_tokens=max_tokens)["texto"]


def cer(a: str, b: str) -> float:
    """Character Error Rate de `b` contra `a` (Levenshtein / len(a)) sobre texto normalizado."""
    a, b = normalizar(a), normalizar(b)
    if not a:
        return 0.0 if not b else 1.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] / len(a)


def clasificar_imagen(path: str) -> str:
    r = _llamar_imagen(config.MODELO_OCR_VERIF, path, PROMPT_ROUTER, max_tokens=5).lower()
    for k in ("post_it", "escena"):
        if k.replace("_", "") in r.replace("_", "").replace("-", ""):
            return k
    return "otro"


def leer_post_it(path: str, verificar: bool = True) -> Segmento:
    texto = _llamar_imagen(config.MODELO_OCR, path, PROMPT_LITERAL)
    adv: list[str] = []
    calidad = 1.0
    modelo = config.MODELO_OCR
    if verificar:
        try:
            segunda = _llamar_imagen(config.MODELO_OCR_VERIF, path, PROMPT_LITERAL)
            d = cer(texto, segunda)
            calidad = max(0.0, 1.0 - d)
            modelo += f" + verif {config.MODELO_OCR_VERIF}"
            if d > 0.15:
                adv.append(f"lecturas del post-it discrepan (CER {d:.0%}): confirmar el texto con la tía")
        except Exception:  # noqa: BLE001
            logging.getLogger(__name__).exception("verificación del post-it falló")
            adv.append("verificación de la lectura no disponible")
    n_ileg = texto.lower().count("[ilegible]")
    if n_ileg:
        adv.append(f"{n_ileg} palabra(s) ilegible(s)")
        calidad = min(calidad, max(0.0, 1 - 0.15 * n_ileg))
    return Segmento(fuente="post_it", texto=texto.strip(), calidad=round(calidad, 3), advertencias=adv, modelo=modelo)


def describir_escena(path: str) -> Segmento:
    texto = _llamar_imagen(config.MODELO_OCR, path, PROMPT_ESCENA)
    return Segmento(fuente="escena", texto=texto.strip(), calidad=0.8, modelo=config.MODELO_OCR,
                    advertencias=["descripción visual generada por modelo: revisar"])


def procesar_imagen(path: str, tipo: str | None = None) -> Segmento:
    if not path or not Path(path).exists():
        return Segmento(fuente="post_it", texto="", calidad=0.0, advertencias=["imagen no encontrada"])
    tipo = tipo or clasificar_imagen(path)
    if tipo == "post_it":
        return leer_post_it(path)
    if tipo == "escena":
        return describir_escena(path)
    return Segmento(fuente="escena", texto="", calidad=0.0,
                    advertencias=["la imagen no parece una nota ni una escena con niños/as"])
