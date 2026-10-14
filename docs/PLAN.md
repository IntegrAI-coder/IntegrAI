# IntegrAI — Plan de equipo (v2)

Desafío 1 de Fundación Integra, Breaking Barriers 2026 (14–16 oct). Repo: <https://github.com/IntegrAI-coder/IntegrAI>

Esta versión toma el plan seccionado hecho en Kiro (*IntegrAI — Plan, Kiro prompt and team methodology*, @Santiago) y lo corrige con lo que verificamos en la cuenta AWS del evento. Mantiene la arquitectura, las 5 unidades (U1–U5), el contrato `Classification` y el método AI-DLC. Los cambios están en la sección 1.

## 0. Qué construimos (resumen)

Una tía envía por WhatsApp una observación (texto, foto de post-it, nota de voz o video). El sistema la convierte a texto, identifica al niño/a dentro del jardín de esa tía y propone **un nivel** con evidencia del catálogo. La salida se valida con Pydantic ("typesafe"). La tía responde **Confirmar / Ajustar / Cancelar**. Solo su confirmación cambia el nivel del niño/a. KPI: bajar el tiempo de documentación de 4 h/semana a casi 0.

```
Tía (WhatsApp) → U1 Gateway (firma + whitelist) → SQS → Worker
   → U2 Normalizar (texto | Transcribe | visión post-it | video) → U3 Clasificador (Bedrock + Pydantic)
   → U4 Sesión (propuesta + botones; Ajustar re-clasifica, máx. 3 rondas)
   → U5 Commit (observación + evidencia + nivel actual + auditoría, en una transacción)
```

## 1. Correcciones al plan de Kiro

| # | Plan de Kiro | Corrección | Motivo |
|---|---|---|---|
| 1 | "Claude on Bedrock" sin modelo fijo | **Clasificador y visión: `us.anthropic.claude-sonnet-5`**. Generar mensajes sintéticos para la evaluación: `us.anthropic.claude-haiku-4-5-20251001-v1:0`. Video: `us.amazon.nova-pro-v1:0`. Fallback: `us.anthropic.claude-sonnet-4-6` | La cuenta del evento tiene una lista de modelos permitidos (`ws-bedrock-model-allowlist-policy-1`). **Sonnet 5.5 y Haiku 5.5 dan AccessDenied.** Siempre usar el ID con prefijo `us.` (inference profile). |
| 2 | Video: capa ffmpeg en Lambda + 4 keyframes | **Sin ffmpeg**: Transcribe recibe el `.mp4` directo para el audio, y Nova Pro describe el video desde S3. ffmpeg queda solo como plan B | Ahorra unas 2 h de U2 (compilar la capa, límites de tamaño). Los videos de WhatsApp pesan como máximo 16 MB. |
| 3 | Credenciales para desplegar no definidas | Desplegar `sam deploy` **desde el Code Editor del evento o el escritorio Kiro RDP**, que usan rol de instancia sin vencimiento. Desde un PC local se usan las llaves STS del Workshop Studio, que **vencen en pocas horas** | Las llaves locales expiran a mitad del trabajo. |
| 4 | — | Hay una instancia EC2 **`integra-server`** (i-0226f28f9b99716f2, Ubuntu 24.04, puertos 8000/8501 abiertos) con código del equipo. **Decidir hoy (14-oct) en la Inception** si se integra a la arquitectura serverless (por ejemplo, para el dashboard) o se apaga | Evita tener dos backends. Además, tener 22/8000/8501 abiertos a `0.0.0.0/0` es un riesgo: cerrar 22 y usar SSM. |
| 5 | "Ningún nombre ni foto de niños fuera de AWS" | Agregar: los medios **pasan por Meta** igual, porque WhatsApp es el canal. Mitigación: los niños/as se identifican solo por código o apodo en el roster, nunca con RUT. Descargar cada medio una sola vez a S3 cifrado (30 días). Opcional: Bedrock Guardrail con anonimización de PII antes de guardar el texto. Mencionar la Ley 21.719 en el pitch | Es la pregunta de privacidad que harán los jurados. |
| 6 | Dashboard "después de la hackathon" | **Dashboard mínimo como stretch del día 16** (P4): tabla por sala con nivel actual vs. nivel esperado por edad, y alerta de rezago. Una página estática que lee desde una Lambda | Así se ve "poner al niño en su nivel", y el deck pide identificar rezago. |
| 7 | Evidencia "dentro de ±1 del nivel" | Mantener ±1 en la validación, pero **marcar `confianza=baja` si alguna evidencia no es del nivel exacto**. Medir los dos casos en la evaluación | En el dataset, cada observación se vincula solo con manifestaciones de su nivel exacto. |
| 8 | Repo con los CSV en `/data` | El repo es **PÚBLICO**: (a) nunca subir `.env`, el token de Meta ni llaves AWS (agregar `.gitignore` y usar Secrets Manager); (b) confirmar con la organización si se puede publicar el dataset, o dejar el repo privado durante el evento. **Nunca** subir `dataset_e1_validacion_interna.zip` | El README del dataset restringe su distribución. |
| 9 | Python 3.12, SAM | Se mantiene. Lambda `python3.12`, Pydantic v2 empaquetado con `sam build --use-container`, o en una capa con wheels `manylinux` | `pydantic_core` es binario; un build desde Windows sin contenedor falla en Lambda. |
| 10 | Presupuesto Kiro "10,000" | Con **Kiro Pro** ya activo, son créditos, no tokens. El reparto por unidad sigue igual | Aclara la duda que quedó abierta en el plan de Kiro. |

