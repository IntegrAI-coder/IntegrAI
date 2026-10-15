#!/usr/bin/env python3
"""Sube un archivo local a la EC2 vía SSM (base64).

uso: python3 tools/ssm_push.py <local> <remoto> [--mkdir]
"""
import base64, sys
from ssm import run

if __name__ == "__main__":
    local, remoto = sys.argv[1], sys.argv[2]
    mkdir = "--mkdir" in sys.argv
    data = base64.b64encode(open(local, "rb").read()).decode()
    pre = f"mkdir -p $(dirname {remoto}); " if mkdir else ""
    cmd = f"{pre}echo '{data}' | base64 -d > {remoto} && wc -c {remoto}"
    st, out = run(cmd)
    print(f"[{st}] {local} -> {remoto}")
    print(out.strip())
