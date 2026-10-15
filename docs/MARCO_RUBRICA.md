# Marco principal: rúbrica oficial de Integra (Identidad y Autonomía)

> 15-oct-2026 · Mauricio (marco + multimodal + evaluación). Entrega para Sebastián (ensemble/Laya) y Santiago (dashboard) al final.

## 1. Qué cambió

Fundación Integra envió su rúbrica real del **núcleo Identidad y Autonomía** (ámbito Desarrollo Personal y Social). Desde ahora es el **marco principal** del sistema. Los 9 niveles × 5 dominios del dataset sintético quedan para regresión.

| | Antes (dataset E-1) | Ahora (rúbrica Integra) |
|---|---|---|
| Escala | 9 niveles, 0–36 meses | **8 niveles por tramo**: 1 Comenzando · 2 Explorando · 3 Desarrollando · 4 Afianzando · 5 Integrando · 6 Ampliando · 7 Consolidando · 8 Profundizando |
| Alcance | 5 dominios (motor, lenguaje, cognitivo, socioemocional) | 1 núcleo (Identidad y Autonomía) de los 10; los otros 9 llegarán después |
| Edades | 0–3 años | **0–6 años**, en 3 tramos |
| Rol de la edad | Casi determinaba el nivel (98,5 %) | **Solo elige el tramo**; dentro del tramo hay que leer la observación |

## 2. Tramos (ChileAtiende, ficha 1786)

El tramo se define por la **edad al 31 de marzo del año escolar**. El año escolar parte en marzo: una observación de enero o febrero pertenece al año anterior. Un niño/a nacido después del 31 de marzo queda en Sala Cuna Menor.

| Tramo (tabla de la rúbrica) | Subtramos | Edad al corte | Observaciones del dataset |
|---|---|---|---|
| Sala Cuna | Menor · Mayor | 0–12 · 12–24 meses | 2.183 · 682 |
| Nivel Medio | Menor · Mayor | 24–36 · 36–48 meses | 85 · **0** |
| Transición | NT1 · NT2 | 48–60 · 60–72 meses | **0** |

Medio Mayor y Transición **no tienen datos en el dataset**: se evalúan con los casos construidos desde la rúbrica (§5). Si la edad es mayor a 72 meses o desconocida, el sistema **no adivina**: pide la edad o el tramo a la educadora.

## 3. Cómo se usa en el código

| Pieza | Archivo |
|---|---|
| Rúbrica .docx → JSON (**no se versiona**: material de Integra) | `tools/importar_rubrica.py "<rúbrica>.docx"` → `privado/marcos/integra_identidad_autonomia.json` (fuera de `data/`, que el frontend publica) |
| Marco intercambiable (`MARCO=integra_iya` por defecto, `dataset_e1` para regresión) | `src/marcos.py`: `tramo_por_edad`, `niveles`, `nombre_nivel`, `descripcion_nivel`, `anclas`, `dimensiones_observables` |
| Matcher con anclas externas, filtro por tramo y leave-one-out (compatible con lo anterior) | `src/matcher.py` (`Matcher(anclas=…)`, `matchear(…, tramo=, excluir=)`) |
| Clasificador base por rúbrica (la línea base que el ensemble debe superar) | `src/clasificador_rubrica.py` |
| Dataset unificado por tramos + crosswalk tentativo E-1 → rúbrica | `tools/unificar_dataset.py` → `data/marcos/crosswalk_e1_integra.json`, `bench/dataset_tramos.csv` |

**Anclas:** por cada tramo y nivel, la descripción, la conducta observable y los 2 ejemplos (`IYA-SC-N04-E2` = Sala Cuna, nivel 4, ejemplo 2). Son 96 en total.

**Crosswalk tentativo (validar con Integra):** Sala Cuna E-1 L1…L8 → 1…8. Nivel Medio E-1 L7–L8 → 1, L9 → 2. Sirve para correr regresiones con el dataset en la escala nueva. No es una equivalencia oficial.

## 4. Mejoras del modelo multimodal (MM v2)

Los ejemplos de la rúbrica muestran **qué separa un nivel de otro**. La v1 lo perdía al convertir la nota en conductas:

| Lo que separa niveles | Regla nueva en U2 |
|---|---|
| Lo que el niño **dice** ("¡mío!", "¡lo logré!", "estoy enojado porque…") | Se conserva textual entre comillas, también en el campo `dicho_nino` |
| Grado de apoyo (con ayuda → con recordatorio → sin que se lo pidan → por iniciativa propia) | Se conserva siempre |
| Contexto (rutina, conflicto, espejo, separación, juego simbólico, proyecto) | Va en la misma conducta |
| Cómo expresa o regula la emoción y si explica el motivo | Se conserva |

- Los ejemplos de estilo del prompt son **propios, no de la rúbrica**, para no filtrar la evaluación, que se construye desde ella.
- Video y foto de escena: el prompt agrega las dimensiones del marco activo (`dimensiones_observables`) y pide citar lo que dice el niño.
- El vocabulario de Whisper incluye las rutinas (colación, babero, siesta, asamblea) y frases típicas.
- `webhook_ec2.py` usa la v2 automáticamente si la rúbrica está instalada; si no, la v1.

## 5. Evaluación

