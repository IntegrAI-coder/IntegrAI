# PR 06 — Data science: análisis de manifestaciones categorizadas

## Contexto
El catálogo de manifestaciones (nivel × dominio) tiene un uso real en las
observaciones que puede no corresponder a lo esperado. Este PR agrega un análisis
estadístico que compara **observado vs. esperado** y lo interpreta.

## Objetivo
Enlazar el backend (`src.config` + `src.plataforma`, el mismo SQLite que usa
`app.py` y el dashboard) y analizar el catálogo de manifestaciones frente a su
uso real, generando un HTML con gráficos comparativos e interpretados (4 tiempos).

## Qué incluye
Verificado con `git log --oneline origin/main..Ivan -- datascience/analisis_manifestaciones.py`:

| Archivo | Qué aporta |
|---|---|
| `datascience/analisis_manifestaciones.py` | Análisis + generación del HTML |
| `datascience/analisis_manifestaciones.html` | Artefacto generado |

Commit: `b2c8a6c feat(datascience): analisis de manifestaciones categorizadas y vinculos con observaciones (script + HTML)`.

## Por qué merece su propio PR
Es un análisis **exploratorio de datos** autocontenido (script + HTML), sin
dependencias del frontend ni del backend de servicio. Temáticamente distinto del
resto.

## Decisiones y notas técnicas
- **Profundiza** el gráfico "Evidencias por nivel y dominio" del dashboard, con
  **comparativos** (observado vs. esperado) e **interpretados** (cada uno con
  lectura en 4 tiempos: Qué veo / Qué significa / Por qué importa / Qué hago).
- **Fuentes flexibles:** por defecto lee el SQLite; con `--csv` ignora el SQLite
  y con `--datos ruta` usa CSV; con `--abrir` abre el HTML.
- **Sin red:** Plotly por CDN.

## Cómo probarlo
```powershell
$env:PYTHONIOENCODING='utf-8'
python datascience/analisis_manifestaciones.py --abrir
python datascience/analisis_manifestaciones.py --csv --datos data
```

## Riesgos y limitaciones
- Si el SQLite no tiene la tabla `manifestaciones`, el flujo depende de los CSV
  (usar `--csv`).
- Artefacto HTML generado; se regenera con el script.

## Criterios de aceptación
- [ ] `python datascience/analisis_manifestaciones.py` genera el HTML sin error.
- [ ] Los gráficos comparativos muestran observado vs. esperado.
- [ ] Cada gráfico incluye su lectura en 4 tiempos.

## Evidencia
- Commit `b2c8a6c` en la rama **Ivan** (verificado 2026-10-15).
- `datascience/analisis_manifestaciones.html` presente en la rama.
