"""Validación de archivos de entrada (medios de WhatsApp).

- ruta_segura: la ruta del medio la genera el servidor, nunca el cliente. Aun así, toda lectura
  se confina a un directorio permitido (evita leer /etc/passwd, ~/.aws/credentials, etc.).
- validar_medio: tope de tamaño y verificación por magic bytes (no por extensión), para no
  mandar a los modelos archivos que no son lo que dicen ser.
"""
from __future__ import annotations

import os
from pathlib import Path

from .. import config

MAX_BYTES = int(os.getenv("MAX_MEDIO_BYTES", str(16 * 1024 * 1024)))  # límite de WhatsApp para video/audio

# firma -> tipo; algunas firmas requieren chequear un offset
_FIRMAS: list[tuple[str, int, bytes]] = [
    ("jpeg", 0, b"\xff\xd8\xff"),
    ("png", 0, b"\x89PNG\r\n\x1a\n"),
    ("gif", 0, b"GIF8"),
    ("webp", 8, b"WEBP"),
    ("ogg", 0, b"OggS"),
    ("mp3", 0, b"ID3"),
    ("mp3", 0, b"\xff\xfb"),
    ("mp3", 0, b"\xff\xf3"),
    ("wav", 8, b"WAVE"),
    ("mp4", 4, b"ftyp"),      # mp4, m4a, mov, 3gp
    ("webm", 0, b"\x1a\x45\xdf\xa3"),
]
_PERMITIDOS = {"imagen": {"jpeg", "png", "gif", "webp"},
               "audio": {"ogg", "mp3", "wav", "mp4"},
               "video": {"mp4", "webm"}}


class MedioInvalido(ValueError):
    """El archivo no se procesa; el mensaje es seguro para mostrar al usuario."""


def directorio_medios() -> Path:
    return Path(os.getenv("DIR_MEDIOS", str(config.RAIZ / "medios_tmp"))).resolve()


def ruta_segura(ref: str, base: Path | None = None) -> Path:
    """Resuelve `ref` y exige que quede dentro de `base` (por defecto DIR_MEDIOS)."""
    base = (base or directorio_medios()).resolve()
    p = Path(ref)
    p = (p if p.is_absolute() else base / p).resolve()
    if p != base and base not in p.parents:
        raise MedioInvalido("ruta de archivo no permitida")
    return p


def tipo_real(cabecera: bytes) -> str | None:
    for tipo, off, firma in _FIRMAS:
        if cabecera[off:off + len(firma)] == firma:
            return tipo
    return None


def validar_medio(path: Path, categoria: str) -> str:
    """Valida tamaño y magic bytes. Devuelve el tipo real (jpeg, ogg, mp4…)."""
    if not path.is_file():
        raise MedioInvalido("archivo no encontrado")
    if path.stat().st_size > MAX_BYTES:
        raise MedioInvalido(f"archivo supera {MAX_BYTES // (1024 * 1024)} MB")
    with open(path, "rb") as f:
        t = tipo_real(f.read(16))
    if t is None or t not in _PERMITIDOS.get(categoria, set()):
        raise MedioInvalido(f"el archivo no es un {categoria} válido")
    return t
