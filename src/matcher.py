"""Matcher híbrido: texto de la observación -> manifestaciones (conductas observables).

Híbrido = combina **similitud semántica** (embeddings de Bedrock Titan) con
**similitud léxica** (solapamiento de tokens). Es el paso que convierte el
lenguaje libre de la tía ("se vistió sola, contó hasta 5") en la evidencia
estructurada que el clasificador necesita.

Sin Bedrock (modo offline/MOCK) cae elegantemente a sólo-léxico, así la demo
nunca se cae. Los embeddings de las 90 manifestaciones se cachean en disco.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import json
import math
import re
import unicodedata

from . import config, marco


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", _norm(s)) if t not in marco.STOPWORDS and len(t) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _contencion(a: set[str], b: set[str]) -> float:
    """Qué fracción de los tokens de `a` aparece en `b` (recall asimétrico)."""
    if not a:
        return 0.0
    return len(a & b) / len(a)


@dataclass
class Match:
    manifestacion: dict
    score: float
    lexico: float
    semantico: float

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.manifestacion["id"], "nivel": self.manifestacion["nivel"],
                "dominio": self.manifestacion["dominio"], "texto": self.manifestacion["texto"],
                "score": round(self.score, 4), "lexico": round(self.lexico, 4),
                "semantico": round(self.semantico, 4)}


class Embedder:
    """Embeddings con Amazon Titan (Bedrock). Devuelve None si no está disponible."""

    MODEL_ID = "amazon.titan-embed-text-v2:0"

    def __init__(self) -> None:
        self._cliente = None
        self.disponible = False
        try:
            from .bedrock import GatewayModelos  # noqa
            import boto3
            if not config.usar_mock():
                self._cliente = boto3.client("bedrock-runtime", region_name=config.AWS_REGION)
                self.disponible = True
        except Exception:
            self.disponible = False

    def embed(self, texto: str) -> list[float] | None:
        if not self.disponible:
            return None
        try:
            r = self._cliente.invoke_model(
                modelId=self.MODEL_ID,
                body=json.dumps({"inputText": texto[:8000], "normalize": True}),
            )
            return json.loads(r["body"].read())["embedding"]
        except Exception:
            return None


def _cos(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)); nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb + 1e-9)


class Matcher:
    def __init__(self, usar_semantico: bool = True, alfa: float = 0.6,
                 anclas: list[dict] | None = None, nombre_cache: str = "emb_manifestaciones.json") -> None:
        """alfa = peso del componente semántico (el resto es léxico).

        anclas: textos de referencia de otro marco (src/marcos.py, p. ej. la rúbrica de Integra),
        cada uno con id, nivel, dominio, texto y opcionalmente tramo. Por defecto, las 90
        manifestaciones del dataset (comportamiento original).
        """
        self.alfa = alfa
        self.embedder = Embedder() if usar_semantico else Embedder()
        if not usar_semantico:
            self.embedder.disponible = False
        self.man = list(anclas) if anclas is not None else list(marco.manifestaciones())
        self._nombre_cache = nombre_cache
        self._tok = [(_tokens(m["texto"]), m) for m in self.man]
        self._emb: list[list[float] | None] = []
        self._cargar_o_calcular_embeddings()

    # -- cache de embeddings ------------------------------------------
    def _cache_path(self):
        return config.RAIZ / "models" / self._nombre_cache

    def _cargar_o_calcular_embeddings(self) -> None:
        # intenta cache
        if self.embedder.disponible and self._cache_path().exists():
            try:
                data = json.loads(self._cache_path().read_text())
                if len(data) == len(self.man):
                    self._emb = data
                    return
            except Exception:
                pass
        if self.embedder.disponible:
            self._emb = [self.embedder.embed(m["texto"]) for m in self.man]
            try:
                self._cache_path().parent.mkdir(exist_ok=True)
                self._cache_path().write_text(json.dumps(self._emb))
            except Exception:
                pass
        else:
            self._emb = [None] * len(self.man)

    # -- matching ------------------------------------------------------
    # Rango empírico de la similitud coseno de Titan; se reescala a [0,1].
    SEM_LO, SEM_HI = 0.15, 0.55

    def matchear(self, texto: str, top_k: int = 8, umbral: float = 0.25,
                 ratio: float = 0.65, tramo: str | None = None,
                 excluir: set[str] | None = None) -> list[Match]:
        """Híbrido: score = alfa*semantico_reescalado + (1-alfa)*lexico.

        Usa umbral **relativo** (una fracción del mejor score) para no depender de
        la escala absoluta de los embeddings. `tramo` restringe a las anclas de ese tramo;
        `excluir` deja fuera ids de anclas (evaluación leave-one-out).
        """
        q_tok = _tokens(texto)
        q_emb = self.embedder.embed(texto) if self.embedder.disponible else None
        scored: list[Match] = []
        for i, (tok, m) in enumerate(self._tok):
            if (tramo and m.get("tramo") != tramo) or (excluir and m["id"] in excluir):
                continue
            lex = max(_jaccard(q_tok, tok), 0.6 * _contencion(q_tok, tok))
            sem = _cos(q_emb, self._emb[i]) if (q_emb and self._emb and self._emb[i]) else 0.0
            sem_r = max(0.0, min(1.0, (sem - self.SEM_LO) / (self.SEM_HI - self.SEM_LO)))
            score = (self.alfa * sem_r + (1 - self.alfa) * lex) if q_emb else lex
            scored.append(Match(manifestacion=m, score=score, lexico=lex, semantico=sem))
        if not scored:
            return []
        top = max(x.score for x in scored)
        corte = max(umbral, ratio * top) if q_emb else umbral
        out = [x for x in scored if x.score >= corte]
        out.sort(key=lambda x: x.score, reverse=True)
        return out[:top_k]
