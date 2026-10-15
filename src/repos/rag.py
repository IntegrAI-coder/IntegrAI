"""Pipeline RAG: trocear código, generar embeddings (Bedrock Titan) y preparar
los ítems indexables con sus metadatos.

Sin credenciales AWS todo corre en MOCK: el embedding es determinista (hash ->
vector) para que el flujo sea demostrable y testeable sin nube.

Cada ítem lleva metadatos de trazabilidad exigidos por la spec:

    {
      "source_repo": "owner/repo",
      "file_path": "src/app.py",
      "data_type": "synthetic_code",
      "chunk_index": 3,
      "lenguaje": "python"
    }
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .. import config
from .sincronizacion import ArchivoInfo, escanear_repo

MODELO_EMBEDDING = os.getenv("MODELO_EMBEDDING", "amazon.titan-embed-text-v2:0")
DIMENSIONES = int(os.getenv("INTEGRA_EMBED_DIM", "256"))
TAMANO_TROZO = int(os.getenv("INTEGRA_CHUNK_CHARS", "1000"))
SOLAPE = int(os.getenv("INTEGRA_CHUNK_OVERLAP", "200"))
MAX_TROZOS = int(os.getenv("INTEGRA_MAX_CHUNKS", "500"))
DATA_TYPE = "synthetic_code"


@dataclass
class ItemIndexado:
    texto: str
    metadata: dict
    embedding: list[float] = field(default_factory=list)


def trocear(texto: str, tamano: int = TAMANO_TROZO, solape: int = SOLAPE) -> list[str]:
    """Parte ``texto`` en trozos de ``tamano`` caracteres con ``solape`` de contexto."""
    if solape < 0 or solape >= tamano:
        raise ValueError("el solape debe estar entre 0 y tamano-1")
    limpio = texto.strip()
    if not limpio:
        return []
    if len(limpio) <= tamano:
        return [limpio]
    paso = tamano - solape
    trozos: list[str] = []
    for i in range(0, len(limpio), paso):
        trozo = limpio[i:i + tamano].strip()
        if trozo:
            trozos.append(trozo)
        if i + tamano >= len(limpio):
            break
    return trozos


def _embedding_mock(texto: str, dimensiones: int = DIMENSIONES) -> list[float]:
    """Vector determinista en [0, 1) a partir de sha256 (sin AWS, reproducible)."""
    base = hashlib.sha256(texto.encode("utf-8")).digest()
    vector: list[float] = []
    contador = 0
    while len(vector) < dimensiones:
        bloque = hashlib.sha256(base + contador.to_bytes(4, "big")).digest()
        for byte in bloque:
            vector.append(byte / 255.0)
            if len(vector) == dimensiones:
                break
        contador += 1
    return vector


def embedding(texto: str) -> list[float]:
    """Embedding real (Bedrock Titan) con degradación a MOCK."""
    if config.usar_mock():
        return _embedding_mock(texto)
    try:
        import boto3  # type: ignore

        cliente = boto3.client("bedrock-runtime", region_name=config.AWS_REGION)
        r = cliente.invoke_model(
            modelId=MODELO_EMBEDDING,
            body=json.dumps({"inputText": texto}),
            accept="application/json",
            contentType="application/json",
        )
        return list(json.loads(r["body"].read())["embedding"])
    except Exception:  # noqa: BLE001
        return _embedding_mock(texto)


def _leer_texto(archivo: Path) -> str | None:
    """Lee un archivo como texto; devuelve ``None`` si es binario o ilegible."""
    try:
        return archivo.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def ingestar_archivo(ruta_repo: Path, info: ArchivoInfo, source_repo: str,
                     tamano: int = TAMANO_TROZO, solape: int = SOLAPE) -> list[ItemIndexado]:
    """Trocea e indexa un único archivo del repo."""
    contenido = _leer_texto(ruta_repo / info.ruta)
    if contenido is None:
        return []
    items: list[ItemIndexado] = []
    for i, trozo in enumerate(trocear(contenido, tamano, solape)):
        items.append(ItemIndexado(
            texto=trozo,
            metadata={
                "source_repo": source_repo,
                "file_path": info.ruta,
                "data_type": DATA_TYPE,
                "chunk_index": i,
                "lenguaje": info.lenguaje,
            },
        ))
    return items


def ingestar_repo(ruta: str | Path, source_repo: str | None = None,
                  max_trozos: int = MAX_TROZOS, con_embeddings: bool = True) -> dict:
    """Indexa todos los archivos de un repo clonado.

    Devuelve un resumen con los ítems (texto + metadatos + embedding) acotado a
    ``max_trozos`` para no explotar en repos grandes.
    """
    base = Path(ruta)
    if source_repo is None:
        source_repo = f"{base.parent.name}/{base.name}"
    archivos = escanear_repo(base)
    items: list[ItemIndexado] = []
    truncado = False
    for info in archivos:
        for item in ingestar_archivo(base, info, source_repo):
            if len(items) >= max_trozos:
                truncado = True
                break
            items.append(item)
        if truncado:
            break
    if con_embeddings:
        for item in items:
            item.embedding = embedding(item.texto)
    return {
        "source_repo": source_repo,
        "ruta": str(base),
        "archivos": len(archivos),
        "trozos": len(items),
        "truncado": truncado,
        "modelo_embedding": "MOCK" if config.usar_mock() else MODELO_EMBEDDING,
        "dimensiones": len(items[0].embedding) if items and items[0].embedding else 0,
        "items": [
            {"texto": it.texto, "metadata": it.metadata, "embedding": it.embedding}
            for it in items
        ],
    }
