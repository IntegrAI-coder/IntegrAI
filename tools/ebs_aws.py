#!/usr/bin/env python3
"""Migrar volumen EBS de la instancia a cifrado (F0).

    python tools/ebs_aws.py auditar
    python tools/ebs_aws.py plan

Requiere INTEGRA_INSTANCE_ID. No ejecuta la migración; solo genera un plan
detallado (--dry-run implícito). Para ejecutar requiere detener la instancia
(docs/SEGURIDAD.md L76).
"""
from __future__ import annotations

import os
import sys

REGION = os.getenv("AWS_REGION", "us-east-1")
IID = os.getenv("INTEGRA_INSTANCE_ID", "")


def _ec2():
    import boto3

    return boto3.Session(region_name=REGION).client("ec2")


def _volumes(inst):
    return [_v["Ebs"]["VolumeId"] for _v in inst["BlockDeviceMappings"] if _v.get("Ebs")]


def auditar() -> None:
    if not IID:
        sys.exit("define INTEGRA_INSTANCE_ID")
    ec2 = _ec2()
    inst = ec2.describe_instances(InstanceIds=[IID])["Reservations"][0]["Instances"][0]
    vols = ec2.describe_volumes(VolumeIds=_volumes(inst))["Volumes"]
    for v in vols:
        print(v["VolumeId"], "encrypted:", v["Encrypted"], "size:", v["Size"], "type:", v["VolumeType"])
    ebd = ec2.get_ebs_encryption_by_default()["EbsEncryptionByDefault"]
    print("EBS default encryption:", ebd)


def plan() -> None:
    if not IID:
        sys.exit("define INTEGRA_INSTANCE_ID")
    ec2 = _ec2()
    inst = ec2.describe_instances(InstanceIds=[IID])["Reservations"][0]["Instances"][0]
    state = inst["State"]["Name"]
    az = inst["Placement"]["AvailabilityZone"]
    vols = ec2.describe_volumes(VolumeIds=_volumes(inst))["Volumes"]
    print(f"Instancia {IID} estado={state} AZ={az}")
    for v in vols:
        if v["Encrypted"]:
            print(f"  {v['VolumeId']} YA cifrado (no requiere migración)")
            continue
        print(f"  {v['VolumeId']} SIN cifrar: size={v['Size']}")
        print("    PLAN (requiere detener instancia):")
        print(f"      1. ec2 stop-instances --instance-ids {IID}")
        print(f"      2. Crear snapshot: ec2 create-snapshot --volume-id {v['VolumeId']}")
        print(f"      3. Copiar snapshot cifrado: ec2 copy-snapshot --source-snapshot-id <snap> --source-region {REGION} --encrypted --kms-key-id <cmk> --destination-region {REGION}")
        print(f"      4. Crear volumen cifrado desde snapshot en {az}")
        print(f"      5. Desmontar y swap (detach/attach) / reemplazar raíz")
    print("Nota: esto es NO ejecutable aquí (solo plan). Ver L76 en docs/SEGURIDAD.md.")


if __name__ == "__main__":
    cmd = (sys.argv[1:] or ["auditar"])[0]
    if cmd == "auditar":
        auditar()
    elif cmd == "plan":
        plan()
    else:
        sys.exit(__doc__)
