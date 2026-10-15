#!/usr/bin/env python3
"""Auditoría de residencia/región de recursos (F2).

    python tools/region_audit.py auditar
"""
from __future__ import annotations

import os
import sys

REGION = os.getenv("AWS_REGION", "us-east-1")


def auditar() -> None:
    s = __import__("boto3").Session(region_name=REGION)
    sts = s.client("sts")
    print("Account:", sts.get_caller_identity()["Account"])
    print("Default region:", REGION)
    print("Revisa: S3 buckets (location), EBS volúmenes, CloudTrail trails, DynamoDB, RDS, Bedrock endpoints")
    print("Ver docs/TRANSFERENCIA_INTERNACIONAL.md para checklist legal.")


if __name__ == "__main__":
    auditar()
