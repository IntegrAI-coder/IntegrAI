# Arquitectura — Resolver nombre→ID y evaluación periódica (IntegrAI · Desafío E-1)

> **Proyecto:** `ws:integra_ai` · **Fecha:** 14-oct-2026 · **Autor:** Sebastián Wagner + Shiva
> **Estado:** decisiones cerradas (falta: cadencia del cron → confirmar con Fundación Integra).

---

## 0. Principio rector

> **WhatsApp es SOLO canal de entrada.** El LLM/OCR **lee y extrae**; el sistema **resuelve y decide** de forma determinista y auditable. La tía **no cambia su forma de trabajar** (post-it → foto → WhatsApp). Nosotros nos adaptamos a ella, no al revés.

```
👩🏫 Tía ── WhatsApp (SOLO entrada)
     │  texto · foto (post-it) · audio · video
     ▼
① INGESTA      normaliza a texto (Whisper audio/video · visión+OCR imagen)
     ▼
② EXTRACCIÓN   LLM: { mención_nombre, texto_observación, dominio?, evidencia }
     ▼
③ RESOLVER     nombre → id_nino   ★ DETERMINISTA (no IA) ★   ← el corazón
     ▼
④ DECISIÓN     ensemble (matcher Titan+léxico + prior + Laya) → nivel 1-9 + margen
     ▼
⑤ PERSISTENCIA gate por margen:
        margen ≥ 0.15  → observación DIRECTA a la BD canónica   (≈83%)
        margen <  0.15 → cola "POR VERIFICAR" en la plataforma   (≈17%)
     ▼
⑥ CRON (diario) evalúa desde la BD acumulada → avance/retroceso/estancamiento
```

**ACK:** WhatsApp responde `"registrado ✓"` (y, si aplica, `"por verificar, revísalo en la plataforma"`). Nunca es mudo (la tía necesita saber que entró).

---

## 1. Decisiones cerradas (14-oct-2026)

| # | Punto | Decisión |
|---|---|---|
| 1 | Respuesta de WhatsApp | `"registrado"` (ACK mínimo). No es bidireccional. |
| 2 | Qué requiere verificación | **Solo lo que el gate marca dudoso** (margen < 0.15). Si no, no se cumple el KPI de 0 hrs. |
| 3 | Cadencia del cron | **Diaria** con data acumulada (detectar retrocesos/avances/estancamientos). *Pendiente: confirmar con Integra.* |
| 4 | Regla de nombres | La tía escribe solo el nombre de pila si es único en la sala; **nombre + apellido si hay homónimos** (ej. "sebastian wagner"). El resolver **imita la lógica de la tía**. |
| 5 | Ámbito | **Demo: por sala.** Escalamiento: identificar a la **educadora por su número de WhatsApp** → mapear a **su sala y sus alumnos** (roster por sala). |
| 6 | Gate alto | **Entra directo a la BD** (sin staging). |

---

## 2. ★ El RESOLVER (nombre → `id_nino`)

> **Regla de oro:** el LLM **nunca** inventa el `id_nino`. Extrae la **mención literal**; el resolver determinista la mapea. Así la asignación es **reproducible y auditable** ("¿por qué este niño?" → "coincidencia exacta de nombre de pila único en la sala").

### 2.1 Índice del roster (por sala)
```
nombre_pila_normalizado → { id_nino: [apellidos_normalizados...] }
```
La normalización: minúsculas, sin acentos, sin puntuación, espacios colapsados.

