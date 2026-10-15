#!/usr/bin/env python3
"""CloudWatch: log groups y alarmas básicas del servidor (Docs/PLAN.md §2, Ivan).

    python tools/cloudwatch_aws.py auditar
    python tools/cloudwatch_aws.py crear

Variables:
    AWS_REGION                 us-east-1 por defecto
    INTEGRA_INSTANCE_ID        habilita alarmas de la instancia
    INTEGRA_DLQ_NAME           cola DLQ a vigilar (default integrai-dlq)
    INTEGRA_ALARM_EMAIL        correo para el topic SNS (opcional)
    INTEGRA_ALARM_TOPIC_ARN    topic existente (si no, se crea integrai-alarmas)

Sin secretos ni IDs en el repo.
"""
from __future__ import annotations

import os
import sys

REGION = os.getenv("AWS_REGION", "us-east-1")
IID = os.getenv("INTEGRA_INSTANCE_ID", "")
DLQ = os.getenv("INTEGRA_DLQ_NAME", "integrai-dlq")
EMAIL = os.getenv("INTEGRA_ALARM_EMAIL", "")
TOPIC_ARN = os.getenv("INTEGRA_ALARM_TOPIC_ARN", "")
TOPIC_NAME = "integrai-alarmas"

# (nombre, retención en días)
LOG_GROUPS = [("/integra/app", 30), ("/integra/auditoria", 730)]


def _session():
    import boto3

    return boto3.Session(region_name=REGION)


def _configuracion_alarmas(instance_id: str, dlq: str, topic_arn: str) -> list[dict]:
    """Alarmas de la instancia y de la DLQ (aliases de etiqueta para legibilidad)."""
    alarmas: list[dict] = []

    def accion() -> list[str]:
        return [topic_arn] if topic_arn else []

    alarmas.append({
        "AlarmName": "integrai-dlq-mensajes",
        "AlarmDescription": "Mensajes visibles en la DLQ (IntegrAI)",
        "Namespace": "AWS/SQS",
        "MetricName": "ApproximateNumberOfMessagesVisible",
        "Dimensions": [{"Name": "QueueName", "Value": dlq}],
        "Statistic": "Maximum",
        "Period": 300,
        "EvaluationPeriods": 1,
        "Threshold": 1,
        "ComparisonOperator": "GreaterThanOrEqualToThreshold",
        "TreatMissingData": "notBreaching",
        "AlarmActions": accion(),
    })
    if instance_id:
        alarmas.append({
            "AlarmName": "integrai-statuscheck",
            "AlarmDescription": "Estado de la instancia integra-server",
            "Namespace": "AWS/EC2",
            "MetricName": "StatusCheckFailed",
            "Dimensions": [{"Name": "InstanceId", "Value": instance_id}],
            "Statistic": "Maximum",
            "Period": 300,
            "EvaluationPeriods": 2,
            "Threshold": 1,
            "ComparisonOperator": "GreaterThanOrEqualToThreshold",
            "TreatMissingData": "breaching",
            "AlarmActions": accion(),
        })
        alarmas.append({
            "AlarmName": "integrai-cpu",
            "AlarmDescription": "CPU alta en integra-server",
            "Namespace": "AWS/EC2",
            "MetricName": "CPUUtilization",
            "Dimensions": [{"Name": "InstanceId", "Value": instance_id}],
            "Statistic": "Average",
            "Period": 300,
            "EvaluationPeriods": 3,
            "Threshold": 85,
            "ComparisonOperator": "GreaterThanOrEqualToThreshold",
            "TreatMissingData": "notBreaching",
            "AlarmActions": accion(),
        })
    return alarmas


def _topic(s) -> str:
    if TOPIC_ARN:
        return TOPIC_ARN
    cw = s.client("cloudwatch")
    s3 = s.client("sns")
    creado = s3.create_topic(Name=TOPIC_NAME)
    arn = creado["TopicArn"]
    if EMAIL:
        s3.subscribe(TopicArn=arn, Protocol="email", Endpoint=EMAIL)
        print("suscripción pendiente de confirmación:", EMAIL)
    return arn


def auditar() -> None:
    s = _session()
    logs = s.client("logs")
    for nombre, retencion in LOG_GROUPS:
        try:
            r = logs.describe_log_groups(logGroupNamePrefix=nombre)["logGroups"]
            igual = [g for g in r if g["logGroupName"] == nombre]
            if igual:
                print("OK ", nombre, "retención:", igual[0].get("retentionInDays"), f"(esperado {retencion})")
            else:
                print("-- ", nombre, "(no existe)")
        except Exception as e:
            print("-- ", nombre, e)
    cw = s.client("cloudwatch")
    estados = {a["AlarmName"]: a["StateValue"] for a in cw.describe_alarms()["MetricAlarms"]}
    if estados:
        for nombre, estado in sorted(estados.items()):
            print("OK " if estado != "ALARM" else "-- ", "alarma", nombre, estado)
    else:
        print("-- sin alarmas")


def crear() -> None:
    s = _session()
    logs = s.client("logs")
    for nombre, retencion in LOG_GROUPS:
        try:
            logs.create_log_group(logGroupName=nombre)
            print("creado log group:", nombre)
        except logs.exceptions.ResourceAlreadyExistsException:
            print("log group ya existe:", nombre)
        logs.put_retention_policy(logGroupName=nombre, retentionInDays=retencion)

    topic_arn = _topic(s)
    cw = s.client("cloudwatch")
    for alarma in _configuracion_alarmas(IID, DLQ, topic_arn):
        cw.put_metric_alarm(**alarma)
        print("alarma aplicada:", alarma["AlarmName"])
    print("topic:", topic_arn)


if __name__ == "__main__":
    cmd = (sys.argv[1:] or ["auditar"])[0]
    if cmd == "auditar":
        auditar()
    elif cmd == "crear":
        crear()
    else:
        sys.exit(__doc__)