`bench/rubrica_casos.py` genera **168 casos** (no se versionan: derivan de la rúbrica), cubriendo los 3 tramos:
- **144 paráfrasis:** 2 por cada conducta y ejemplo, escritas por Claude Haiku 4.5 como nota de tía chilena. Al clasificar se **excluye del matcher el ancla de origen** (leave-one-out).
- **24 escenarios nuevos:** 1 por nivel y tramo, escritos **solo desde la descripción**, sin ver los ejemplos. Es la prueba más dura.
- La edad es aleatoria dentro del subtramo; el sistema deriva el tramo.

`python -m bench.eval_rubrica --variantes solo_edad,crudo,mm_v1,mm_v2` → `bench/reporte_rubrica.md`

**Resultados (15-oct, 168 casos; azar con 8 niveles = 12,5 %):**

| Variante | Exacto | ±1 | Sala Cuna | Nivel Medio | Transición | Paráfrasis | Escenarios nuevos | A revisión | Correctos en aceptados |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Solo edad (sin leer la nota) | 12 % | 34 % | 9 % | 14 % | 14 % | 12 % | 12 % | — | — |
| Matcher · nota cruda | 43 % | 58 % | 38 % | 52 % | 41 % | 43 % | 46 % | 41 % | 51/99 |
| Matcher · MM v1 (conductas) | 42 % | 59 % | 41 % | 46 % | 38 % | 41 % | 46 % | 29 % | 62/119 |
| Matcher · **MM v2** | 44 % | 57 % | 46 % | 45 % | 41 % | 42 % | 54 % | 30 % | 61/118 |
| **Juez LLM con la rúbrica** (`JuezRubrica`) | **65 %** | **69 %** | 62 % | 70 % | 64 % | 65 % | **71 %** | 26 % | **110/124 (89 %)** |

**Lectura:**
1. **La trampa de la edad desapareció:** "solo edad" da 12 %, igual que el azar. Dentro del tramo hay que leer la observación.
2. **El matcher por similitud llega a ~44 %:** comparar frases no captura lo que separa niveles ("con recordatorio" contra "sin recordatorio", "verbaliza el motivo"). Los errores son lejanos (4 → 8), no de un nivel.
3. **El MM v2 mejora poco con el matcher** (+8 puntos solo en escenarios nuevos), porque el matcher no aprovecha los rasgos que la v2 conserva.
4. **El juez LLM**, que lee la rúbrica completa del tramo y entrega una salida Pydantic con el nivel restringido a 1–8, sube a **65 %**, y a **89 % en los casos que acepta sin revisión**. En las paráfrasis se le saca del prompt el ejemplo de origen (leave-one-out), así que el número no está inflado por copia.
5. Medio Mayor y Transición, sin datos en el dataset, rinden igual que Sala Cuna: la rúbrica cubre las edades que el dataset no tiene.

**Recomendación para el ensemble:** agregar `JuezRubrica` como **voto principal**, con el matcher y Laya como votos de apoyo, y mandar a revisión cuando el juez tenga confianza < 0,6 o discrepe del matcher en 2 niveles o más. Detalle de matrices de confusión en `bench/reporte_rubrica.md`.


## 6. Entrega para el resto del equipo

**Sebastián (ensemble / Laya / servicio):**
1. `backend_decision.py`: reemplazar `NIVELES = range(1, 10)` y `1 <= l <= 9` por `marcos.marco_activo().niveles(tramo)`. Criterios de Laya = `descripcion_nivel(tramo, n)`.
2. **No usar prior de edad dentro del tramo.** La edad ya se usó para elegir el tramo; dentro de él, repetiría la trampa del 98,5 %.
3. `webhook_ec2.py`: tramo = `tramo_por_edad(fecha_nac, fecha_obs)`. Si es `None`, pedir la edad. Pasar el tramo al clasificador. Guardar `marco`, `tramo`, `subtramo`, `nivel` y `nombre_nivel`. Responder: "Sala Cuna · nivel 4 Afianzando (propuesta)".
4. En la EC2: copiar el docx y ejecutar `python tools/importar_rubrica.py <docx>` (el JSON no viene en el repo).
5. Usar **`JuezRubrica`** (65 % exacto, 89 % en aceptados) como voto principal. `ClasificadorRubrica` (matcher) y Laya quedan como votos de apoyo y para detectar discrepancias.

**Santiago (dashboard):** mostrar tramo + nombre del nivel. Alerta de rezago: "nivel bajo para su subtramo"; el umbral se define con Integra.

**Choques revisados con `main` (PR #10 y #11):**
- El frontend publica `data/` completo (`vite.config.ts: publicDir: '../data'`). Por eso la rúbrica vive en `privado/`, que no se versiona ni se publica. **Santiago:** servir los datos por una API con autenticación (hallazgo H16 de `SEGURIDAD.md`).
- `docs/METRICAS_GATE.md` (umbral 0,15, 98 % en aceptados) se midió sobre la escala vieja de 9 niveles **con la edad como pista**, que con el dataset predice el nivel en el 98,5 % de los casos. Con la rúbrica, la compuerta debe recalibrarse sobre `bench/casos_rubrica.jsonl`. Con el juez, confianza < 0,6 deja 26 % a revisión y 89 % de exactitud en los aceptados.

**Integra (pendiente):** los otros 9 núcleos; validar el crosswalk; confirmar si la rúbrica puede publicarse; definir el umbral de rezago por subtramo.
