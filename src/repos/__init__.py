"""Sincronización de repos (clonar/escanear/indexar) para el pipeline RAG.

Conveniencia: ``from src.repos import clonar_repo, escanear_repo, ingestar_repo``.
"""
from __future__ import annotations

from .rag import (
    DATA_TYPE,
    ItemIndexado,
    embedding,
    ingestar_archivo,
    ingestar_repo,
    trocear,
)
from .sincronizacion import (
    REPOS_DIR,
    ArchivoInfo,
    CloneResult,
    clonar_repo,
    escanear_por_nombre,
    escanear_repo,
    es_url_repo,
    listar_repos,
    parsear_url,
    resolver_destino,
    resumen,
)

__all__ = [
    "REPOS_DIR",
    "DATA_TYPE",
    "ArchivoInfo",
    "CloneResult",
    "ItemIndexado",
    "clonar_repo",
    "escanear_por_nombre",
    "escanear_repo",
    "es_url_repo",
    "listar_repos",
    "parsear_url",
    "resolver_destino",
    "resumen",
    "embedding",
    "ingestar_archivo",
    "ingestar_repo",
    "trocear",
]
