# IntegrAI-MM · benchmark de ingesta multimodal (U2)

No hay un benchmark público para notas de voz de educadoras chilenas ni para post-its manuscritos en español. Por eso medimos **el resultado final**: ¿el matcher encuentra las manifestaciones correctas y el decisor el nivel correcto, cuando la observación llega como audio o foto en vez de texto?

## Pasos

```bash
pip install pydantic faster-whisper pillow boto3
python -m bench.guiones --n 30          # casos.jsonl: guion + ids_manifestacion + nivel (desde el dataset)
python -m bench.sinteticos              # medios/sint/{audio,postit}/Cxx.* (Polly + fuentes manuscritas)
python -m bench.run --medios sint --pipelines all
```

## Medios del equipo (`medios/equipo/`, NO se suben al repo)

Usa `casos.jsonl` como guion. **Sin niños reales**: los videos se actúan con un muñeco o entre adultos.

| Tipo | Cuántos | Cómo | Nombre |
|---|---|---|---|
| Audio | 10 (C01–C10) | Nota de voz de WhatsApp leyendo o improvisando el guion; exportar el `.ogg`/`.opus` | `medios/equipo/audio/C01.ogg` |
| Post-it | 10 (C11–C20) | Escribir el guion a mano en un post-it y fotografiarlo con el celular | `medios/equipo/postit/C11.jpg` |
| Video | 5 (C21–C25) | 15–30 s actuando las conductas del guion | `medios/equipo/video/C21.mp4` |

Luego: `python -m bench.run --medios equipo --pipelines all`.

## Pipelines

| Pipeline | Qué es |
|---|---|
| `oraculo` | Guion tipeado: el techo del matcher |
| `oraculo+conductas` | Guion → etapa 2 (normalización conductual). ¿Ayuda al matcher? |
| `postit_legacy` | `procesadores.describir_imagen` original (Nova Pro "describe aprendizajes") |
| `postit_v2` | Claude Sonnet 5 literal + verificación con Nova 2 Lite + etapa 2 |
| `audio_small` | Whisper `small` (línea base original) |
| `audio_v2` | Whisper `large-v3-turbo` + prompt de vocabulario + etapa 2 |

**Criterio de éxito:** el pipeline v2 queda a ≤ 10 puntos de Recall@5 del oráculo y supera a la línea base.
