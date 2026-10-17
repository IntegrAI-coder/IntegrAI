# Política de seguridad

IntegrAI es un repositorio **público**. El proyecto maneja datos de contexto sensible
(observaciones sobre niños y niñas); por diseño, el dataset del repositorio es **100% sintético**.

## Cómo reportar una vulnerabilidad

- **NO** abras un issue público para reportar vulnerabilidades.
- Repórtala en privado con **GitHub Security Advisories**
  (`Security → Report a vulnerability`) o contacta al responsable: `@icortesve`.
- Incluye: descripción, pasos para reproducir, impacto y, si puedes, una corrección sugerida.
- Plazo objetivo de respuesta: **72 h**.

## Reglas del repositorio

- **Nunca** subir secretos: tokens, `.env`, llaves AWS/PEM ni material privado de Integra.
  Los secretos viven en **AWS Secrets Manager**.
- El CI bloquea con **Gitleaks** si detecta un secreto y, además, corre un **escaneo de PII**.
- Los datos personales (nombres, teléfonos, IPs, RUT) **no** se versionan:
  usa identificadores sintéticos (`EDU-0001`, `NINO-00001`).

## Alcance

Aplica a este repositorio y a los servicios desplegados
(webhook de WhatsApp, servicio de decisión en EC2, distribución CloudFront).
