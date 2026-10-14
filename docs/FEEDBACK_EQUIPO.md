# IntegrAI — Feedback de arquitectura + propuesta de integración

> **Para:** equipo IntegrAI (Santiago, P1–P4) · **De:** Sebastián Wagner + Shiva
> **Fecha:** 14-oct-2026 · **Contexto:** Desafío 1 Fundación Integra · Breaking Barriers Chile 2026
> **Insume:** Plan de equipo v2 (doc Google) + verificación directa en la cuenta AWS del evento.

---

## 0. TL;DR

El plan v2 está **muy bien pensado** y encaja casi 1:1 con lo que ya construimos. Hay **1 error crítico** (la rúbrica) y **3 ajustes de alto impacto**. Proponemos **integrar** nuestra instancia `integra-server` como el **servicio de decisión (U3-bis)** + **dashboard**, en lugar de apagarla. Cero duplicación de backends.

---

## 1. Verificaciones hechas en la cuenta del evento (dato duro)

### 1.1 Modelos de Bedrock (su corrección #1) — ✅ VALIDADA
Probé las llamadas reales. **Todos existen y responden** con el prefijo `us.`:

| Modelo | Uso en el plan | Resultado |
|---|---|---|
| `us.anthropic.claude-sonnet-5` | U3 Clasificador + visión | ✅ OK |
| `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Generar eval sintética | ✅ OK |
| `us.amazon.nova-pro-v1:0` | Video | ✅ OK |
| `us.anthropic.claude-sonnet-4-6` | Fallback | ✅ OK |

> Nota: sin el prefijo `us.` (inference profile) varios dan `AccessDenied`/`ValidationException`. Su corrección es correcta.

### 1.2 Instancia `integra-server` (su corrección #4)
Existe y está **operativa**. Detalle en §6. No es "código suelto": es un **servicio de decisión + dashboard** funcionando.

---

## 2. Lo que validamos del plan (alineación)

| Tema | Coincidencia |
|---|---|
| Dolor / KPI | 4 h/semana → ~0 ✔️ |
| Canal | WhatsApp multi-formato (texto, post-it, voz, video) ✔️ |
| **Human-in-the-loop** | *Solo la tía cambia el nivel* ✔️ — **es el mejor punto del plan** y alinea con nuestra tesis "el modelo propone, la persona decide" |
| Privacidad | código/apodo (no RUT), S3 cifrado, Ley 21.719 ✔️ |
| Encuadre | "apoyo, no diagnóstico clínico" ✔️ |
| Método | AI-DLC + contrato congelado + gates ✔️ |

---

## 3. Correcciones

### 🔴 CRÍTICA — La rúbrica (rompería la evaluación)

| El plan dice | La **realidad del dataset** (autoritativa) |
|---|---|
| "8 niveles × 10 núcleos" (del PPT), en *pendientes* | **9 niveles × 5 dominios** |
| — | Ground truth = `nivel_estimado` ∈ **1…9** |
| "90 manifestaciones" | **90 = 9 niveles × 10** (2 por dominio × 5 dominios) |

Los 5 dominios del dataset: `motor_grueso`, `motor_fino`, `lenguaje_comunicacion`, `socioemocional`, `cognitivo`.

**Acción:** construir `LevelEnum` (1–9) y `DomainEnum` (5) **desde `ruta_niveles.csv` y `manifestaciones.csv`**, NO desde el PPT. Si el enum tiene 8 niveles, la eval contra `nivel_estimado` queda inconsistente.

### 🟡 AI-1 — "typesafe" ≠ Pydantic (oportunidad de Innovación 25%)
Pydantic garantiza la **forma** del JSON, no la **decisión** ("no se sale del esquema, pero puede equivocarse dentro de él").
**Sugerencia:** mantener Pydantic para el **contrato** + sumar un **decision model** (Laya, on-prem) que emita el nivel como **decisión tipada y calibrada** (distribución sobre los 9 niveles). Sube el eje de Innovación.

### 🟡 AI-2 — La eval sintética sobre `nota_breve` es débil
Verificado: 70% de las notas existen, pero son **plantillas genéricas** (ej. *"Registro realizado durante una actividad de juego libre"*). Poca señal.
**Acción:** generar los casos de evaluación desde las **manifestaciones** (conductas observables), que sí cargan el nivel; y medir contra las **2.950 observaciones reales**.

### 🟡 AI-3 — `integra-server`: INTEGRAR (no apagar)
Es lo que el serverless **no** puede cómodo:
- **Laya** (421M, on-prem) no cabe/corre bien en Lambda.
- **Dashboard funcional** → es su *stretch* P4 del día 16, **ya construido**.
- **Matcher + trayectorias + alertas de rezago** → justo lo que el deck pide mostrar.

**Seguridad (su observación es correcta):** cerrar el puerto **22** (usar SSM) y **restringir el 8501**. Acción nuestra.

---

## 4. Nuestra arquitectura (lo que ya está construido)

```
👩🏫 Tía (WhatsApp)
   │  texto · foto · audio · video
   ▼
[1] INGESTA        recibe y clasifica el formato
   ▼
[2] COMPRENSIÓN    Whisper (audio/video) · Nova Pro visión (imagen)   → texto
   ▼
[3] MATCHER        híbrido: embeddings Titan (1024-d) + léxico
   │               →  ¿qué MANIFESTACIONES del catálogo aparecen?
   ▼
[4] DECISIÓN       modelo typesafe Laya (on-prem, 421M)
   │               →  nivel 1-9 + probabilidad CALIBRADA
   ▼
