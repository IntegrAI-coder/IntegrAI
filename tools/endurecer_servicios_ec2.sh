#!/bin/bash
# endurecer_servicios_ec2.sh
# Ejecuta los servicios de IntegrAI sin root (F0). Ejecutar EN la EC2 con sudo, en una ventana coordinada.
#
#   sudo bash tools/endurecer_servicios_ec2.sh          # aplicar
#   sudo bash tools/endurecer_servicios_ec2.sh revertir # volver a root (emergencia)
#
# Cuidados (revisados el 15-oct):
#  - Streamlit escucha en :80: sin root necesita CAP_NET_BIND_SERVICE o no levanta.
#  - Whisper y Laya tienen ~2,7 GB de modelos en /root/.cache/huggingface: se copian a una caché
#    compartida (HF_HOME) para que el usuario `integra` no los vuelva a descargar.
#  - /etc/integrai/seguridad.env (token de la API) lo lee systemd como root antes de bajar privilegios.
set -euo pipefail

SERVICES=("integra-webapi.service" "integra.service")
CACHE=/opt/integra/.cache/huggingface

if [[ $EUID -ne 0 ]]; then
  echo "Debe ejecutarse con sudo" >&2
  exit 1
fi

if [[ "${1:-}" == "revertir" ]]; then
  for svc in "${SERVICES[@]}"; do rm -f "/etc/systemd/system/${svc}.d/sin-root.conf"; done
  systemctl daemon-reload
  for svc in "${SERVICES[@]}"; do systemctl restart "$svc"; done
  echo "Revertido: los servicios vuelven a correr como root."
  exit 0
fi

if ! id -u integra >/dev/null 2>&1; then
  useradd -r -s /usr/sbin/nologin -m integra
  echo "Usuario integra creado"
else
  echo "Usuario integra ya existe"
fi

# caché de modelos compartida (evita re-descargar 2,7 GB y fallos sin internet)
mkdir -p "$CACHE"
if [[ -d /root/.cache/huggingface ]] && [[ -z "$(ls -A "$CACHE" 2>/dev/null)" ]]; then
  cp -a /root/.cache/huggingface/. "$CACHE"/
  echo "Modelos copiados a $CACHE"
fi

for svc in "${SERVICES[@]}"; do
  mkdir -p "/etc/systemd/system/${svc}.d"
  cat > "/etc/systemd/system/${svc}.d/sin-root.conf" <<EOF
[Service]
User=integra
Group=integra
WorkingDirectory=/opt/integra
Environment=HF_HOME=$CACHE
Environment=XDG_CACHE_HOME=/opt/integra/.cache
# permite escuchar en :80 sin ser root (solo esa capacidad)
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
NoNewPrivileges=true
EOF
  echo "Drop-in creado para ${svc}"
done

mkdir -p /opt/integra/medios_tmp
chown -R integra:integra /opt/integra
chmod -R o-rwx /opt/integra
chmod 700 /opt/integra/medios_tmp

systemctl daemon-reload
for svc in "${SERVICES[@]}"; do
  systemctl restart "${svc}" || echo "WARN: no pudo reiniciar ${svc}"
done
sleep 8

fallo=0
for svc in "${SERVICES[@]}"; do
  usuario=$(ps -o user= -p "$(systemctl show -p MainPID --value "$svc")" 2>/dev/null || echo "?")
  activo=$(systemctl is-active "$svc" || true)
  echo "$svc: $activo (usuario: $usuario)"
  [[ "$activo" == "active" && "$usuario" == "integra" ]] || fallo=1
done
echo -n "dashboard :80 -> "; curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:80/ || true
echo -n "API /health  -> "; curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/health || true

if [[ $fallo -ne 0 ]]; then
  echo "ALGO FALLÓ: revisa 'journalctl -u <servicio> -n 50'. Para volver atrás: sudo bash $0 revertir" >&2
  exit 1
fi
echo "Listo: servicios sin root."
