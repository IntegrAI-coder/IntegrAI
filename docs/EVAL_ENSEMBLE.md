# Revisión de la evaluación del ensemble (15-oct)

Revisa los números publicados del ensemble (híbrido 0,6 + Laya 0,4, con compuerta de margen ≥ 0,15) y los contrasta con una medición independiente del **clasificador desplegado** en `integra-server` (`POST /clasificar`, `backend: ensemble`).

## 1. Lo que se reportó (blog del día 1)

| Motor | Exacto | ±1 |
|---|---:|---:|
| Laya base | 0,507 | 0,857 |
| Laya afinado v1 | 0,137 | 0,480 |
| Matcher híbrido | 0,663 | 0,690 |
| **Ensemble** | **0,940** | **0,973** |
| Ensemble + compuerta (margen ≥ 0,15) | 0,98 en los aceptados, con 83 % aceptado y **17 % a revisión** | — |

Sobre esos números:
- Se midieron sobre **300 notas sintéticas**. No se publicó cómo se generaron ni la matriz de confusión.
- Los pesos 0,6/0,4 y el umbral 0,15 parecen ajustados **sobre el mismo set** que se reporta. Sin un set aparte, el 94 % puede estar inflado.
- Laya v1 con 0,137 ≈ azar entre 9 niveles (0,11): coincide con el "colapso a la clase prior" descrito en `FEEDBACK_EQUIPO.md`.
- El 17 % de revisión es la fracción con margen < 0,15 en ese set, no en datos reales.

## 2. Medición independiente del despliegue

Usamos 30 casos que el ensemble nunca vio (`bench/casos.jsonl`). Son notas estilo tía chilena **parafraseadas** por Claude Haiku 4.5 desde las manifestaciones de 30 observaciones reales del dataset, con 3–4 casos por nivel. Script: `python -m bench.eval_api`.

| Variante | Nivel exacto | ±1 | A revisión | Exactos en aceptados |
|---|---:|---:|---:|---:|
| Ensemble con edad | **90 %** | 90 % | 20 % | 24/24 |
| Ensemble con edad, nota → conductas (etapa 2 de U2) | 90 % | 97 % | 10 % | 25/27 |
| **Ensemble sin edad (solo texto)** | **47 %** | 50 % | 50 % | 9/15 |
| **Solo la edad, sin leer el texto** | **100 %** | 100 % | — | — |

La matriz de confusión con edad es casi diagonal. El único error sistemático: 3 de los 4 casos de nivel 2 se predicen como nivel 5.

## 3. Conclusión: la edad explica casi todo el acierto

En el dataset sintético **el nivel está casi determinado por la edad**: el nivel más frecuente para cada edad en meses acierta el **98,5 %** de las 2.920 observaciones (ver también "Niveles por edad" en `distribucion_y_validacion.md`). Entonces:

1. **El 90–94 % del ensemble no demuestra que entienda la observación.** Un clasificador que ignora el texto y solo mira la edad saca 100 % en nuestros casos. Con el texto solo, el ensemble baja a 47 %.
2. **El valor real del producto está en los casos que se apartan de la edad**: rezagos o adelantos. Ahí la edad engaña y solo el texto puede detectar la diferencia. El dataset tiene 47 observaciones fuera del rango orientativo y 25 niños/as con una baja acotada. **Esa es la evaluación que importa** para el jurado y para Integra.
3. **La compuerta funciona con edad (24/24 aceptados correctos), pero sin edad se debilita: 9/15 aceptados correctos y 50 % a revisión.** Pero el 17 % depende de qué tanto empuje la edad, y en datos reales con rezago la tasa de revisión será mayor.

## 4. Recomendaciones antes del pitch

- Reportar **siempre tres números**: solo edad, solo texto y ensemble. Si el ensemble no supera a "solo edad", el aporte de la IA no se ve.
- Armar un set de evaluación **"contra la edad"**: observaciones donde el `nivel_estimado` difiere del nivel típico de la edad, más casos sintéticos de rezago (por ejemplo, un niño de 24 meses con conductas de nivel 5). Medir exacto, ±1 y **recall de alerta de rezago**.
- Separar el set de ajuste (pesos 0,6/0,4, umbral 0,15) del set de reporte.
- Usar la etapa 2 de U2 (nota → conductas) delante del ensemble: con el mismo texto sube el ±1 de 90 % a 97 % y baja la revisión de 20 % a 10 %. El efecto del matcher solo es mayor (ver `bench/reporte_sint.md`).