[5] PLATAFORMA     jardín › educadora › niño/a › observación › manifestaciones
   ▼
[6] SALIDA         WhatsApp (respuesta) + TRAYECTORIA + ALERTA de rezago
```

**Piezas clave:**
- **Matcher híbrido** sobre los 90 manifestaciones → evidencia **auditable** (no alucinada).
- **Laya typesafe** (Apache-2.0, on-prem, ~30 ms) → decisión calibrada. **+ fine-tuning con datos de Integra** (en curso).
- **Trayectoria + alertas** de rezago/estancamiento.
- **Dashboard Streamlit** (4 pestañas): registrar, trayectoria, panorama de aula, marco.

---

## 5. Arquitectura unificada propuesta

```
WhatsApp → U1 Gateway (Lambda + firma + whitelist) → SQS → U2 Normalizar          ← EQUIPO
              (Transcribe audio/video · Nova Pro visión post-it)
                                     │
                                     ▼
        ┌─────────────────────────────────────────────────────┐
        │  U3-bis · DECISIÓN  (EC2 integra-server)             │ ← NOSOTROS
        │   matcher híbrido (Titan) + Laya typesafe           │
        │   → nivel + confianza calibrada + evidencia         │
        └─────────────────────────────────────────────────────┘
                                     │
        U4 Sesión (Confirmar / Ajustar / Cancelar)  — Lambda    ← EQUIPO
                                     │
        U5 Commit (DynamoDB transaccional) + auditoría          ← EQUIPO
                                     │
                    Dashboard + Alertas de rezago (EC2)          ← NOSOTROS
```

**Reparto:** el equipo hace el *core serverless* (U1, U2, U4, U5). Nosotros el **motor de decisión on-prem (U3-bis)** + **dashboard + trayectorias**. Sin duplicar backends.

**Interfaz sugerida U3-bis** (contrato mínimo):
```
POST /clasificar
{ "observation_id": "...", "text": "...", "edad_meses": 24, "candidates": [7,8,9] }
→ 200 {
     "nivel": 8, "nombre_nivel": "Combinación y participación",
     "probabilidades": {"7":0.22,"8":0.51,"9":0.27},
     "confianza": 0.51, "dominios": ["motor_fino"],
     "evidencia": [{"id":"MAN-L08-MF-01","texto":"...","score":0.87}],
     "backend": "laya-integra", "alerta_rezago": false
   }
```

---

## 6. Datos de la instancia `integra-server` (para `/docs/decisiones.md`)

| Ítem | Valor |
|---|---|
| **Instance ID** | `i-0226f28f9b99716f2` |
| **Estado** | running |
| **Tipo** | `c6i.2xlarge` (8 vCPU · 16 GB RAM · 60 GB gp3) |
| **IP pública** | `44.204.243.156` |
| **AZ** | `us-east-1a` |
| **SO** | Ubuntu 24.04 LTS · Python 3.12 |
| **Acceso** | **SSM** (Session Manager) + key `integra-kp.pem` |
| **Security Group** | `sg-06699d42c3e0fb9eb` (22/80/443/8000/8501 → 0.0.0.0/0) ⚠️ *a endurecer* |
| **IAM** | instance profile con **Bedrock** ✅ (probado) |
| **Servicios** | `integra.service` (dashboard Streamlit, systemd, auto-restart) |
| **Dashboard** | **http://44.204.243.156** (Streamlit, HTTP 200) |
| **Modelos en disco** | `laya` (2.3G) · `laya-typed-decisions` (808M) · `laya-integra` (fine-tune v1) · `laya-integra2` (fine-tune v2, en curso) |
| **Stack** | boto3 · streamlit 1.66 · **laya 0.4.7** · torch 2.14.1+cpu · transformers · faster-whisper |
| **Disco** | 15 GB usados / 58 GB (25%) |

**Acciones de seguridad pendientes (acordar):**
1. Cerrar puerto **22** → administrar solo por **SSM**.
2. Restringir **8501/8000** (o cerrarlos; el dashboard va por 80).
3. Mover el dashboard a un subdominio con TLS si se expone.

---

## 7. Próximos pasos / decisiones

1. **Decisión de integración** (corrección #4): ¿`integra-server` como **U3-bis + dashboard**? → escribir en `/docs/decisiones.md`.
2. **Alinear enums** (`LevelEnum` 1–9, `DomainEnum` 5) desde `ruta_niveles.csv` / `manifestaciones.csv`.
3. **Acceso al repo** `IntegrAI-coder/IntegrAI` → revisamos `/contracts` y alineamos la interfaz U3-bis.
4. **Canal de sync**: sumarnos a la cadencia de 15 min/bolt.
5. **Seguridad**: ejecutamos el endurecimiento del SG.

---

## Anexo — Estado del fine-tuning de Laya (evidencia propia)

- **Datos**: 2.507 train / 443 eval, construidos desde las **manifestaciones** (conductas observables → nivel 1–9) del dataset.
- **v1** (criterios sin descripción) → colapsó a la clase prior (acc ≈ 0.13). *Causa raíz encontrada y corregida.*
- **v2** (criterios **descriptivos** por nivel, base multilingual, 6 épocas, CPU) → **en curso**, mean loss bajando (2.20 → 2.01 en 2 épocas).
- **Resultado final**: accuracy **antes/después** (lo calcula Laya), para el *moat* de Innovación.

> *"El LLM escribe; el decision model decide."*
