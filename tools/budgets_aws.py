#!/usr/bin/env python3
"""AWS Budgets: alerta de gasto en Bedrock (F1).

    python tools/budgets_aws.py auditar
    python tools/budgets_aws.py crear

Requiere INTEGRA_BUDGET_AMOUNT y opcional INTEGRA_EMAIL.
"""
from __future__ import annotations

import os
import sys

REGION = os.getenv("AWS_REGION", "us-east-1")
AMOUNT = os.getenv("INTEGRA_BUDGET_AMOUNT", "")
EMAIL = os.getenv("INTEGRA_EMAIL", "")


def _session():
    return __import__("boto3").Session(region_name=REGION)


def auditar() -> None:
    try:
        b = _session().client("budgets", region_name="us-east-1")
        res = b.describe_budgets(AccountId=_acct())["Budgets"]
        for x in res:
            if "bedrock" in x["BudgetName"].lower():
                print("Bedrock budget:", x["BudgetName"], x["BudgetLimit"])
    except Exception as e:
        print("Budgets ERR:", e)


def _acct():
    return __import__("boto3").client("sts").get_caller_identity()["Account"]


def crear() -> None:
    print("Plan:")
    print("  - Crear presupuesto 'integrai-bedrock' con umbral", AMOUNT or "(no definido)")
    print("  - Alertas + SNS a", EMAIL or "(sin email)")
    print("  - Filtro por servicio Bedrock (o tags)")


if __name__ == "__main__":
    cmd = (sys.argv[1:] or ["auditar"])[0]
    if cmd == "auditar":
        auditar()
    elif cmd == "crear":
        crear()
    else:
        sys.exit(__doc__)
