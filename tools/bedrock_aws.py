#!/usr/bin/env python3
"""Bedrock: VPC endpoint + verificación de logging (F1).

    python tools/bedrock_aws.py auditar
    python tools/bedrock_aws.py crear

Requiere VPC_ID, SUBNET_IDS, SG_ID (opcionales).
"""
from __future__ import annotations

import os
import sys

REGION = os.getenv("AWS_REGION", "us-east-1")
VPC = os.getenv("INTEGRA_VPC_ID", "")
SUBNETS = os.getenv("INTEGRA_SUBNET_IDS", "")
SG = os.getenv("INTEGRA_SG_ID", "")


def _session():
    return __import__("boto3").Session(region_name=REGION)


def auditar() -> None:
    s = _session()
    ec2 = s.client("ec2")
    try:
        eps = ec2.describe_vpc_endpoints(Filters=[{"Name": "service-name", "Values": [f"com.amazonaws.{REGION}.bedrock-runtime"]}])
        print("bedrock-runtime endpoint:", len(eps["VpcEndpoints"]))
    except Exception as e:
        print("EP ERR:", e)
    logs = s.client("logs")
    try:
        groups = logs.describe_log_groups(logGroupNamePrefix="/aws/bedrock")
        print("Bedrock log groups:", len(groups["logGroups"]))
    except Exception as e:
        print("Logs ERR:", e)


def crear() -> None:
    print("Plan:")
    print("  - Crear VPC endpoint interface para bedrock-runtime")
    print("  - Subnets:", SUBNETS or "(no definidas)")
    print("  - SG:", SG or "(no definido)")
    print("  - Verificar invocation logging desactivado (mantener como está)")
    print("Variables: INTEGRA_VPC_ID, INTEGRA_SUBNET_IDS (csv), INTEGRA_SG_ID")


if __name__ == "__main__":
    cmd = (sys.argv[1:] or ["auditar"])[0]
    if cmd == "auditar":
        auditar()
    elif cmd == "crear":
        crear()
    else:
        sys.exit(__doc__)
