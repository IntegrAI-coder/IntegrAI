# Plan B Laya — ¿mejora el ensemble el modelo afinado? **No.**

Medición del **Plan B**: reemplazar la componente Laya del ensemble (Laya **base**) por el
checkpoint afinado **`laya-integra3`**. Sobre el benchmark interno de 300 notas (semilla
`20261014`), con el ensemble desplegado (`0,6 · híbrido ⊕ 0,4 · Laya`).

## 1. Resultado — el ensemble **empeora**

| Motor | Exacto | ±1 |
|---|---:|---:|
| Híbrido (matcher + prior etario) | 0,663 | 0,690 |
| Laya **base** | 0,507 | 0,857 |
| **`laya-integra3`** (standalone, en el pipeline) | 0,540 | 0,687 |
| **Ensemble con Laya base** (desplegado) | **0,940** | **0,973** |
| **Ensemble con `laya-integra3`** | **0,717** | **0,817** |

Cambiar Laya base → `laya-integra3` **baja el ensemble de 0,940 a 0,717**. El "Plan B" **no ayuda**;
mantener la Laya base es la decisión correcta.

> Nota: el **Laya base tiene peor exacto (0,507) que `laya-integra3` (0,540)**, y aun así el
> ensemble con base llega a **0,940**. La razón: lo que aporta Laya al ensemble son sus
> **probabilidades calibradas** (bien repartidas), no su argmax. `laya-integra3` es
> **sobreconfiado** (p≈0,99) y arrastra el ensemble hacia sus aciertos *y* sus errores.

## 2. ¿Por qué? El fine-tune es **frágil a la entrada**

`laya-integra3` se entrenó con `state = "Conductas observadas: <manifestaciones GOLD>. Nota de la
educadora: <nota>"`. Medimos el mismo modelo con tres entradas (300 casos):

| Entrada a `laya-integra3` | Exacto | ±1 |
|---|---:|---:|
| **GOLD** (las manifestaciones del dataset = las del entrenamiento) | 0,890 | 0,913 |
| **MATCHER** (las que detecta el matcher en el pipeline real) | **0,540** | 0,687 |
| **NOTA** (la nota cruda, sin manifestaciones) | 0,323 | 0,530 |

**Lectura:** el fine-tune **memorizó el mapeo manifestaciones-gold → nivel** (0,890), pero **no
generaliza** a la evidencia que el matcher entrega en producción (0,540). El "96,3 %" del held-out
(ver `EVAL_LAYA_HELDOUT.md`) es la misma película: se midió con las manifestaciones gold.

## 3. Conclusión

1. **Plan B descartado:** el modelo afinado **no mejora** el ensemble; lo degrada (0,940 → 0,717).
2. **El 96,3 % no era generalización:** era **memorización del catálogo + input perfecto**. En el
   pipeline real cae a **0,540**.
3. **La palanca no es el modelo, es el harness:** el ensemble con Laya **base** (peor modelo, pero
   probabilidades calibradas) + el gate por margen llega a **0,940 / 0,98**. *El modelo es commodity;
   la decisión es el producto.*

**Recomendación:** mantener **Laya base** en el ensemble. Si se quiere aprovechar un modelo afinado,
habría que **re-entrenarlo con la salida real del matcher** (no con las manifestaciones gold) y con un
held-out sin fugas — y volver a medir. No es un ajuste de hoy.

## 4. Reproducir (en `integra-server`)

```bash
cd /opt/integra
.venv/bin/python evaluar_ensemble_laya.py 300    # ensemble con base vs integra3
.venv/bin/python eval_integra3_input.py 300      # sensibilidad de entrada del fine-tune
```

- `evaluar_ensemble_laya.py` monta el ensemble con ambas Laya; para el afinado construye el
  `state`/`criteria` **exactos del fine-tune** (si no, el modelo recibe basura).
- `eval_integra3_input.py` mide el mismo modelo con entrada GOLD / MATCHER / NOTA.

*Shiva · IntegrAI (AWS Breaking Barriers Chile 2026) · 15-oct-2026.*
