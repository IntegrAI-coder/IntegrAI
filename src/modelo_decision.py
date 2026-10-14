"""Primitivas de decisión tipada (estilo "Jev / System One").

Un *decision model* NO redacta: devuelve una decisión tipada en un solo paso.
Las tres primitivas son:

    - Choice : elegir 1 de N opciones (con distribución calibrada)
    - Score  : un valor continuo con intervalo de confianza
    - Noul   : un sí/no calibrado (probabilidad) sobre una pregunta

La gracia de la decisión tipada es que es **auditable**: el espacio de
respuesta es finito y enumerable, y cada salida lleva una confianza calibrada
(no una frase que puede alucinar forma). "Decide, no redacta."

Este módulo define el contrato y un backend heurístico (MOCK). El backend real
(Jev API / Laya open-weight / CLM-8B local) se enchufa detrás de la misma
interfaz -> el resto del sistema es agnóstico del modelo.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Protocol
import json
import math


# --------------------------------------------------------------------------
# Primitivas
# --------------------------------------------------------------------------
@dataclass
class Choice:
    """Elegir 1 de N opciones (ej: nivel de logro de un aprendizaje)."""
    name: str
    options: list[str]
    value: str
    probabilities: dict[str, float]

    @property
    def confidence(self) -> float:
        return float(self.probabilities.get(self.value, 0.0))


@dataclass
class Score:
    """Valor continuo con intervalo (ej: 0-100 de desarrollo del núcleo)."""
    name: str
    value: float
    lo: float
    hi: float
    confidence: float


@dataclass
class Noul:
    """Pregunta sí/no calibrada (ej: ¿hay evidencia suficiente?)."""
    name: str
    question: str
    probability: float
    threshold: float = 0.5

    @property
    def value(self) -> bool:
        return self.probability >= self.threshold


@dataclass
class Decision:
    """Salida tipada completa de un decision model sobre una unidad de análisis."""
    choice: Choice | None = None
    scores: list[Score] = field(default_factory=list)
    flags: list[Noul] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def flag(self, name: str) -> Noul | None:
        for f in self.flags:
            if f.name == name:
                return f
        return None

    def score(self, name: str) -> Score | None:
        for s in self.scores:
            if s.name == name:
                return s
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "choice": asdict(self.choice) if self.choice else None,
            "scores": [asdict(s) for s in self.scores],
            "flags": [{**asdict(f), "value": f.value} for f in self.flags],
            "meta": self.meta,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------
# Utilidades matemáticas (calibración)
# --------------------------------------------------------------------------
def softmax(logits: list[float], temperature: float = 1.0) -> list[float]:
    """Softmax con temperatura (temperature>1 suaviza, <1 agudiza)."""
    if not logits:
        return []
    t = max(temperature, 1e-6)
    m = max(logits)
    exps = [math.exp((x - m) / t) for x in logits]
    s = sum(exps) or 1.0
    return [e / s for e in exps]


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


# --------------------------------------------------------------------------
# Backend (interfaz) — MOCK heurístico + gancho para modelo real
# --------------------------------------------------------------------------
class BackendDecision(Protocol):
    nombre: str

    def clasificar_nivel(
        self,
        señales_positivas: float,
        señales_negativas: float,
        n_evidencias: int,
        opciones: list[str],
    ) -> dict[str, Any]:
        ...


class BackendHeuristico:
    """Backend MOCK determinista.

    Convierte señales agregadas de evidencia en una decisión tipada.
    Es 'tipado' en el sentido de que respeta SIEMPRE el contrato (opción válida
    + probabilidades que suman 1 + confianza en [0,1]). No pretende ser el
    modelo final: es el *placeholder* que permite probar el flujo end-to-end
    mientras se enchufa Jev/Laya.
    """

    nombre = "heuristico-mock"

    def clasificar_nivel(
        self,
        señales_positivas: float,
        señales_negativas: float,
        n_evidencias: int,
        opciones: list[str],
    ) -> dict[str, Any]:
        vol = señales_positivas + señales_negativas
        ratio = (señales_positivas - señales_negativas) / vol if vol > 0 else 0.0
        ev = clamp01(vol / 3.0)                      # cuánta evidencia hay (volumen)
        strength = clamp01(ev * max(ratio, 0.0))     # manifestación = volumen × positividad

        # Logits sobre las 3 opciones típicas: No observado / En proceso / Logrado.
        n = len(opciones)
        if n == 3:
            if vol <= 0:
                logits = [4.0, 0.0, -2.0]            # sin señal -> No observado
            else:
                logits = [
                    -1.5,                            # No observado (si hay señal, no aplica)
                    1.2 + 0.8 * (1.0 - strength),    # En proceso (zona media)
                    strength * 2.6,                  # Logrado (requiere volumen + positividad)
                ]
        else:
            logits = [strength * (i + 1) for i in range(n)]

        probs = softmax(logits, temperature=0.9)
        value = opciones[max(range(n), key=lambda i: probs[i])]

        # Confianza: sube con la evidencia disponible
        prob_max = max(probs)
        conf = clamp01(prob_max * (0.6 + 0.4 * ev))

        score_val = round(strength * 100, 1)
        margen = 12.0 - 6.0 * ev
        suficiencia = ev
        return {
            "value": value,
            "probabilities": {o: round(p, 4) for o, p in zip(opciones, probs)},
            "confidence": round(conf, 4),
            "score": {
                "value": score_val,
                "lo": round(max(0.0, score_val - margen), 1),
                "hi": round(min(100.0, score_val + margen), 1),
                "confidence": round(conf, 4),
            },
            "suficiencia": round(suficiencia, 4),
        }


class BackendJevAPI:
    """Gancho para el modelo real (Jev / Laya / CLM).

    No implementado en el prototipo: si hay credenciales se usaría el SDK/API.
    Se deja explícito para que el diseño sea *modelo-agnóstico* (swap sin tocar
    el resto del sistema) — eje de auditoría y de costo.
    """

    nombre = "jev-api"

    def __init__(self, api_key: str | None = None, endpoint: str | None = None):
        self.api_key = api_key
        self.endpoint = endpoint

    def clasificar_nivel(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError(
            "Backend real no conectado en el prototipo. Ver README > Modelo de decisión."
        )


def construir_backend(nombre: str | None = None) -> BackendDecision:
    """Factory: elige el backend de decisión de forma agnóstica."""
    if nombre in (None, "", "heuristico", "mock"):
        return BackendHeuristico()
    if nombre in ("jev", "laya", "clm"):
        return BackendJevAPI()
    return BackendHeuristico()
