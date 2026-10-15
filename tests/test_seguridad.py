"""Tests de los controles de seguridad (offline)."""
import hashlib
import hmac
from types import SimpleNamespace as N

import pytest

from src.multimodal import normalizar_entradas
from src.seguridad.archivos import MAX_BYTES, MedioInvalido, ruta_segura, tipo_real, validar_medio
from src.seguridad.webhook import enmascarar, telefono_autorizado, verificar_firma

SECRETO = "app-secret-de-prueba"


def _firma(cuerpo: bytes) -> str:
    return "sha256=" + hmac.new(SECRETO.encode(), cuerpo, hashlib.sha256).hexdigest()


def test_firma_valida_e_invalida():
    cuerpo = b'{"entry":[]}'
    assert verificar_firma(cuerpo, _firma(cuerpo), SECRETO)
    assert not verificar_firma(cuerpo + b" ", _firma(cuerpo), SECRETO)      # cuerpo alterado
    assert not verificar_firma(cuerpo, _firma(cuerpo), "otro-secreto")
    assert not verificar_firma(cuerpo, None, SECRETO)
    assert not verificar_firma(cuerpo, "md5=abc", SECRETO)
    assert not verificar_firma(cuerpo, _firma(cuerpo), "")                   # sin secreto configurado


def test_whitelist_y_mascara():
    wl = {"+56 9 1234 5678"}
    assert telefono_autorizado("56912345678", wl)
    assert not telefono_autorizado("56900000000", wl)
    assert not telefono_autorizado("", wl)
    assert enmascarar("56912345678") == "569*****678"


def test_path_traversal_rechazado(tmp_path):
    base = tmp_path / "medios"; base.mkdir()
    (base / "ok.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    assert ruta_segura("ok.jpg", base) == (base / "ok.jpg").resolve()
    for malo in ("../secreto.txt", str(tmp_path / "fuera.jpg"), "sub/../../x"):
        with pytest.raises(MedioInvalido):
            ruta_segura(malo, base)


def test_magic_bytes_y_tamano(tmp_path):
    jpg = tmp_path / "a.jpg"; jpg.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 100)
    falso = tmp_path / "b.jpg"; falso.write_bytes(b"#!/bin/sh\nrm -rf /")
    ogg = tmp_path / "c.ogg"; ogg.write_bytes(b"OggS" + b"0" * 100)
    assert validar_medio(jpg, "imagen") == "jpeg"
    assert validar_medio(ogg, "audio") == "ogg"
    with pytest.raises(MedioInvalido):
        validar_medio(falso, "imagen")            # extensión .jpg pero no es imagen
    with pytest.raises(MedioInvalido):
        validar_medio(jpg, "audio")               # imagen enviada como audio
    grande = tmp_path / "g.mp4"
    with open(grande, "wb") as f:
        f.write(b"\x00\x00\x00\x18ftypmp42"); f.truncate(MAX_BYTES + 1)
    with pytest.raises(MedioInvalido):
        validar_medio(grande, "video")
    assert tipo_real(b"\x00\x00\x00\x18ftypmp42") == "mp4"


def test_u2_rechaza_ruta_fuera_del_directorio(tmp_path, monkeypatch):
    monkeypatch.setenv("DIR_MEDIOS", str(tmp_path))
    obs = normalizar_entradas([N(tipo="foto", ref="../../.aws/credentials", pie="", texto_extraido="")], etapa2=False)
    assert obs.transcripcion == ""
    assert "ruta de archivo no permitida" in obs.advertencias
