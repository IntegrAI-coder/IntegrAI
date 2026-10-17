# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/);
versionado semántico.

## [Unreleased]

### Por hacer

- Corte de seguridad: activar token de la API, cerrar 80/8000 a solo-CloudFront,
  WAF + Basic auth, rol IAM mínimo, servicios sin root, EBS cifrado.
- Desplegar la infraestructura como código (`infra/integra-server.yaml`).
- Activar GitHub Pages del frontend.
- Validar umbrales del recomendador RAG.

## [0.1.0] - 2026-10-17

### Añadido

- Pipeline completo: WhatsApp → U2 multimodal (post-it/audio/video) → clasificación por
  rúbrica de Integra → compuerta → cola "por verificar" (human-in-the-loop).
- Webhook WhatsApp Cloud API (firma HMAC fail-closed, whitelist, logs sin PII).
- Dashboards: React (`frontend/`) y Streamlit (`app.py`).
- Recomendador RAG (demo estática) con citas OMS/CDC/MINEDUC.
- Infraestructura y seguridad como código (`infra/`, `tools/*_aws.py`): CloudFront + TLS,
  Secrets Manager, IAM, WAF, EBS, CloudWatch, Budgets.
- CI bloqueante: Gitleaks + pytest + pip-audit.

### Seguridad

- Secretos en AWS Secrets Manager; escáner de PII/secretos en la ingesta.
- Gobierno de datos según Ley 21.719 (revisión humana de cada clasificación).
