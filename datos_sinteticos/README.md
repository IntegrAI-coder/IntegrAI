# Datos sintéticos generados (trazabilidad)

Todo lo que hay aquí fue **generado** durante la hackathon (14–16 oct 2026) para evaluar el sistema. **No hay datos de niños/as reales**: notas escritas por modelos, voces sintéticas (Polly), post-its renderizados con fuentes manuscritas y un video animado. Cada archivo está en [`MANIFEST.csv`](MANIFEST.csv) con su **SHA-256**, script generador, modelo y descripción.

> Los apodos ("la Sofi", "el Benja") y los códigos `NINO-xxxxx` son ficticios (dataset sintético E-1).

## Contenido

| Carpeta | Qué es | Generado con | Usado en |
|---|---|---|---|
| `casos/casos_aleatorios_30.jsonl` | 30 notas estilo tía chilena desde observaciones del dataset E-1, estratificadas por nivel | `bench/guiones.py` · Claude Haiku 4.5 | `bench/run.py`, `bench/eval_api.py` |
| `casos/casos_contra_edad_60.jsonl` | 60 casos donde la edad no basta (20 reales discordantes, 20 rezagos, 10 adelantos, 10 controles) | `bench/contra_edad.py` · Haiku 4.5 | `docs/EVAL_ENSEMBLE.md` §5 |
| `casos/casos_rubrica_168.jsonl` | 144 paráfrasis + 24 escenarios nuevos de la rúbrica de Integra, en los 3 tramos (0–6 años) | `bench/rubrica_casos.py` · Haiku 4.5 | `docs/MARCO_RUBRICA.md` §5 |
| `medios/audio/C01–C30.mp3` | Los 30 guiones aleatorios leídos con voces neuronales | `bench/sinteticos.py` · Amazon Polly (es-US/es-MX) | Benchmark de audio |
| `medios/postit/C01–C30.jpg` | Los 30 guiones como post-it manuscrito (rotación, desenfoque) | `bench/sinteticos.py` · PIL + Caveat / Indie Flower / Patrick Hand (OFL) | Benchmark de post-it (CER 96 % → 1 %) |
| `medios/video/demo_pararse.mp4` | Figura que se para apoyada en una silla y luego camina sin apoyo (4 s) | `medios/video/generar_video.py` | Primera prueba de Pegasus |
| `salidas_modelos/` | Lo que respondieron los modelos para cada caso: conductas U2 v1/v2, veredictos del juez, respuestas del clasificador desplegado, detalle por caso de cada benchmark | ver `MANIFEST.csv` | Reproducir y auditar los resultados sin volver a llamar a Bedrock |
| `reportes/` | Reportes de evaluación que no estaban versionados | `bench/eval_api.py` | — |

Los reportes principales siguen en `bench/reporte_*.md`. Los casos originales que los scripts leen siguen en `bench/` (`casos.jsonl`, `casos_contra_edad.jsonl`); esta carpeta es la **copia de trazabilidad**.

## Cómo reproducir

```bash
python -m bench.guiones --n 30          # casos aleatorios (semilla 20261015)
python -m bench.sinteticos              # audio Polly + post-its
python -m bench.contra_edad             # set contra la edad
python tools/importar_rubrica.py "<rúbrica Integra>.docx" && python -m bench.rubrica_casos   # requiere la rúbrica
python -m bench.eval_rubrica --variantes solo_edad,crudo,mm_v1,mm_v2,juez
```

Los modelos generativos no son deterministas: una nueva corrida produce textos parecidos, no idénticos. Por eso se versionan los archivos exactos usados en los resultados publicados (verificables con `sha256sum` contra `MANIFEST.csv`).

## Nota sobre la rúbrica

`casos_rubrica_168.jsonl` y `salidas_modelos/juez_rubrica.json` **derivan de la rúbrica de Fundación Integra**: son paráfrasis de sus ejemplos y citas de sus descripciones. Se publican por decisión del equipo para mantener la trazabilidad. La rúbrica original (`privado/`) sigue fuera del repo. Si Integra pide no publicar material derivado, hay que borrar estos dos archivos y reescribir el historial.
