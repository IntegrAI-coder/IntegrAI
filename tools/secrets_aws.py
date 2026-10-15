#!/usr/bin/env python3
"""Gestión de secretos de Meta (WA_TOKEN, WA_APP_SECRET) en AWS Secrets Manager.
Docs/SEGURIDAD.md: guardar secretos de Meta fuera del disco (F0).

    python tools/secrets_aws.py auditar  # solo lectura
    python tools/secrets_aws.py crear    # crea/actualiza secretos desde variables de entorno o getpass (no imprime)

Requiere credenciales AWS configuradas. Usa región us-east-1 por defecto.
No versiona secretos: los valores no se escriben en el repo.
"""
from __future__ import annotations

import getpass
import os
import sys

REGION = os.getenv("AWS_REGION", "us-east-1")
SECRET_TOKEN = "integrai/wa-token"
SECRET_APP_SECRET = "integrai/wa-app-secret"


def _sm():
    import boto3

    return boto3.Session(region_name=REGION).client("secretsmanager")


def auditar() -> None:
    sm = _sm()
    for name in (SECRET_TOKEN, SECRET_APP_SECRET, "integrai/api-token"):
        resp = sm.list_secrets(Filters=[{"Key": "name", "Values": [name]}])
        items = resp.get("SecretList", [])
        if items:
            s = items[0]
            print("OK ", name, s.get("LastChangedDate"))
        else:
            print("-- ", name, "(no existe)")


def _get_secret(name: str, env: str) -> str:
    val = os.getenv(env)
    if val:
        return val
    return getpass.getpass(f"Ingrese valor para {name} ({env}): ")


def crear() -> None:
    sm = _sm()
    token = _get_secret(SECRET_TOKEN, "WA_TOKEN")
    app_secret = _get_secret(SECRET_APP_SECRET, "WA_APP_SECRET")

    for name, val in ((SECRET_TOKEN, token), (SECRET_APP_SECRET, app_secret)):
        try:
            sm.create_secret(Name=name, SecretString=val, Description="IntegrAI Meta WhatsApp secret (F0)")
            print("creado:", name)
        except sm.exceptions.ResourceExistsException:
            sm.put_secret_value(SecretId=name, SecretString=val)
            print("actualizado:", name)
        except Exception as e:
            print("ERROR", name, e, file=sys.stderr)
            raise


if __name__ == "__main__":
    cmd = (sys.argv[1:] or ["auditar"])[0]
    if cmd == "auditar":
        auditar()
    elif cmd == "crear":
        crear()
    else:
        sys.exit(__doc__)