## 2. Equipo y responsabilidades

Reemplazar P1–P4 por los nombres reales.

| Persona | Rol | Unidades | Además |
|---|---|---|---|
| **P1** (¿Santiago?) | Lead y conductor AI-DLC | **U3 Clasificador** | Steering files, aprobación de gates, presupuesto Kiro, pitch |
| **P2** | Integración | **U1 Gateway** + **U4 Conversación** | App de Meta y número de prueba, webhook, botones, máquina de estados |
| **P3** | Multimodal | **U2 Normalización** | Transcribe, prompt de visión para post-its, video con Nova, medios de prueba |
| **P4** | Datos, infraestructura y QA | **U5 Datos, commit y evaluación** | Stack SAM, DynamoDB, seed, evaluación de 200 casos, runbook, dashboard (stretch) |

## 3. Tareas por persona y por día

### Martes 14-oct (tarde/noche) — Inception, ~3 h, los 4 juntos

| Tarea | Responsable | Listo cuando |
|---|---|---|
| Subir al repo `/data` (los 7 CSV), `/docs` (diccionario y resumen del deck), `.gitignore` y `README` | P4 | Merge en `main`, sin secretos |
| Steering files `.kiro/steering/{product,tech,structure}.md` desde el master prompt, **con las correcciones 1, 2, 5 y 7 de arriba** | P1 | Commit |
| Correr `/aidlc` y aprobar requisitos, historias, diseño y unidades | P1 conduce, todos aprueban | Gates aprobados en Kiro |
| Congelar `/contracts` (JSON Schema): `InboundMessage`, `NormalizedObservation{text, source_type, media_s3_key}`, `Classification`, `SessionState`, `CommitRecord` | P1 + dueño de cada unidad | Commit; desde aquí, cambios solo con P1 |
| Decidir qué hacer con `integra-server` (corrección 4) | Todos | Decisión escrita en `/docs/decisiones.md` |
| Crear la app de Meta y el número de prueba, registrar los 4 teléfonos, generar el verify token | P2 | Un mensaje de prueba llega a un teléfono del equipo |
| Verificar Bedrock: una llamada a `us.anthropic.claude-sonnet-5` desde el Code Editor | P1 | Respuesta OK |
| Grabar los medios de demo: 2 post-its escritos a mano y fotografiados, 2 notas de voz y 1 video de 15–20 s (con un "niño" de juguete o una descripción, **sin niños reales**) | P3 | Archivos en `/samples` (o en S3 si pesan) |

### Miércoles 15-oct — Construction, ~10 h, en paralelo

