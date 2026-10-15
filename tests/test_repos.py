"""Tests del módulo de sincronización de repos + RAG (offline, modo MOCK)."""
from __future__ import annotations

import pytest

from src import config
from src.repos import (
    clonar_repo,
    escanear_repo,
    es_url_repo,
    ingestar_repo,
    listar_repos,
    parsear_url,
    resolver_destino,
    resumen,
    trocear,
)
from src.repos import rag
from src.repos import sincronizacion


@pytest.fixture(autouse=True)
def _mock(monkeypatch):
    monkeypatch.setattr(config, "MODO_MOCK", "1")


# --- validación de URL (fail-closed) -----------------------------------------

@pytest.mark.parametrize("url", [
    "owner/repo",
    "https://github.com/owner/repo",
    "https://github.com/owner/repo.git",
])
def test_url_valida(url):
    assert parsear_url(url) == ("github.com", "owner", "repo")
    assert es_url_repo(url)


@pytest.mark.parametrize("url", [
    "",
    "http://github.com/owner/repo",
    "git://github.com/owner/repo",
    "https://evil.example.com/owner/repo",
    "https://github.com/owner",
    "https://github.com/owner/repo/extra",
    "file:///etc/passwd",
    "https://github.com/../etc",
    "https://github.com/owner/..",
])
def test_url_invalida(url):
    assert not es_url_repo(url)
    with pytest.raises(ValueError):
        parsear_url(url)


def test_destino_confinado(monkeypatch, tmp_path):
    monkeypatch.setattr(sincronizacion, "REPOS_DIR", tmp_path)
    destino = resolver_destino("https://github.com/owner/repo")
    assert tmp_path.resolve() in destino.parents


def test_clonar_url_invalida_no_ejecuta():
    r = clonar_repo("https://evil.example.com/x/y")
    assert not r.ok and "host" in r.mensaje


# --- escaneo -----------------------------------------------------------------

@pytest.fixture
def repo_falso(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hola')\n", encoding="utf-8")
    (tmp_path / "src" / "vista.tsx").write_text("export const x = 1;\n", encoding="utf-8")
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\r\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.py").write_text("x=1\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    (tmp_path / ".oculto.py").write_text("y=2\n", encoding="utf-8")
    return tmp_path


def test_escanear_filtra_ruido(repo_falso):
    rutas = {a.ruta for a in escanear_repo(repo_falso)}
    assert rutas == {"src/app.py", "src/vista.tsx"}


def test_escanear_repo_inexistente():
    assert escanear_repo("C:/no/existe/xyz") == []


def test_resumen_por_lenguaje(repo_falso):
    r = resumen(escanear_repo(repo_falso))
    assert r["total"] == 2
    assert r["por_lenguaje"] == {"python": 1, "typescript": 1}


def test_listar_repos_vacio(monkeypatch, tmp_path):
    monkeypatch.setattr(sincronizacion, "REPOS_DIR", tmp_path / "nada")
    assert listar_repos() == []


# --- troceado -----------------------------------------------------------------

def test_trocear_texto_corto():
    assert trocear("hola", tamano=100, solape=10) == ["hola"]


def test_trocear_vacio():
    assert trocear("   \n  ") == []


def test_trocear_con_solape():
    texto = "a" * 2500
    trozos = trocear(texto, tamano=1000, solape=200)
    assert len(trozos) == 3
    assert all(len(t) <= 1000 for t in trozos)


def test_trocear_solape_invalido():
    with pytest.raises(ValueError):
        trocear("x" * 100, tamano=100, solape=100)


# --- embeddings e indexado ----------------------------------------------------

def test_embedding_mock_determinista():
    a = rag.embedding("mismo texto")
    b = rag.embedding("mismo texto")
    c = rag.embedding("otro texto")
    assert a == b and a != c
    assert len(a) == rag.DIMENSIONES


def test_ingestar_repo_metadatos(repo_falso):
    resultado = ingestar_repo(repo_falso, source_repo="acme/demo", max_trozos=50)
    assert resultado["archivos"] == 2
    assert resultado["trozos"] == 2
    assert resultado["modelo_embedding"] == "MOCK"
    metadatos = {it["metadata"]["file_path"]: it["metadata"] for it in resultado["items"]}
    assert metadatos["src/app.py"]["source_repo"] == "acme/demo"
    assert metadatos["src/app.py"]["data_type"] == "synthetic_code"
    assert metadatos["src/app.py"]["lenguaje"] == "python"
    assert all(len(it["embedding"]) == rag.DIMENSIONES for it in resultado["items"])


def test_ingestar_repo_trocea_archivo_grande(tmp_path):
    (tmp_path / "grande.py").write_text("linea\n" * 2000, encoding="utf-8")
    resultado = ingestar_repo(tmp_path, source_repo="a/b")
    assert resultado["trozos"] > 1
    assert resultado["truncado"] is False


# --- endpoints HTTP (/api/repos/*) --------------------------------------------

def _cliente(monkeypatch, tmp_path, token=""):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.repos import endpoints

    monkeypatch.setattr(endpoints, "REPOS_DIR", tmp_path)
    monkeypatch.setattr(sincronizacion, "REPOS_DIR", tmp_path)
    monkeypatch.setattr(endpoints, "API_TOKEN", token)
    app = FastAPI()
    app.include_router(endpoints.router)
    return TestClient(app)


def test_endpoint_listar_vacio(monkeypatch, tmp_path):
    c = _cliente(monkeypatch, tmp_path)
    assert c.get("/api/repos").json() == {"repos": []}


def test_endpoint_exige_token(monkeypatch, tmp_path):
    c = _cliente(monkeypatch, tmp_path, token="secreto")
    assert c.get("/api/repos").status_code == 401
    assert c.get("/api/repos", headers={"X-Api-Key": "secreto"}).status_code == 200


def test_endpoint_clone_url_invalida(monkeypatch, tmp_path):
    c = _cliente(monkeypatch, tmp_path)
    r = c.post("/api/repos/clone", json={"url": "https://evil.example.com/a/b"})
    assert r.status_code == 400


def test_endpoint_scan_repo_no_clonado(monkeypatch, tmp_path):
    c = _cliente(monkeypatch, tmp_path)
    r = c.post("/api/repos/scan", json={"repo": "acme/demo"})
    assert r.status_code == 404
