#!/usr/bin/env python3
"""Ejecuta un comando shell en la EC2 IntegrAI vía AWS SSM.

uso:  python3 tools/ssm.py "comando; otro"
      echo "cmd" | python3 tools/ssm.py -
"""
import os, sys, time, boto3

REGION = os.getenv("AWS_REGION", "us-east-1")
IID = os.getenv("INTEGRA_INSTANCE_ID", "")   # no se versiona el ID de la instancia (repo público)
if not IID:
    sys.exit("define INTEGRA_INSTANCE_ID con el ID de la EC2")


def run(script: str, timeout: int = 120) -> tuple[str, str]:
    ssm = boto3.client("ssm", region_name=REGION)
    r = ssm.send_command(InstanceIds=[IID], DocumentName="AWS-RunShellScript",
                         Parameters={"commands": [script]}, TimeoutSeconds=timeout)
    cid = r["Command"]["CommandId"]
    for _ in range(timeout):
        time.sleep(2)
        try:
            o = ssm.get_command_invocation(CommandId=cid, InstanceId=IID)
        except Exception:
            continue
        if o["Status"] in ("Success", "Failed", "Cancelled", "TimedOut"):
            return o["Status"], o.get("StandardOutputContent", "") + (("\n[ERR] " + o["StandardErrorContent"]) if o.get("StandardErrorContent") else "")
    return "PENDING", ""


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] != "-":
        cmd = " ".join(sys.argv[1:])
    else:
        cmd = sys.stdin.read()
    st, out = run(cmd)
    print(f"[{st}]")
    print(out)
