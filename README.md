# IntegrAI

Hackathon AWS Breaking Barriers Chile 2026 — **Desafío 1 de Fundación Integra**: IA para el desarrollo infantil, de la observación a la acción.

Asistente de WhatsApp para tías de jardín. La tía envía una observación (texto, foto de un post-it, nota de voz o video) y el sistema la transcribe, identifica al niño/a y **propone un nivel de desarrollo** con evidencia del catálogo, usando Claude en Amazon Bedrock con una salida validada por Pydantic. La tía responde **Confirmar / Ajustar / Cancelar**, y solo su confirmación actualiza el nivel del niño/a.

**KPI:** bajar el tiempo de documentación de 4 h/semana por tía a casi 0.

> Datos 100 % sintéticos. La ruta de niveles es una síntesis para la hackathon; no es un instrumento clínico, diagnóstico ni validado. Toda clasificación es una propuesta para el criterio de la educadora.

## Estructura

| Carpeta | Contenido |
|---|---|
| `data/` | Dataset sintético E-1 (7 CSV): jardines, educadoras, niños/as, niveles, manifestaciones, observaciones y vínculos |
| `docs/` | `PLAN.md` (plan del equipo y tareas por persona), `diccionario_datos.md`, `resumen_deck.md` |
| `contracts/` | JSON Schema entre unidades (se congela al final de la Inception) |
| `.kiro/steering/` | Contexto para Kiro (product, tech, structure) |

## Arquitectura (resumen)

```
WhatsApp → API Gateway + Lambda (firma + whitelist) → SQS → Worker
  → Normalizar (Transcribe · visión post-it · video Nova) → Clasificador (Bedrock + Pydantic)
  → Sesión (Confirmar / Ajustar / Cancelar) → Commit en DynamoDB (nivel + auditoría)
```

Stack: Python 3.12, AWS SAM, Lambda, SQS, S3, DynamoDB, Amazon Transcribe, Amazon Bedrock (`us.anthropic.claude-sonnet-5`, `us.amazon.nova-pro-v1:0`) y Meta WhatsApp Cloud API.

## Reglas del repo

- Repo **público**: nunca subir tokens, `.env` ni llaves AWS. Los secretos van en AWS Secrets Manager.
- Branches `u1-…` a `u5-…`, squash merge, `main` siempre desplegable.
- Ver `docs/PLAN.md` para unidades, responsables y cronograma.
