"""Tests de la configuración de CloudWatch (sin credenciales AWS).

Solo cubre las funciones puras: log groups y alarmas.
"""

import importlib.util
from pathlib import Path

RUTA = Path(__file__).resolve().parent.parent / "tools" / "cloudwatch_aws.py"
_spec = importlib.util.spec_from_file_location("cloudwatch_aws", RUTA)
cw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cw)


def test_log_groups_y_retencion():
    grupos = dict(cw.LOG_GROUPS)
    assert grupos["/integra/app"] == 30
    assert grupos["/integra/auditoria"] == 730


def test_alarma_dlq_sin_instancia():
    alarmas = cw._configuracion_alarmas("", "mi-dlq", "arn:aws:sns:us-east-1:1:t")
    nombres = {a["AlarmName"] for a in alarmas}
    assert nombres == {"integrai-dlq-mensajes"}
    dlq = alarmas[0]
    assert dlq["Dimensions"] == [{"Name": "QueueName", "Value": "mi-dlq"}]
    assert dlq["AlarmActions"] == ["arn:aws:sns:us-east-1:1:t"]


def test_alarmas_instancia():
    alarmas = cw._configuracion_alarmas("i-123", "integrai-dlq", "")
    nombres = {a["AlarmName"] for a in alarmas}
    assert nombres == {"integrai-dlq-mensajes", "integrai-statuscheck", "integrai-cpu"}
    assert all(a["AlarmActions"] == [] for a in alarmas)
