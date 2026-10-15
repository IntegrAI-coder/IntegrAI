# Evaluación honesta de Laya (held-out limpio)

> **TL;DR** — El `0.9865` que reporta `laya-train` está **inflado** (el set de eval se
> solapa con el de entrenamiento). Sobre un **held-out limpio** (135 items sin
> duplicado exacto), el checkpoint afinado da **96.3% exacto / 98.5% ±1**, contra
> **11.9%** del modelo base. El salto es **real**, pero hay un **caveat de fondo**.

## 1. El problema: eval contaminado

`laya-train` emite una advertencia explícita:

```
eval items 443 from data/eval.jsonl (skipped {}, 308 overlapping training/calibration items)
```

→ **308 de 443** items de evaluación aparecen también en entrenamiento/calibración.
Las métricas que reporta **no son** un held-out independiente.

## 2. El held-out limpio

Filtrando los items cuyo `state` **no** aparece en `train.jsonl`:

| | |
|---|---|
| Items de eval | **443** |
| Solapados (duplicado exacto) | −308 |
| **Held-out limpio** | ✅ **135** |
| Únicos (dedup por state) | 124 |

## 3. Resultados (verificados, reproducibles)

| Modelo / set | Exacto | ±1 |
|---|---|---|
| `base(laya)` sobre CLEAN 135 | 0.119 | 0.296 |
| `laya-integra2` sobre CLEAN 135 | 0.178 | 0.474 |
| **`laya-integra3` sobre CLEAN 135** | **0.963** (130/135) | **0.985** (133/135) |
| `laya-integra3` sobre CLEAN únicos | 0.960 | 0.984 |
| `laya-integra3` sobre **FULL 443** (contaminado) | 0.9865 | 0.9932 |

> **Control de sanidad:** nuestro harness reproduce **exactamente** el `0.9865`
> oficial sobre los 443 → la implementación es correcta, por lo que la cifra limpia
> (0.963) es confiable.

## 4. El caveat (honestidad radical) ⚠️

```
manifest overlap medio clean/train: 1.000  (min 1.00, max 1.00)
items con manifestaciones 100% NUEVAS: 0 de 135
```

**Todos** los items "held-out" reusan manifestaciones ya vistas en entrenamiento.
El dataset es **sintético de un catálogo fijo de 90 manifestaciones** (9 niveles × 10).
Por lo tanto:

- El 96.3% mide que el modelo **aprendió el catálogo y combina bien** → **no** prueba
  generalización a observaciones reales nuevas.
- **No existe** un set verdaderamente independiente disponible en el dataset del desafío.

## 5. Qué número usar en el pitch

✅ **Headline:** *fine-tuning elevó la exactitud de **11.9% → 96.3%** en un held-out sin duplicados exactos (135 items).*
✅ **Nota metodológica (nos distingue):** *"medimos el solapamiento y reportamos el número limpio, no el inflado; el dataset es sintético de un catálogo fijo, así que esto mide aprendizaje del catálogo + combinación, no generalización a campo."*

❌ **NO usar** el `98.65%` sin el contexto de contaminación.

## 6. Reproducir

```bash
# en la EC2 (integra-server), con el venv del proyecto
/opt/integra/.venv/bin/python evaluar_laya_heldout.py
```

Genera `data/eval_clean.jsonl` (el set limpio de 135) e imprime la tabla.

---
*Medición: 15-oct-2026 · Shiva · IntegrAI (AWS Breaking Barriers Chile 2026).*
