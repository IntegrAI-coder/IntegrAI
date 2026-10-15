#!/bin/bash
# endurecer_servicios_ec2.sh
# Activa ejecución de servicios sin root (F0). Ejecutar EN la EC2 con sudo.
set -euo pipefail

SERVICES=("integra-webapi.service" "integra.service")

if [[ $EUID -ne 0 ]]; then
  echo "Debe ejecutarse con sudo" >&2
  exit 1
fi

if ! id -u integra >/dev/null 2>&1; then
  useradd -r -s /usr/sbin/nologin -m integra
  echo "Usuario integra creado"
else
  echo "Usuario integra ya existe"
fi

for svc in "${SERVICES[@]}"; do
  mkdir -p /etc/systemd/system/${svc}.d
  cat > /etc/systemd/system/${svc}.d/sin-root.conf <<EOF
[Service]
User=integra
Group=integra
WorkingDirectory=/opt/integra
EOF
  echo "Drop-in creado para ${svc}"
done

chown -R integra:integra /opt/integra/medios_tmp 2>/dev/null || true
chown -R integra:integra /opt/integra 2>/dev/null || true
chmod -R o-rwx /opt/integra 2>/dev/null || true

systemctl daemon-reload
for svc in "${SERVICES[@]}"; do
  systemctl restart "${svc}" || echo "WARN: no pudo reiniciar ${svc} (quizá no instalado aún)"
done

for svc in "${SERVICES[@]}"; do
  systemctl status "${svc}" --no-pager -l | head -15
done

ps -eo pid,user,comm | grep integra || true
echo "Listo. Verifica User=integra en cada servicio." 