### 2.2 Algoritmo de resolución
```python
def resolver(mencion, roster_sala):
    toks   = normalizar(mencion)            # "Sebastián Wagner" -> ["sebastian","wagner"]
    pila   = toks[0]
    apells = toks[1:]

    # 1) match exacto de nombre de pila
    cands = roster_sala.get(pila, {})       # {id: [apellidos...]}
    if len(cands) == 1:                     # único en la sala -> RESUELVE
        return OK(unico_id, metodo="exacto")
    if len(cands) > 1:                      # homónimos
        if apells:                          # la tía dio apellido -> RESUELVE
            for id, aps in cands.items():
                if any(a in aps for a in apells):
                    return OK(id, metodo="exacto+apellido")
            return AMBIGUO(cands)           # apellido no matchea
        return AMBIGUO(cands)               # falta apellido -> POR VERIFICAR

    # 2) diminutivos (es-CL): "mati" -> {matias, matilde}
    for canon in DIMINUTIVOS.get(pila, []):
        sub = roster_sala.get(canon, {})
        if len(sub) == 1: return OK(list(sub)[0], metodo="diminutivo")

    # 3) fuzzy (typos de OCR): difflib sobre nombres de pila
    best = fuzzy_top(pila, roster_sala)
    if best.score >= UMBRAL_FUZZY and best.es_unico_bajo_umbral:
        return OK(best.id, metodo="fuzzy", confianza=best.score)

    return DESCONOCIDO()                    # no matchea -> POR VERIFICAR
```

### 2.3 Salidas posibles
| Salida | Cuándo | Acción |
|---|---|---|
| `OK(id, metodo)` | nombre único / nombre+apellido / diminutivo / fuzzy seguro | asigna y sigue el flujo |
| `AMBIGUO([ids])` | homónimos sin apellido, o apellido que no matchea | **POR VERIFICAR** |
| `DESCONOCIDO` | el nombre no está en la sala | **POR VERIFICAR** |
| `SIN_NOMBRE` | nota general sin niño ("actividad de arte") | a nivel **aula** o descartar (decidir) |

### 2.4 Casos borde (registrados)
- **Diminutivos chilenos:** Mati (Matías/Matilde), Cote/Coté (María José), Pancho (Francisco), Nacho (Ignacio), Vale (Valentina/Valeria).
- **Homónimos totales** (mismo nombre + apellido): requiere 3er discriminador → **POR VERIFICAR**.
- **Varios niños en un mensaje:** el LLM extrae **una mención por niño** → N observaciones (o bloqueo a revisión; decidir).
- **OCR dudoso:** la mención entra con baja confianza → **POR VERIFICAR**.

---

## 3. Escalamiento: WhatsApp → educadora → sala → alumnos

```
número WhatsApp ──(registry)──> id_educadora ──> sala_grupo ──> roster de la sala
```
- **Demo:** un número ↔ una educadora ↔ una sala.
- **Escala (todos los jardines):** tabla `educadoras.telefono_whatsapp`. Un número puede tener **varias salas** → si el nombre matchea en una sola, resuelve; si matchea en varias → POR VERIFICAR.
- **Número nuevo / desconocido:** onboarding (verificar identidad antes de habilitar).
- Beneficio: el **ámbito por sala** reduce drásticamente la ambigüedad de nombres.

---

## 4. Migración de la BD (nuevas tablas / columnas)

