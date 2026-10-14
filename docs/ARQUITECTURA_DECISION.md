# 🇨🇱 IntegraAI · Agente de evaluación de párvulos

> **Desafío:** *Fundación Integra — análisis de observaciones (notas, fotos, audio, video)
> para la evaluación de aprendizajes de niños y niñas.*
> **Evento:** AWS Breaking Barriers Chile 2026 (14–16 oct, U. de Chile).
> **Equipo:** Sebastián Wagner + Shiva.

## 💡 La idea en una frase

Hoy una educadora de párvulos dedica **~4 horas semanales** a analizar notas, fotos,
audios y videos para evaluar a cada niño/a. Construimos un **agente que recibe esos
insumos por WhatsApp (en cualquier formato), los procesa con modelos de lenguaje,
emite una decisión de evaluación tipada y calibrada, y responde por el mismo canal** —
dejando el registro ordenado por **institución › docente › aula › alumno**.

**Lo que nos hace distintos:** no es un chatbot que escribe párrafos. Es un flujo
donde **el LLM escribe y un *decision model* decide**. La evaluación sale como una
**decisión tipada** (`Choice` / `Score` / `Noul`, estilo *Jev / System One*): un
espacio finito, enumerable y **auditable**, con confianza calibrada — exactamente lo
que una institución educativa necesita para confiar en el resultado.

## 🏗️ Arquitectura

```
  Educadora ── WhatsApp (nota · foto · audio · video)
        │
        ▼
   App / Harness ── EC2 (familiar: Linux)
        │
        ├──▶ Procesadores        notas/fotos/audios/videos -> Evidencia
        ├──▶ Amazon Bedrock      gateway multi-modelo (Nova Lite/Pro + Claude)
        │     + Strands Agents SDK (harness agéntico AWS)
        ├──▶ Decision Model      Jev / Laya (open, 421M) -> decisión tipada + calibrada
        ├──▶ Plataforma          institución › docente › aula › alumno (SQLite -> Aurora/DynamoDB)
        └──▶ WhatsApp            respuesta cálida en el mismo canal
```

## 🚀 Cómo correr (demo local, sin AWS)

```bash
cd integra
python3 demo_cli.py "hoy Martina se vistió sola y contó hasta 5"
# o el escenario precargado:
python3 demo_cli.py

# dashboard (requiere streamlit):
pip install -r requirements.txt
streamlit run app.py
```

Sin credenciales AWS corre en **modo MOCK** (todo offline). Con credenciales de
Bedrock, las respuestas y el análisis de imagen/audio se hacen con modelos reales
**sin tocar el resto del código** (el gateway degrada solo).

## 🧠 El decision model (el corazón de la tesis)

En vez de pedirle a un LLM que "opine" el nivel de un niño/a en texto libre, el
clasificador emite, por cada núcleo del marco curricular:

| Primitiva | Salida | Para qué |
|---|---|---|
| **Choice** | `No observado \| En proceso \| Logrado` + probabilidades | el nivel, con distribución calibrada |
| **Score** | 0–100 + intervalo | magnitud del aprendizaje |
| **Noul** | probabilidad de "¿hay evidencia suficiente?" | evita afirmar sin respaldo |

Es **modelo-agnóstico**: el backend (`BackendHeuristico` MOCK → `BackendJevAPI`) se
intercambia sin tocar el resto. Eje de **auditoría + costo + soberanía** (Laya corre
offline en ~1 GB).

## 🗂️ Estructura

```
integra/
├── data/
│   ├── marco_evaluacion.json   # ámbitos / núcleos / aprendizajes esperados (semilla)
│   └── lexico_senales.json     # léxico de señales por núcleo
├── src/
│   ├── modelo_decision.py      # primitivas tipadas (Choice/Score/Noul) + calibración
│   ├── clasificador.py         # evidencia -> decisión por núcleo
│   ├── procesadores.py         # formatos -> evidencia
│   ├── bedrock.py              # gateway LLM (Nova/Claude) con fallback MOCK
│   ├── plataforma.py           # institución>docente>aula>alumno (SQLite)
│   ├── whatsapp.py             # canal (consola MOCK / Cloud API stub)
│   └── agente.py               # orquestador end-to-end
├── demo_cli.py                 # demo end-to-end offline
└── app.py                      # dashboard Streamlit
```

## ⚠️ Estado y límites honestos

- El **decision model real (Jev/Laya)** está como gancho (`BackendJevAPI`); hoy corre
  el `BackendHeuristico` (MOCK) para probar el flujo completo offline.
- La **transcripción/visión de imagen** en MOCK usa el texto provisto; con Bedrock
  (o Whisper) se conecta de verdad.
- El **marco curricular** es una semilla de 3 ámbitos × 8 núcleos (BCEP); se completa
  con el instrumento oficial de Integra.
- El canal WhatsApp tiene el contrato; el adaptador real (Meta Cloud API / Twilio)
  queda detrás de `CanalCloudAPI`.
