#!/usr/bin/env python3
"""KMS + S3 para medios y backups (F1).

    python tools/kms_s3_aws.py auditar
    python tools/kms_s3_aws.py crear

Requiere INTEGRA_S3_BUCKET, opcional INTEGRA_KMS_ALIAS. Sin secretos.
"""
from __future__ import annotations

import os
import sys

REGION = os.getenv("AWS_REGION", "us-east-1")
BUCKET = os.getenv("INTEGRA_S3_BUCKET", "")
KMS_ALIAS = os.getenv("INTEGRA_KMS_ALIAS", "alias/integrai")


def _session():
    return __import__("boto3").Session(region_name=REGION)


def auditar() -> None:
    s = _session()
    kms = s.client("kms")
    try:
        resp = kms.list_aliases()
        for a in resp["Aliases"]:
            if "integrai" in a["AliasName"]:
                print("KMS alias:", a["AliasName"])
    except Exception as e:
        print("KMS ERR:", e)
    s3 = s.client("s3")
    try:
        if BUCKET:
            b = s3.get_bucket_encryption(Bucket=BUCKET)
            print("S3 enc:", BUCKET, b["ServerSideEncryptionConfiguration"])
    except Exception as e:
        print("S3 enc ERR:", e)
    try:
        if BUCKET:
            bl = s3.get_public_access_block(Bucket=BUCKET)
            print("S3 PAB:", bl["PublicAccessBlockConfiguration"])
    except Exception as e:
        print("S3 PAB ERR:", e)


def crear() -> None:
    print("Plan (idempotente sugerido):")
    print("  - Crear CMK KMS:", KMS_ALIAS)
    print("  - Crear bucket S3:", BUCKET, "en", REGION)
    print("  - Block Public Access: BlockAllPublicAccess=True")
    print("  - Cifrado SSE-KMS con CMK; bucket policy TLS-only")
    print("  - Lifecycle: eliminar medios crudos a 24h (medios_tmp/uploads)")
    print("Variables: INTEGRA_S3_BUCKET, INTEGRA_KMS_ALIAS (opcional)")


if __name__ == "__main__":
    cmd = (sys.argv[1:] or ["auditar"])[0]
    if cmd == "auditar":
        auditar()
    elif cmd == "crear":
        crear()
    else:
        sys.exit(__doc__)
