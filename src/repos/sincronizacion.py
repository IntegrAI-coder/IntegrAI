"""Sincronización de repositorios: clonar (seguro) y escanear.

Solo se sincronizan repositorios **sintéticos** (metadatos ``data_type="synthetic_code"``).
El clonado es higiénico:

* ``git clone --depth 1`` en ``./repos/[owner]/[repo]`` (configurable con
  ``INTEGRA_REPOS_DIR``);
* sin ``shell=True`` (lista de argumentos) -> sin inyección de comandos;
* URL validada (solo https de un host permitido, por defecto ``github.com``) y
  destino confinado a ``REPOS_DIR`` (fail-closed, sin path traversal).
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
REPOS_DIR = Path(os.getenv("INTEGRA_REPOS_DIR", str(RAIZ / "repos")))

# Dominios desde los que aceptamos clonar (fail-closed: allowlist).
HOSTS_PERMITIDOS = frozenset(
    h.strip().lower()
    for h in os.getenv("INTEGRA_REPOS_HOSTS", "github.com").split(",")
    if h.strip()
)

# Extensiones de código/texto que vale la pena indexar.
EXTENSIONES: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".java": "java",
    ".kt": "kotlin",
    ".go": "go",
    ".rb": "ruby",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cs": "csharp",
    ".php": "php",
    ".swift": "swift",
    ".sql": "sql",
    ".sh": "shell",
    ".md": "markdown",
    ".txt": "text",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".html": "html",
    ".css": "css",
}

# Directorios que nunca se recorren (ruido, dependencias, artefactos).
IGNORAR_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        "dist",
        "build",
        "out",
        "coverage",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        ".next",
        ".nuxt",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "vendor",
        "target",
        "data",
    }
)

TAMANO_MAX_ARCHIVO = int(os.getenv("INTEGRA_REPOS_MAX_BYTES", str(1_000_000)))

_RE_COMPONENTE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")


@dataclass(frozen=True)
class ArchivoInfo:
    ruta: str          # ruta relativa dentro del repo
    lenguaje: str
    extension: str
    tamano: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CloneResult:
    ok: bool
    mensaje: str
    owner: str = ""
    repo: str = ""
    ruta: str = ""
    actualizado: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def parsear_url(url: str) -> tuple[str, str, str]:
    """Devuelve ``(host, owner, repo)`` o lanza ``ValueError`` si la URL no es válida.

    Acepta ``https://github.com/owner/repo(.git)`` y el atajo ``owner/repo``
    (asume GitHub). Rechaza cualquier otro esquema, host o componente raro.
    """
    texto = (url or "").strip()
    if not texto:
        raise ValueError("URL vacía")

    if "://" in texto:
        if not texto.lower().startswith("https://"):
            raise ValueError("solo se permite https://")
        resto = texto[len("https://"):]
    else:
        # atajo owner/repo -> asumimos el primer host permitido
        resto = f"{sorted(HOSTS_PERMITIDOS)[0]}/{texto}"

    partes = [p for p in resto.split("/") if p]
    if len(partes) != 3:
        raise ValueError("formato esperado: https://host/owner/repo")

    host, owner, repo = partes
    host = host.lower()
    if host not in HOSTS_PERMITIDOS:
        raise ValueError(f"host no permitido: {host}")
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not _RE_COMPONENTE.match(owner) or not _RE_COMPONENTE.match(repo):
        raise ValueError("owner/repo inválidos")
    return host, owner, repo


def resolver_destino(url: str) -> Path:
    """Ruta de destino confinada a ``REPOS_DIR`` (fail-closed ante traversal)."""
    _, owner, repo = parsear_url(url)
    destino = (REPOS_DIR / owner / repo).resolve()
    base = REPOS_DIR.resolve()
    if base != destino and base not in destino.parents:
        raise ValueError("destino fuera de REPOS_DIR")
    return destino


def es_url_repo(texto: str) -> bool:
    try:
        parsear_url(texto)
        return True
    except ValueError:
        return False


def clonar_repo(url: str, profundidad: int = 1, timeout: int = 120) -> CloneResult:
    """Clona (o actualiza con ``--ff-only``) un repo en ``REPOS_DIR/[owner]/[repo]``."""
    try:
        host, owner, repo = parsear_url(url)
        destino = resolver_destino(url)
    except ValueError as e:
        return CloneResult(ok=False, mensaje=str(e))

    REPOS_DIR.mkdir(parents=True, exist_ok=True)
    entorno = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}  # nunca pedir credenciales

    try:
        if (destino / ".git").is_dir():
            r = subprocess.run(
                ["git", "-C", str(destino), "pull", "--ff-only", "--depth", str(profundidad)],
                capture_output=True, text=True, timeout=timeout, env=entorno,
            )
            if r.returncode != 0:
                return CloneResult(ok=False, owner=owner, repo=repo, ruta=str(destino),
                                   mensaje=f"no se pudo actualizar: {r.stderr.strip()[:200]}")
            return CloneResult(ok=True, owner=owner, repo=repo, ruta=str(destino),
                               actualizado=True, mensaje="repositorio actualizado")
        if destino.exists():
            return CloneResult(ok=False, owner=owner, repo=repo, ruta=str(destino),
                               mensaje="el destino existe y no es un repo git")
        r = subprocess.run(
            ["git", "clone", "--depth", str(profundidad), f"https://{host}/{owner}/{repo}.git",
             str(destino)],
            capture_output=True, text=True, timeout=timeout, env=entorno,
        )
        if r.returncode != 0:
            return CloneResult(ok=False, owner=owner, repo=repo, ruta=str(destino),
                               mensaje=f"git clone falló: {r.stderr.strip()[:200]}")
        return CloneResult(ok=True, owner=owner, repo=repo, ruta=str(destino),
                           mensaje="repositorio clonado")
    except subprocess.TimeoutExpired:
        return CloneResult(ok=False, owner=owner, repo=repo, ruta=str(destino),
                           mensaje="git tardó demasiado (timeout)")
    except FileNotFoundError:
        return CloneResult(ok=False, owner=owner, repo=repo, mensaje="git no está disponible")
    except Exception as e:  # noqa: BLE001
        return CloneResult(ok=False, owner=owner, repo=repo, mensaje=f"{type(e).__name__}: {e}")


def escanear_repo(ruta: str | Path, limite: int = 5000) -> list[ArchivoInfo]:
    """Recorre un repo y devuelve los archivos indexables (solo metadatos, sin contenido)."""
    base = Path(ruta)
    if not base.is_dir():
        return []
    hallados: list[ArchivoInfo] = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in IGNORAR_DIRS and not d.startswith(".")]
        for nombre in filenames:
            if nombre.startswith("."):
                continue
            ext = Path(nombre).suffix.lower()
            if ext not in EXTENSIONES:
                continue
            archivo = Path(dirpath) / nombre
            try:
                tamano = archivo.stat().st_size
            except OSError:
                continue
            if tamano > TAMANO_MAX_ARCHIVO:
                continue
            hallados.append(ArchivoInfo(
                ruta=archivo.relative_to(base).as_posix(),
                lenguaje=EXTENSIONES[ext],
                extension=ext,
                tamano=tamano,
            ))
            if len(hallados) >= limite:
                return sorted(hallados, key=lambda a: a.ruta)
    return sorted(hallados, key=lambda a: a.ruta)


def escanear_por_nombre(nombre: str) -> list[ArchivoInfo]:
    """Escanea ``REPOS_DIR/[owner]/[repo]`` a partir de ``owner/repo`` o de la URL."""
    try:
        _, owner, repo = parsear_url(nombre)
    except ValueError:
        return []
    return escanear_repo(REPOS_DIR / owner / repo)


def listar_repos() -> list[dict]:
    """Lista los repos ya clonados en ``REPOS_DIR`` con su resumen de archivos."""
    if not REPOS_DIR.is_dir():
        return []
    repos: list[dict] = []
    for entrada in sorted(REPOS_DIR.iterdir()):
        if not entrada.is_dir() or entrada.name.startswith("."):
            continue
        for repo_dir in sorted(entrada.iterdir()):
            if not (repo_dir / ".git").is_dir():
                continue
            archivos = escanear_repo(repo_dir)
            repos.append({
                "owner": entrada.name,
                "repo": repo_dir.name,
                "ruta": str(repo_dir.resolve()),
                "total_archivos": len(archivos),
                "archivos": [a.to_dict() for a in archivos],
            })
    return repos


def resumen(archivos: list[ArchivoInfo]) -> dict:
    """Conteo por lenguaje (para la vista de Sincronización)."""
    por_lenguaje: dict[str, int] = {}
    for a in archivos:
        por_lenguaje[a.lenguaje] = por_lenguaje.get(a.lenguaje, 0) + 1
    return {
        "total": len(archivos),
        "bytes": sum(a.tamano for a in archivos),
        "por_lenguaje": dict(sorted(por_lenguaje.items(), key=lambda kv: -kv[1])),
    }
