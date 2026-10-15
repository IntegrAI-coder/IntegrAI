"""Contrato de salida de U2: lo que la ingesta multimodal entrega al matcher.

Etapa 1 (transcripción fiel) llena `transcripcion`; etapa 2 (normalización
conductual) llena `conductas`. Cada conducta debe citar un fragmento literal de
la transcripción: si la cita no aparece, la conducta se descarta (anti-alucinación).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, Field

Fuente = Literal["texto", "audio", "post_it", "escena", "video_audio", "video_visual"]


def normalizar(s: str) -> str:
    """minúsculas, sin tildes, sin puntuación, espacios simples (para comparar citas)."""
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9ñ ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


class Conducta(BaseModel):
    texto: str = Field(description="Conducta observable, corta, en presente y tercera persona. Ej: 'Camina sin apoyo varios pasos'.")
    cita: str = Field(description="Fragmento LITERAL de la transcripción que respalda la conducta.")
    fuente: Fuente = "texto"
    t_inicio_s: float | None = Field(default=None, description="Segundo del video donde ocurre (solo video).")


class Segmento(BaseModel):
    """Resultado de la etapa 1 para una entrada."""
    fuente: Fuente
    texto: str
    calidad: float = Field(ge=0, le=1, default=1.0)
    advertencias: list[str] = []
    modelo: str = ""


class ObservacionNormalizada(BaseModel):
    transcripcion: str
    conductas: list[Conducta] = []
    nino_mencionado: str | None = None
    calidad: float = Field(ge=0, le=1, default=1.0)
    advertencias: list[str] = []
    modelos: dict[str, str] = {}
    latencia_ms: int = 0
    segmentos: list[Segmento] = []

    def texto_para_matcher(self) -> str:
        """Lo que consume Matcher.matchear(): conductas unidas, o la transcripción si no hay."""
        if self.conductas:
            return " ".join(c.texto.rstrip(".") + "." for c in self.conductas)
        return self.transcripcion


def cita_valida(cita: str, transcripcion: str, min_cobertura: float = 0.8) -> bool:
    """La cita está en la transcripción (literal normalizado, o >=80 % de sus palabras en orden cercano)."""
    c, t = normalizar(cita), normalizar(transcripcion)
    if not c:
        return False
    if c in t:
        return True
    palabras = c.split()
    tok = set(t.split())
    return len(palabras) >= 2 and sum(p in tok for p in palabras) / len(palabras) >= min_cobertura