| Hora (aprox.) | P1 — U3 | P2 — U1 + U4 | P3 — U2 | P4 — U5 |
|---|---|---|---|---|
| Bolt 1 (09–12) | `LevelEnum` y `DomainEnum` construidos desde la tabla `levels`. Modelo Pydantic `Classification`. Prompt en español con el catálogo completo (90 manifestaciones) | Webhook: GET verify, POST con firma `X-Hub-Signature-256`, whitelist `authorized_staff`, idempotencia por `message.id`, envío a SQS + DLQ | Texto pass-through. Descarga de medios desde la Graph API a S3. Audio OGG → Transcribe `es-US` | **Primero (1 h):** template SAM base (tablas, S3, SQS, secretos), seed de los CSV y `authorized_staff` con los 4 teléfonos. Después: loaders de `levels` y del catálogo |
| Bolt 2 (13–16) | Converse con tool forzada. 1 reintento si `ValidationError`, luego `needs_review`. Post-checks: IDs del catálogo, nivel exacto/±1, ventana de edad con holgura | Máquina de estados `IDLE → AWAITING_CHILD → CLASSIFYING → AWAITING_CONFIRMATION → (ADJUSTING → CLASSIFYING)* → COMMITTED / CANCELLED / EXPIRED`. TTL de 24 h | Post-it: visión con Sonnet 5 que devuelve texto limpio. Video: Transcribe mp4 + Nova Pro | Commit con `TransactWriteItems`: observación, evidencia, nivel actual y auditoría (tía, antes, después, modelo, versión del prompt) |
| Bolt 3 (16–19) | Ajustar: re-clasificar con el feedback de la tía (texto o audio vía U2) | Botones Confirmar / Ajustar / Cancelar. Resolver al niño/a contra el roster del jardín y preguntar si hay ambigüedad. Todos los mensajes dicen "propuesta para tu criterio" | Pruebas con los medios de `/samples`. Manejo de errores (medio ilegible → pedir nota de voz) | `eval.py`: 200 mensajes sintéticos generados con Haiku 4.5 desde las observaciones + manifestaciones + `nota_breve` |
| Integración (19–20) | Revisión de contratos | Prueba E2E de texto en un teléfono real | Prueba E2E de audio y post-it | Corre el E2E en el stack dev y publica el reporte |
| Noche (20–22) | Ajustar el prompt **una vez** según la evaluación y congelarlo | Arreglos del E2E | Arreglos del E2E | Reporte de evaluación: exactitud exacta y ±1, por nivel y por tipo de entrada |

### Jueves 16-oct (mañana) — Operation y demo

| Tarea | Responsable |
|---|---|
| `sam deploy` del stack prod desde el Code Editor y cambiar el webhook de Meta a prod | P4 + P2 |
| Alarmas de CloudWatch: mensajes en la DLQ y errores de Bedrock | P4 |
| Dashboard mínimo por sala (stretch, corrección 6) | P4 |
| Ensayar la demo 2 veces en teléfonos reales: texto, nota de voz, post-it, Ajustar por audio y número desconocido ignorado | Todos, P2 opera |
| Pitch: dolor (4 h/semana) → demo → resultados de la evaluación → privacidad → escalabilidad | P1 |
| **Congelar el código 2 h antes del juicio** (el desarrollo termina el 16-oct a las 10:15) | P1 decide |

## 4. Reglas de trabajo (sin cambios respecto al plan de Kiro)

- Branches cortas `u1-…` a `u5-…`, squash merge, `main` siempre desplegable. Se commitean las specs de Kiro y el estado de AI-DLC.
- Sync de 15 min por bolt: qué se mergeó, qué está bloqueado y cuántos créditos de Kiro se usaron.
- **Definition of done:** los tests pasan, el contrato se respeta, está desplegado en dev y hay 1 prueba en teléfono real grabada.
- Kiro solo para lo difícil (U3, U4, U2). El boilerplate (loaders, configuración) se escribe a mano.

## 5. Verificación

- **Unitarias:** el esquema rechaza un nivel fuera de la tabla y evidencia que no está en el catálogo. La edad calculada coincide con `edad_meses_observacion` de `consolidado.json`. El webhook rechaza firmas inválidas y números desconocidos.
- **Evaluación:** 200 casos, reportar exactitud exacta y ±1 contra `nivel_estimado`.
- **E2E en teléfono:** cada tipo de entrada produce una propuesta en menos de 60 s. Ajustar cambia el nivel. Confirmar escribe el nivel y la fila de auditoría. Un número desconocido no recibe respuesta.

## 6. Pendientes para Integra (después de la hackathon)

La rúbrica real de 8 niveles × 10 núcleos (se cambia solo la tabla `levels`), un número verificado de WhatsApp Business, una revisión de privacidad sobre guardar medios de niños/as y un dashboard para directoras.
