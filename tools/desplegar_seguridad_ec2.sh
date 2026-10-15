#!/bin/bash
# Activa los controles de seguridad del servicio de decisión en integra-server.
# Se ejecuta EN la EC2 (por SSM), con el código de main ya desplegado en /opt/integra.
#
#   sudo bash tools/desplegar_seguridad_ec2.sh
#
# 1. Lee el token de la API desde Secrets Manager (integrai/api-token) -> /etc/integrai/seguridad.env (600)
# 2. Agrega EnvironmentFile a integra-webapi.service (drop-in, no edita la unidad original)
# 3. Reinicia el servicio y verifica: /health 200, /docs 404, /clasificar sin token 401
#
# IMPORTANTE: después de esto el webhook necesita el MISMO token (INTEGRA_API_TOKEN) o recibirá 401.
set -euo pipefail
REGION="${AWS_REGION:-us-east-1}"
PY=/opt/integra/.venv/bin/python

mkdir -p /etc/integrai && chmod 700 /etc/integrai
TOKEN=$($PY -c "import boto3;print(boto3.client('secretsmanager',region_name='$REGION').get_secret_value(SecretId='integrai/api-token')['SecretString'])")
umask 077
cat > /etc/integrai/seguridad.env <<EOF
INTEGRA_API_TOKEN=$TOKEN
U2_CONDUCTAS=1
INTEGRA_DOCS=0
DIR_MEDIOS=/opt/integra/medios_tmp
EOF
unset TOKEN
mkdir -p /opt/integra/medios_tmp && chmod 700 /opt/integra/medios_tmp

mkdir -p /etc/systemd/system/integra-webapi.service.d
cat > /etc/systemd/system/integra-webapi.service.d/seguridad.conf <<'EOF'
[Service]
EnvironmentFile=/etc/integrai/seguridad.env
EOF
systemctl daemon-reload
systemctl restart integra-webapi
sleep 8

echo -n "health: ";      curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/health
echo -n "docs (404): ";  curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/docs
echo -n "sin token (401): "; curl -s -o /dev/null -w "%{http_code}\n" -X POST "http://127.0.0.1:8000/clasificar?texto=x"
