# ⏰ Cron diario + cola "POR VERIFICAR" — IntegrAI

## 1. El cron (evaluación periódica)

**Cuándo:** **todos los días a las 00:00 (hora de Chile)**.
**Qué hace:** consolida las observaciones acumuladas y deja las evaluaciones
**actualizadas hasta el día anterior**.

### Configuración (systemd, en la EC2)
| Archivo | Contenido |
|---|---|
| `/etc/systemd/system/integra-cron.timer` | `OnCalendar=*-*-* 00:00:00` · `Persistent=true` |
| `/etc/systemd/system/integra-cron.service` | `ExecStart=/opt/integra/.venv/bin/python -m src.evaluacion_periodica` |

> `Persistent=true` → si la máquina estuvo apagada, corre al encender (no pierde el día).
> Zona horaria de la EC2: **America/Santiago** (maneja automáticamente el horario de verano).

### Lógica
```
observaciones NUEVAS (por watermark)  ─►  consolidar por niño (media pond. por confianza)
   │
   ├─ margen ≥ 0.15  ─►  evaluación CANÓNICA  (tabla `evaluaciones`)
   └─ margen < 0.15  ─►  COLA "POR VERIFICAR" (tabla `evaluaciones_pendientes`)
   └─ tendencia: avance / retroceso / estable / sin_historial  → alerta si retroceso
```
- **`periodo`** de la evaluación = **ayer** (el día completo anterior al run de las 00:00).
- **Watermark por `rowid`** (`meta.cron_watermark_rowid`): solo procesa lo nuevo; idempotente.

### Comandos útiles
```bash
systemctl list-timers integra-cron.timer --no-pager   # ver próxima corrida
systemctl start integra-cron.service                  # correr AHORA (catch-up manual)
journalctl -u integra-cron.service -n 30 --no-pager   # ver el log de la última corrida
/opt/integra/.venv/bin/python -m src.evaluacion_periodica --dry-run   # simular sin escribir
```

---

## 2. La cola "POR VERIFICAR" — **asignada a la tía correcta** 🎯

Cuando una evaluación tiene **margen bajo**, no se decide sola: entra a
`evaluaciones_pendientes` **asignada a la tía responsable**.

### ¿A quién se asigna?
| Prioridad | Regla |
|---|---|
| 1️⃣ | La **tía de la sala del niño** (`educadora_salas` → `educadora_de_sala(jardin, sala)`) |
| 2️⃣ | *(fallback)* quien **registró** la observación (`observaciones.id_educadora`) |

> Así cada tía ve **solo lo suyo**: la cola se filtra por `evaluaciones_pendientes.id_educadora`.

### Campos clave de `evaluaciones_pendientes`
`id_pendiente` · `id_nino_propuesto` · **`id_educadora`** (la tía) · `nivel_propuesto` ·
`margen` · `motivo` (`margen_bajo`) · `evidencia` · `estado` (`pendiente`) · `creado_en`.

---

## 3. Endpoints para la UI / tía

| Método | Ruta | Para qué |
|---|---|---|
| `GET` | `/pendientes?from=<número>` | la cola de **esa** tía (se identifica por su WhatsApp) |
| `POST` | `/pendiente/resolver` | `{id_pendiente, accion: aprobado\|editado\|rechazado, nivel?, resuelto_por?}` |

> **Aprobar/editar escribe en `evaluaciones`** → la decisión de la tía se vuelve canónica.

### Ejemplo
```bash
# la tía de Sala Girasol (+56958947607) pide su cola
curl -H "x-api-key: $INTEGRA_API_TOKEN" "http://44.204.243.156:8000/pendientes?from=56958947607"

# aprueba el nivel propuesto
curl -X POST http://44.204.243.156:8000/pendiente/resolver \
  -H "x-api-key: $INTEGRA_API_TOKEN" -H 'Content-Type: application/json' \
  -d '{"id_pendiente":"PEND-90001","accion":"aprobado","resuelto_por":"EDU-EQ-1"}'

# o lo corrige
curl -X POST http://44.204.243.156:8000/pendiente/resolver \
  -H "x-api-key: $INTEGRA_API_TOKEN" -H 'Content-Type: application/json' \
  -d '{"id_pendiente":"PEND-90001","accion":"editado","nivel":5}'
```

---
*Shiva · IntegrAI (AWS Breaking Barriers Chile 2026) · 15-oct-2026.*