## 5. Set "contra la edad" (`bench/casos_contra_edad.jsonl`, 60 casos)

Armado con `python -m bench.contra_edad`. Tiene 20 observaciones reales con nivel ≠ típico de su edad (en el dataset todas están 1 nivel bajo lo típico), 20 rezagos sintéticos de 2–3 niveles, 10 adelantos de 1–2 niveles y 10 controles en el nivel típico. Evaluado con `python -m bench.eval_api --casos casos_contra_edad.jsonl --conductas`.

| Variante | Exacto | ±1 | A revisión | Exactos en aceptados | Exacto adelanto | Exacto control | Exacto real (−1) | Exacto rezago (−2/−3) | Recall alerta rezago | Precisión alerta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Solo edad (sin texto) | 17 % | 62 % | 0 % | 10/60 | 0 % | 100 % | 0 % | 0 % | 0 % | — |
| Ensemble con edad (desplegado) | 47 % | 73 % | 38 % | **17/37** | 30 % | 80 % | 45 % | 40 % | 50 % | 95 % |
| Ensemble sin edad | 48 % | 70 % | 50 % | 19/30 | 20 % | 30 % | 70 % | 50 % | 78 % | 76 % |
| **Ensemble con edad + conductas U2** | **72 %** | **88 %** | **23 %** | **37/46** | **70 %** | **90 %** | 65 % | **70 %** | **80 %** | **97 %** |

**Lectura:**
1. Cuando el niño no calza con su edad, el ensemble desplegado baja a **47 %** exacto y detecta **la mitad** de los rezagos.
2. **La compuerta no protege en estos casos:** de los 37 que aceptó sin revisión, solo 17 eran correctos. El prior de edad le da confianza alta a respuestas equivocadas: el sistema "aprueba" justo los casos de rezago que debería mandar a la tía.
3. **Poner la etapa 2 de U2 (nota → conductas) delante del ensemble** sube el exacto de 47 % a 72 % y el recall de rezago de 50 % a 80 %, con 97 % de precisión. Además baja la revisión de 38 % a 23 %. Es el cambio de mayor impacto y no toca el ensemble.

**Recomendaciones para la compuerta:**
- Mandar a revisión siempre que la predicción del texto y el prior de edad discrepen (por ejemplo, si el voto del híbrido sin edad está a ≥ 2 niveles del nivel típico), aunque el margen sea alto.
- Calibrar el umbral de margen **en este set**, no en el aleatorio.

## 6. Compuerta de revisión (`src/compuerta.py`, `bench/reporte_compuerta.md`)

Medido sobre las respuestas reales de `/clasificar` (90 casos: 30 al azar y 60 contra la edad). Un *rezago que se escapa* es un niño/a bajo lo típico para su edad que el sistema acepta sin revisión y sin marcarlo.

| Compuerta | A revisión (al azar) | A revisión (contra la edad) | Exactos en aceptados (contra la edad) | Rezagos que se escapan |
|---|---:|---:|---:|---:|
| Actual (margen < 0,15), nota original | 20 % | 38 % | 17/37 | **16/40** |
| Actual, **nota → conductas U2** | **10 %** | 27 % | 37/44 | **6/40** |
| + discrepancia texto-edad ≥ 2 | 13 % | 50 % | 24/30 | 5/40 |
| + discrepancia ≥ 1 | 20 % | 78 % | 9/13 | 4/40 |

**Decisión recomendada:** pasar la nota a conductas (U2) y mantener la compuerta de margen. La regla de discrepancia queda implementada pero **desactivada**: evita un rezago más a costa de duplicar la revisión en los casos difíciles. Es una decisión de política para Integra (cuánta revisión aceptan las tías), no técnica.
