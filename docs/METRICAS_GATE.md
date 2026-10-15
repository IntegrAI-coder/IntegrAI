# Métricas de la compuerta de revisión (margen)

Medición **fresca y reproducible** de la compuerta por **margen** (`top1 − top2`) del
clasificador **desplegado** (`POST /clasificar`, `backend: ensemble` = híbrido ⊕ Laya base),
sobre el benchmark interno de **300 notas sintéticas**. Complementa a `EVAL_ENSEMBLE.md`
(que revisa el ensemble y la debilidad en casos "contra la edad") y a `bench/reporte_compuerta.md`
(que calibra la regla sobre 90 casos vía API).

> **Objetivo del pendiente #4:** fijar la **precisión real** de la compuerta por margen y definir
> el **protocolo de muestreo de auditoría** de la cola auto-registrada.

## 1. La regla

```
margen = top1 − top2   de la distribución del ensemble (sobre los 9 niveles)
si  margen < GATE_MARGEN (0,15)  →  va a «por verificar» (cola de la tía)
si no                            →  se auto-registra
```

Implementada en `src/compuerta.py` y `src/config.py` (`GATE_MARGEN`). El umbral operativo
del despliegue es **0,15**.

## 2. Metodología

- **Set:** 300 notas sintéticas (`bench/casos_300.jsonl`) generadas estilo tía a partir de las
  manifestaciones del dataset, con su `nivel_estimado` como verdad. Semilla fija `20261014`.
- **Modelo:** el **ensemble desplegado**. Detalle honesto: el ensemble usa **Laya base**
  (no el afinado), por lo que **no hay contaminación** de datos en esta medición.
- **Reproducir:** `python -m bench.gate --casos casos_300.jsonl` (escribe `bench/reporte_gate.md`).

## 3. Resultado global (sin compuerta)

| Métrica | Valor |
|---|---:|
| Exactitud **exacta** | **0,940** (282/300) |
| Exactitud **±1** | 0,973 (292/300) |
| Errores totales | 18 |

Coincide con el 0,940 reportado para el ensemble.

## 4. Barrido del umbral de margen

| Umbral | Auto-registradas | Exact. auto | Errores escapados | Detecta errores | A revisión (tía) | Exact. final\* |
|---:|---:|---:|---:|---:|---:|---:|
| 0,00 (sin compuerta) | 100 % | 94,0 % | 18 | 0 % | 0 % | 94,0 % |
| 0,03 | 96 % | 95,8 % | 12 | 33 % | 4 % | 96,0 % |
| 0,05 | 95 % | 95,8 % | 12 | 33 % | 5 % | 96,0 % |
| 0,08 | 91 % | 96,4 % | 10 | 44 % | 9 % | 96,7 % |
| 0,10 | 89 % | 96,3 % | 10 | 44 % | 11 % | 96,7 % |
| 0,12 | 86 % | 97,3 % | 7 | 61 % | 14 % | 97,7 % |
| **0,15** ⭐ | **83 %** | **98,0 %** | **5** | **72 %** | **17 %** | **98,3 %** |
| 0,18 | 79 % | 97,9 % | 5 | 72 % | 21 % | 98,3 % |
| 0,20 | 75 % | 98,2 % | 4 | 78 % | 25 % | 98,7 % |
| 0,25 | 69 % | 98,6 % | 3 | 83 % | 31 % | 99,0 % |
| 0,30 | 62 % | 98,4 % | 3 | 83 % | 38 % | 99,0 % |

\* *Exactitud final = si la tía corrige el 100 % de la cola «por verificar».*

## 5. Lectura del punto operativo (0,15)

- 🟢 **83 %** se auto-registra con **98,0 %** de acierto → *este es el «0,98 en 83 %» ya medido de forma independiente.*
- 🔴 **5 errores escapan** (28 % de los 18) → **riesgo residual real** del sistema.
- 🟡 La compuerta **detecta el 72 %** de todos los errores y los manda a la tía.
- 🏁 **Exactitud final del sistema: 98,3 %** (con revisión humana de la cola).
- 📐 **0,15 es el codo**: subir a 0,20 baja los errores escapados de 5 → 4 (apenas −1) pero
  sube la carga de la tía de 17 % → 25 %. Casi el doble de revisión por un solo error menos.

## 6. Muestreo de auditoría de la cola auto-registrada

La cola «por verificar» (17 %) tiene revisión humana. La cola **auto-registrada** (83 %) **no**:
su calidad se controla por **muestreo**. Con la tasa de error observada (**2,0 %** = 5/249):

**a) Verificación por cota (regla de tres).** Con **0 errores** en `n` muestras al azar, la cota
superior al 95 % de la tasa de error es `3/n`:

| Cota que se quiere sostener | n a auditar |
|---:|---:|
| ≤ 10 % | 30 |
| ≤ 5 % | 60 |
| ≤ 3 % | 100 |
| ≤ 2 % | 150 |

**b) Estimación con precisión.** `n = 1,96²·p(1−p)/e²`, con `p = 2 %`:

| Precisión buscada (±) | n |
|---:|---:|
| ±1 pp | 753 |
| ±2 pp | 189 |
| ±3 pp | 84 |

**Recomendación operativa:** auditar al azar **~10 % de las auto-registradas por período**
(o **n = 30 por jardín/semana**, estratificado por educadora) **+ el 100 % de la cola «por verificar»**.
Con 30 muestras al azar y 0 errores se sostiene una tasa ≤ 10 % (95 %); para una cota más fina
(≤ 3 %) subir a ~100. La estratificación por educadora permite además detectar sesgos entre salas.

## 7. Caveats (para no vender de más)

1. **Set sintético.** Las 300 notas derivan de **90 manifestaciones fijas**, así que la medición
   mide *aprender el catálogo + combinar*, **no** generalización a campo. En producción la tasa de
   revisión será **mayor** (más variabilidad) y la de acierto, **menor**.
2. **Laya base no calibrada.** El checkpoint base emite un *warning* de temperaturas inválidas
   («confidence uncalibrated»): el margen **separa empíricamente** (por eso la compuerta funciona),
   pero la calibración fina de la confianza queda pendiente.
3. **La edad explica casi todo el acierto** (ver `EVAL_ENSEMBLE.md` §3). En los casos donde el
   niño se aparta de su edad (rezago/adelanto) la compuerta **protege menos**: sobre el set
   «contra la edad» (60 casos, `bench/reporte_compuerta.md`) acepta el 62 % y solo 17/37 son
   correctos. **La métrica del §4 es sobre casos al azar; el §6 (auditoría) es justamente el
   control que atrapa esa cola en producción.**

## 8. Decisión

- **Mantener** el umbral de margen en **0,15** (codo cobertura/precisión).
- **Adoptar** el muestreo de auditoría del §6 como control de calidad de la cola auto-registrada.
- **Pendiente relacionado:** activar la regla de discrepancia texto-edad de `src/compuerta.py`
  (hoy desactivada) si Integra prioriza cazar rezagos a costa de más revisión — decisión de
  política, medida en `bench/reporte_compuerta.md`.
