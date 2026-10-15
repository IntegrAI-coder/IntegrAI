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
