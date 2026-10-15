#!/usr/bin/env python3
"""Respaldos con AWS Backup (Docs/GOBIERNO_DATOS.md §2, custodia técnica — Ivan).

    python tools/backup_aws.py auditar
    python tools/backup_aws.py crear

Variables:
    AWS_REGION                 us-east-1 por defecto
    INTEGRA_BACKUP_SELECTION   ARN del recurso (volumen EBS) o tag 'Backup=integrai'
    INTEGRA_BACKUP_RETENTION   días de retención (default 14)

Sin secretos ni IDs en el repo.
"""
from __future__ import annotations

import os
import sys

REGION = os.getenv("AWS_REGION", "us-east-1")
RETENTION = int(os.getenv("INTEGRA_BACKUP_RETENTION", "14"))
PLAN = "integrai-ebs"
VAULT = "integrai-vault"


def _session():
    import boto3

    return boto3.Session(region_name=REGION)


def auditar() -> None:
    s = _session()
    backup = s.client("backup")
    try:
        planes = backup.list_backup_plans()["BackupPlansList"]
        encontrados = [p for p in planes if p["BackupPlanName"] == PLAN]
        print("OK ", PLAN if encontrados else "-- " + PLAN, [p["BackupPlanId"] for p in encontrados])
    except Exception as e:
        print("-- planes:", e)
    try:
        vaults = [v["BackupVaultName"] for v in backup.list_backup_vaults()["BackupVaultList"]]
        print("OK " if VAULT in vaults else "-- ", "vault:", vaults)
    except Exception as e:
        print("-- vaults:", e)


def _role_arn() -> str:
    s = _session()
    iam = s.client("iam")
    nombre = "integrai-backup"
    try:
        return iam.get_role(RoleName=nombre)["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        creado = iam.create_role(
            RoleName=nombre,
            AssumeRolePolicyDocument=(
                '{"Version":"2012-10-17","Statement":[{"Effect":"Allow",'
                '"Principal":{"Service":"backup.amazonaws.com"},'
                '"Action":"sts:AssumeRole"}]}'
            ),
        )
        iam.attach_role_policy(
            RoleName=nombre,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup",
        )
        return creado["Role"]["Arn"]


def crear() -> None:
    s = _session()
    backup = s.client("backup")
    try:
        backup.create_backup_vault(BackupVaultName=VAULT)
        print("vault creado:", VAULT)
    except backup.exceptions.AlreadyExistsException:
        print("vault ya existe:", VAULT)

    plan = backup.create_backup_plan(
        BackupPlan={
            "BackupPlanName": PLAN,
            "Rules": [{
                "RuleName": "diario",
                "TargetBackupVaultName": VAULT,
                "ScheduleExpression": "cron(0 5 * * ? *)",
                "Lifecycle": {"DeleteAfterDays": RETENTION},
            }],
        }
    )
    plan_id = plan["BackupPlanId"]
    print("plan creado:", plan_id)

    backup.create_backup_selection(
        BackupPlanId=plan_id,
        BackupSelection={
            "SelectionName": "integrai-server",
            "IamRoleArn": _role_arn(),
            "ListOfTags": [{
                "ConditionType": "STRINGEQUALS",
                "ConditionKey": "Backup",
                "ConditionValue": "integrai",
            }],
        },
    )
    print("selección por tag Backup=integrai aplicada")


if __name__ == "__main__":
    cmd = (sys.argv[1:] or ["auditar"])[0]
    if cmd == "auditar":
        auditar()
    elif cmd == "crear":
        crear()
    else:
        sys.exit(__doc__)
