# Cola "POR VERIFICAR" — demo de los 4 cursos (human-in-the-loop)

Puebla la **cola de verificación** de los 4 cursos del equipo (`JAR-EQUIPO`) y prueba el
ciclo completo: la tía consulta su cola por WhatsApp → **resuelve** (aprobar / editar /
rechazar) → la decisión se escribe en `evaluaciones`.

## 1. Poblar la cola

```bash
/opt/integra/.venv/bin/python tools/seed_cola_equipo.py       # siembra observaciones
/opt/integra/.venv/bin/python -m src.evaluacion_periodica     # el cron genera los pendientes
```

- El seeder siembra **48 observaciones** (6 niños × 4 cursos) de **nivel variado** (2/3, 3/4,
  …, 7/8), origen `demo_cola`, idempotente.
- El cron las consolida por niño: **dos niveles con confianza parecida → margen ≈ 0,048**
  (< `GATE_MARGEN` 0,15) → cada niño entra a `evaluaciones_pendientes` **asignado a la tía de su sala**.

**Resultado: 24 pendientes (6 por curso), margen 0,048.**

| Curso | Tía | WhatsApp | Pendientes |
|---|---|---|---:|
| Sala Girasol | `EDU-EQ-1` | +56 9 5894 7607 | 6 |
| Sala Mariposa | `EDU-EQ-2` | +56 9 4125 7056 | 6 |
| Sala Estrella | `EDU-EQ-3` | +54 9 381 209 0006 | 6 |
| Sala Cometa | `EDU-EQ-4` | +56 9 5643 3264 | 6 |

- El seeder es **idempotente**: borra lo sembrado (`origen=demo_cola`) y los pendientes de
  `JAR-EQUIPO`, y **retrocede el watermark del cron** al mínimo sembrado. Esto último es necesario
  porque SQLite **reutiliza rowids** al borrar+insertar; sin ese ajuste el cron creería que las
  observaciones nuevas "ya se procesaron" (`nuevas: 0`).

## 2. Probar la cola (por WhatsApp)

```bash
# cada tía ve SOLO lo suyo (se identifica por su número)
curl -H "x-api-key: $INTEGRA_API_TOKEN" "http://44.204.243.156:8000/pendientes?from=56958947607"

# aprobar | editar (con nivel) | rechazar
/opt/integra/.venv/bin/python tools/test_cola_htl.py
/opt/integra/.venv/bin/python tools/test_cola_htl.py --resolver EDU-EQ-1 --accion aprobado
/opt/integra/.venv/bin/python tools/test_cola_htl.py --resolver EDU-EQ-1 --accion editado --nivel 9
/opt/integra/.venv/bin/python tools/test_cola_htl.py --resolver EDU-EQ-1 --accion rechazado
```

## 3. Resultado verificado (15-oct-2026)

| Prueba | Resultado |
|---|---|
| `GET /pendientes?from=<número>` de las 4 tías | ✅ EDU-EQ-1..4 → **6 cada una**, identificadas por su número |
| Tía **aprueba** (`PEND-90137`) | ✅ escribe `EVAL-90367` (nivel 2) en `evaluaciones` |
| Tía **edita** (`PEND-90138`, nivel → 9) | ✅ escribe `EVAL-90368` (nivel 9) |
| Tía **rechaza** (`PEND-90139`) | ✅ **no** escribe evaluación |
| `evaluaciones` | ✅ 366 → **368** (+2, exacto) |
| Cola de `EDU-EQ-1` tras resolver 3 | ✅ 6 → **3** |

Esto cierra el circuito **human-in-the-loop**: *el modelo propone, la tía decide, y solo su
decisión (aprobar/editar) se vuelve canónica.*

## 4. Nota de diseño (para Integra)

Hoy la cola la **llena el CRON** (00:00). Una observación suelta de margen bajo, que entra por
WhatsApp, queda en `observaciones.estado = 'por_verificar'` pero **aparece en
`evaluaciones_pendientes` recién en la próxima corrida** del cron.
Si Integra quiere verla **en vivo** (sin esperar al día siguiente), basta encolar el pendiente en
el handler `/procesar` cuando `requiere_revision` (cambio pequeño en `webhook_ec2.py`).

---
*Shiva · IntegrAI (AWS Breaking Barriers Chile 2026) · 15-oct-2026.*
