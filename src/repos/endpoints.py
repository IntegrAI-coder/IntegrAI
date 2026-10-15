"""Endpoints HTTP de sincronización de repos (``/api/repos/*``).

Se montan en el servicio de decisión (``webhook_ec2.py``) y quedan protegidos
por el mismo token compartido (``INTEGRA_API_TOKEN``): si el token está vacío la
API queda abierta solo para desarrollo (fail-closed cuando sí hay token).
"""
from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from .rag import ingestar_repo
from .sincronizacion import (
    REPOS_DIR,
    clonar_repo,
    escanear_por_nombre,
    escanear_repo,
    listar_repos,
    parsear_url,
    resumen,
)

API_TOKEN = os.getenv("INTEGRA_API_TOKEN", "")


def requiere_token(x_api_key: str = Header(default="")) -> None:
    if API_TOKEN and not hmac.compare_digest(x_api_key, API_TOKEN):
        raise HTTPException(status_code=401, detail="no autorizado")


router = APIRouter(prefix="/api/repos", tags=["repos"],
                   dependencies=[Depends(requiere_token)])


class ClonReq(BaseModel):
    url: str = Field(..., description="URL https del repo o atajo owner/repo")
    indexar: bool = False


class EscaneoReq(BaseModel):
    repo: str | None = Field(default=None, description="owner/repo; vacío = todos")


class IndexarReq(BaseModel):
    repo: str = Field(..., description="owner/repo")
    max_trozos: int = 500


def _ruta_repo(nombre: str):
    try:
        _, owner, repo = parsear_url(nombre)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    ruta = (REPOS_DIR / owner / repo).resolve()
    base = REPOS_DIR.resolve()
    if base != ruta and base not in ruta.parents:
        raise HTTPException(status_code=400, detail="ruta fuera de REPOS_DIR")
    if not ruta.is_dir():
        raise HTTPException(status_code=404, detail=f"repo no clonado: {owner}/{repo}")
    return owner, repo, ruta


@router.get("")
def listar() -> dict:
    return {"repos": listar_repos()}


@router.post("/scan")
def escanear(req: EscaneoReq | None = None) -> dict:
    """Lista los repos clonados; si se indica ``repo``, detalla sus archivos."""
    if req and req.repo:
        owner, repo, ruta = _ruta_repo(req.repo)
        archivos = escanear_repo(ruta)
        return {
            "repos": [{
                "owner": owner, "repo": repo, "ruta": str(ruta),
                "total_archivos": len(archivos),
                "archivos": [a.to_dict() for a in archivos],
                "resumen": resumen(archivos),
            }]
        }
    return {"repos": listar_repos()}


@router.post("/clone")
def clonar(req: ClonReq) -> dict:
    """Clona/actualiza un repo y (opcionalmente) lo indexa en el RAG."""
    resultado = clonar_repo(req.url)
    respuesta: dict = {"clone": resultado.to_dict()}
    if not resultado.ok:
        raise HTTPException(status_code=400, detail=resultado.mensaje)
    _, owner, repo = parsear_url(req.url)
    ruta = REPOS_DIR / owner / repo
    archivos = escanear_repo(ruta)
    respuesta["repo"] = {
        "owner": owner, "repo": repo, "ruta": str(ruta),
        "total_archivos": len(archivos),
        "archivos": [a.to_dict() for a in archivos],
        "resumen": resumen(archivos),
    }
    if req.indexar:
        respuesta["indexado"] = ingestar_repo(ruta, source_repo=f"{owner}/{repo}",
                                              max_trozos=500)
    return respuesta


@router.post("/index")
def indexar(req: IndexarReq) -> dict:
    """Trocea y genera embeddings de un repo ya clonado (Bedrock Titan o MOCK)."""
    owner, repo, ruta = _ruta_repo(req.repo)
    return ingestar_repo(ruta, source_repo=f"{owner}/{repo}", max_trozos=req.max_trozos)
