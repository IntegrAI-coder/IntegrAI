#!/usr/bin/env python3
"""Ejecución del plan de seguridad (docs/SEGURIDAD.md §3) sobre la cuenta AWS.

    python tools/seguridad_aws.py auditar          # solo lectura: estado actual
    python tools/seguridad_aws.py corte            # 80/8000 SOLO desde CloudFront (rompe el acceso directo por IP)
    python tools/seguridad_aws.py corte --cerrar-admin   # además cierra 22/8501 (admin solo por SSM)
    python tools/seguridad_aws.py revertir-corte   # vuelve a abrir 80/8000 a internet (emergencia)

Requiere INTEGRA_INSTANCE_ID (no se versiona el ID: repo público).
`corte` se ejecuta SOLO cuando el webhook ya usa la URL de CloudFront (INTEGRA_BACKEND=https://...).
"""
from __future__ import annotations

import os
import sys

import boto3

REGION = os.getenv("AWS_REGION", "us-east-1")
IID = os.getenv("INTEGRA_INSTANCE_ID", "")
PL_CLOUDFRONT = "com.amazonaws.global.cloudfront.origin-facing"
s = boto3.Session(region_name=REGION)
ec2 = s.client("ec2")


def _instancia() -> dict:
    if not IID:
        sys.exit("define INTEGRA_INSTANCE_ID")
    return ec2.describe_instances(InstanceIds=[IID])["Reservations"][0]["Instances"][0]


def _sg() -> str:
    return _instancia()["SecurityGroups"][0]["GroupId"]


def _prefix_list() -> str:
    r = ec2.describe_managed_prefix_lists(Filters=[{"Name": "prefix-list-name", "Values": [PL_CLOUDFRONT]}])
    return r["PrefixLists"][0]["PrefixListId"]


def auditar() -> None:
    i = _instancia()
    ok = lambda b: "OK " if b else "-- "
    print(ok(i["MetadataOptions"]["HttpTokens"] == "required"), "IMDSv2 obligatorio")
    vols = ec2.describe_volumes(VolumeIds=[b["Ebs"]["VolumeId"] for b in i["BlockDeviceMappings"]])["Volumes"]
    print(ok(all(v["Encrypted"] for v in vols)), "EBS de la instancia cifrado")
    print(ok(ec2.get_ebs_encryption_by_default()["EbsEncryptionByDefault"]), "EBS cifrado por defecto (cuenta)")
    sg = ec2.describe_security_groups(GroupIds=[_sg()])["SecurityGroups"][0]
    for p in sg["IpPermissions"]:
        abiertos = [r["CidrIp"] for r in p.get("IpRanges", []) if r["CidrIp"] == "0.0.0.0/0"]
        print(ok(not abiertos), f"puerto {p.get('FromPort')}-{p.get('ToPort')}:",
              [r["CidrIp"] for r in p.get("IpRanges", [])] + [x["PrefixListId"] for x in p.get("PrefixListIds", [])])
    cf = s.client("cloudfront").list_distributions().get("DistributionList", {}).get("Items", [])
    integrai = [d for d in cf if "IntegrAI" in d.get("Comment", "")]
    print(ok(bool(integrai)), "CloudFront (TLS):", [f"https://{d['DomainName']} {d['Status']}" for d in integrai])
    sm = [x["Name"] for x in s.client("secretsmanager").list_secrets()["SecretList"] if x["Name"].startswith("integrai/")]
    print(ok(bool(sm)), "Secretos en Secrets Manager:", sm)


def corte() -> None:
    """Una sola regla 80-8000 desde el prefix list de CloudFront (dos reglas superan la cuota de 60 del SG).
    También cierra 22 y 8501 (administración por SSM).
    """
    sg, pl = _sg(), _prefix_list()
    ec2.authorize_security_group_ingress(GroupId=sg, IpPermissions=[{
        "IpProtocol": "tcp", "FromPort": 80, "ToPort": 8000,
        "PrefixListIds": [{"PrefixListId": pl, "Description": "solo CloudFront (IntegrAI)"}]}])
    for puerto in (80, 8000):
        try:
            ec2.revoke_security_group_ingress(GroupId=sg, IpPermissions=[{
                "IpProtocol": "tcp", "FromPort": puerto, "ToPort": puerto, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}])
        except ec2.exceptions.ClientError as e:
            print(f"puerto {puerto}: {e.response['Error']['Code']}")
    # 22 y 8501: hoy están limitados a una IP (/32), no abiertos a internet. Solo se cierran del todo
    # con --cerrar-admin (administración únicamente por SSM); confirmar antes con quien use esa IP.
    if "--cerrar-admin" in sys.argv:
        grupo = ec2.describe_security_groups(GroupIds=[sg])["SecurityGroups"][0]
        for p in grupo["IpPermissions"]:
            if p.get("FromPort") in (22, 8501) and p.get("IpRanges"):
                ec2.revoke_security_group_ingress(GroupId=sg, IpPermissions=[{
                    "IpProtocol": p["IpProtocol"], "FromPort": p["FromPort"], "ToPort": p["ToPort"], "IpRanges": p["IpRanges"]}])
                print(f"puerto {p['FromPort']} cerrado ({[r['CidrIp'] for r in p['IpRanges']]})")
    print("corte aplicado: 80 y 8000 solo accesibles vía CloudFront"
          + ("; 22 y 8501 cerrados (admin solo por SSM)" if "--cerrar-admin" in sys.argv else "; 22/8501 sin cambios (usa --cerrar-admin)"))


def revertir_corte() -> None:
    sg = _sg()
    for puerto in (80, 8000):
        try:
            ec2.authorize_security_group_ingress(GroupId=sg, IpPermissions=[{
                "IpProtocol": "tcp", "FromPort": puerto, "ToPort": puerto, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}])
        except ec2.exceptions.ClientError as e:
            print(f"puerto {puerto}: {e.response['Error']['Code']}")
    print("revertido: 80 y 8000 abiertos a internet")


if __name__ == "__main__":
    {"auditar": auditar, "corte": corte, "revertir-corte": revertir_corte}.get(
        (sys.argv[1:] or ["auditar"])[0], lambda: sys.exit(__doc__))()
