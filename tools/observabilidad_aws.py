#!/usr/bin/env python3
"""Observabilidad: CloudTrail, GuardDuty, Security Hub, AWS Config (F1).

    python tools/observabilidad_aws.py auditar  # solo lectura
    python tools/observabilidad_aws.py crear    # idempotente (guía + intentos seguros)

No toca cuentas críticas; solo lectura/guía en muchos casos. Usa variables:
AWS_REGION, INTEGRA_CLOUDTRAIL_BUCKET, INTEGRA_SNS_TOPIC
"""
from __future__ import annotations

import os
import sys

REGION = os.getenv("AWS_REGION", "us-east-1")
CT_BUCKET = os.getenv("INTEGRA_CLOUDTRAIL_BUCKET", "")


def auditar() -> None:
    s = __import__("boto3").Session(region_name=REGION)
    ct = s.client("cloudtrail")
    try:
        trails = ct.describe_trails()["trailList"]
        print("CloudTrail:", len(trails))
        for t in trails[:3]:
            print(" ", t["Name"], t.get("IsMultiRegionTrail"), t.get("LogFileValidationEnabled"))
    except Exception as e:
        print("CloudTrail ERR:", e)
    gd = s.client("guardduty")
    try:
        det = gd.list_detectors()["DetectorIds"]
        print("GuardDuty detectors:", det)
    except Exception as e:
        print("GuardDuty ERR:", e)
    sh = s.client("securityhub")
    try:
        sts = sh.get_enabled_standards()
        print("SecurityHub standards:", [x["StandardsArn"] for x in sts["StandardsSubscriptions"]])
    except Exception as e:
        print("SecurityHub ERR:", e)
    cfg = s.client("config")
    try:
        rec = cfg.describe_configuration_recorders()
        print("Config recorders:", [x["name"] for x in rec["ConfigurationRecorders"]])
    except Exception as e:
        print("Config ERR:", e)


def crear() -> None:
    print("Creación idempotente sugerida (solo preparación):")
    print("  - CloudTrail multiregión + validación logs en bucket S3")
    print("  - GuardDuty habilitar detector (si no existe)")
    print("  - Security Hub habilitar + CIS/FSBP (si disponible)")
    print("  - AWS Config recorder + delivery channel (si bucket existe)")
    print("Variables: INTEGRA_CLOUDTRAIL_BUCKET")


if __name__ == "__main__":
    cmd = (sys.argv[1:] or ["auditar"])[0]
    if cmd == "auditar":
        auditar()
    elif cmd == "crear":
        crear()
    else:
        sys.exit(__doc__)