```sql
-- 4.1 Roster de nombres (para el resolver). Nombre = dato personal -> cifrar/alias en prod.
ALTER TABLE ninos ADD COLUMN nombre_pila TEXT;
ALTER TABLE ninos ADD COLUMN apellidos   TEXT;
CREATE TABLE IF NOT EXISTS ninos_alias (        -- apodos / cómo la llama la tía
    id_nino TEXT, alias TEXT, PRIMARY KEY (id_nino, alias));

-- 4.2 Educadora <-> WhatsApp <-> sala
ALTER TABLE educadoras ADD COLUMN telefono_whatsapp TEXT;
CREATE TABLE IF NOT EXISTS educadora_salas (
    id_educadora TEXT, sala_grupo TEXT, id_jardin TEXT,
    PRIMARY KEY (id_educadora, sala_grupo));

-- 4.3 Estado de resolución en la observación
ALTER TABLE observaciones ADD COLUMN metodo_resolucion TEXT;  -- exacto|apellido|diminutivo|fuzzy|-
ALTER TABLE observaciones ADD COLUMN margen REAL;
ALTER TABLE observaciones ADD COLUMN estado TEXT DEFAULT 'auto';  -- auto|por_verificar|verificado

-- 4.4 Cola de verificación humana (human-in-the-loop)
CREATE TABLE IF NOT EXISTS evaluaciones_pendientes (
    id_pendiente TEXT PRIMARY KEY,
    id_mensaje   TEXT,             -- idempotencia (dedupe por message_id de WhatsApp)
    id_nino_propuesto TEXT,        -- NULL si AMBIGUO/DESCONOCIDO
    candidatos   TEXT,             -- JSON con [id, score]
    nivel_propuesto INTEGER,
    dominio      TEXT,
    confianza    REAL, margen REAL,
    motivo       TEXT,             -- 'margen_bajo'|'nombre_ambiguo'|'nombre_desconocido'|'ocr_dudoso'
    evidencia    TEXT,
    estado       TEXT DEFAULT 'pendiente',   -- pendiente|aprobado|editado|rechazado
    creado_en    TEXT, resuelto_en TEXT, resuelto_por TEXT);

-- 4.5 Evaluación canónica (la que produce el cron, aprobada)
CREATE TABLE IF NOT EXISTS evaluaciones (
    id_evaluacion TEXT PRIMARY KEY, id_nino TEXT, dominio TEXT,
    nivel INTEGER, periodo TEXT, tendencia TEXT, alerta TEXT,
    generado_en TEXT);
```

---

## 5. Idempotencia y auditoría (no negociable)

- **Idempotencia:** WhatsApp reintenta webhooks → dedupe por `message_id` (`evaluaciones_pendientes.id_mensaje` + índice único). Un post-it reenviado no genera doble observación.
- **Auditoría:** toda observación guarda `metodo_resolucion`, `confianza`, `margen`, `evidencia` y su `estado`. Cualquier corrección de la tía queda registrada (`resuelto_por`, `resuelto_en`).
- **Ley 21.719:** nombres y datos de niños = dato personal → cifrado en reposo, sin RUT, minimización. La asignación por `id_nino` desacopla la identidad del análisis.

---

## 6. El CRON (evaluación periódica)

```
[diario, p.ej. 02:00]  evaluacion_periodica.py
  1. leer observaciones nuevas desde el watermark (ultima_ejecucion)
  2. por cada (niño, dominio) con observaciones nuevas:
        - agregar evidencia del período
        - correr el ensemble -> nivel + margen
        - comparar con el nivel previo -> tendencia (avance|retroceso|estancamiento)
        - si margen < 0.15 -> evaluaciones_pendientes (por_verificar)
          si margen ≥ 0.15 -> evaluaciones (canónica) + alerta si retroceso
  3. actualizar watermark
```
- **Watermark:** solo procesa lo nuevo (idempotente y barato).
- **Alertas:** retroceso o estancamiento → destacadas en la plataforma (y opcionalmente un resumen).
- **Reutiliza** `trayectoria.py` para la serie histórica por dominio.

---

## 7. Piano de módulos (repo)

| Módulo | Estado | Rol |
|---|---|---|
| `src/whatsapp.py` | ✅ existe | canal **solo entrada** + ACK |
| `src/procesadores.py` | ✅ existe | Whisper / visión-OCR |
| `src/resolver.py` | 🆕 **NUEVO** | nombre → id_nino (determinista) |
| `src/backend_decision.py` | ✅ existe | ensemble + gate por margen |
| `src/plataforma.py` | 🔧 ampliar | roster + staging + evaluaciones |
| `src/evaluacion_periodica.py` | 🆕 **NUEVO** | el cron |
| `app.py` | 🔧 ampliar | pestaña "Por verificar" |

---

## 8. Pendientes / decisiones abiertas
1. **Cadencia del cron** → confirmar con Fundación Integra (default propuesto: diaria).
2. **Mensaje con varios niños** → ¿N observaciones o bloqueo a revisión?
3. **Nota sin nombre** → ¿nivel aula o descartar?
4. **Umbral fuzzy** y **tabla de diminutivos**: calibrar con datos reales.
5. **¿El cron también re-evalúa lo "por verificar" ya resuelto?** (sí, recomendado).
