#!/bin/bash
# IntegrAI — toggle del intercept del webhook de WhatsApp
#   ./aplicar.sh on   -> los mensajes del número entran a IntegrAI (Meta→IntegrAI)
#   ./aplicar.sh off  -> se desactiva: Meta vuelve a ir directo a Chatwoot (bot reconectado)
set -euo pipefail
cd "$(dirname "$0")"
case "${1:-}" in
  on)  cp compose-on.yml  docker-compose.yml;  echo "→ SWITCH TOTAL: mensajes a IntegrAI" ;;
  off) cp compose-off.yml docker-compose.yml;  echo "→ REVERTIDO: Chatwoot/bot vuelve a recibir" ;;
  status) echo "Compose activo:"; grep -c integrai-intercept docker-compose.yml >/dev/null && (grep -q '^      - traefik.http.routers.integrai-intercept' docker-compose.yml && echo "  intercept: ON" || echo "  intercept: OFF"); exit 0 ;;
  *) echo "uso: ./aplicar.sh on|off|status"; exit 1 ;;
esac
docker compose up -d
sleep 6
docker ps --format '{{.Names}} {{.Status}}' | grep integrai-webhook
curl -s -o /dev/null -w "  staging health -> %{http_code}\n" https://integrai.wagnersolutionsai.com/health
