# PR 05 — Visualización de datos y tablero de estado del equipo

## Contexto
Además del tablero React, se necesitan dos artefactos HTML autocontenidos: uno
que **cuente la historia del dato** para parvularias y otro que muestre el
**avance del proyecto** (plan vs. realidad). Ambos se generan por script y no
requieren red.

## Objetivo
Producir (a) un dashboard de datos con relato en cuatro tiempos y adaptado al
rol, y (b) un tablero de estado del equipo que mida avance por área y conteo de
tests.

## Qué incluye
Verificado con `git show --stat d7e4289` y `git log --oneline origin/main..Ivan`:

| Archivo | Qué aporta |
|---|---|
| `dashboard/visualizar_datos.py` | Genera HTML autocontenido con KPIs y gráficos (Plotly por CDN) |
| `dashboard/visualizacion_datos.html` | Artefacto generado (vigente) |
| `tools/estado_proyecto.py` | Genera el tablero de estado del equipo (áreas, plan, tests) |
| `estado_proyecto.html` | Artefacto generado (raíz) |
| `.gitignore` | Ignora artefactos locales: `/visualizacion_datos.html` (raíz), `frontend/.vite/`, `eval_notas.json` |

Commits:
- `d7e4289 feat(dashboard): tablero de estado del equipo con plan y README (tools/estado_proyecto.py)`
- `ef5caf4 chore(dashboard): regenerar tablero de estado y excluir artefactos (visualizacion_datos.html raiz, frontend/.vite, eval_notas.json)`

## Por qué merece su propio PR
Son artefactos/herramientas de **presentación y seguimiento**, con dependencias
propias (pandas, plotly) y sin relación con el frontend React ni con el backend.
Se revisan aparte.

## Decisiones y notas técnicas
- **Dashboard de datos:** relato en 4 tiempos (**Qué veo / Qué significa / Por
  qué importa / Qué hago**), relato guiado ("la historia de un dato"), ingeniería
  de features (edad, tramo, nivel vigente/esperado, brecha, alerta de rezago,
  cobertura de dominios) y adaptación por rol.
- **Tablero de estado:** agrupa el plan en áreas (Infraestructura AWS,
  WhatsApp+clasificador, Frontend, Modelo multimodal U2+seguridad, Entrega/datos/
  tableros) y calcula avance y conteo de tests.
- **Sin red:** el HTML usa Plotly por CDN; los scripts no requieren credenciales.

## Cómo probarlo
```powershell
$env:PYTHONIOENCODING='utf-8'
python dashboard/visualizar_datos.py --abrir
python tools/estado_proyecto.py
```

## Riesgos y limitaciones
- **El tablero de estado solo cuenta tests de Python (pytest)**: su función
  `contar_tests` recorre `tests/test_*.py` y cuenta `def test_`; **no cuenta
  vitest**. Por eso "Frontend" aparece subrepresentado (solo registra
  `frontend/src/domain/consultas.test.ts`). **Mejora pendiente:** sumar los tests
  de frontend (`experiencia.test.ts`, `estimulacion.test.ts`, `repos.test.ts`) al
  conteo.
- Los `.html` son artefactos generados; se regeneran con los scripts.

## Criterios de aceptación
- [ ] `python dashboard/visualizar_datos.py` genera el HTML sin error.
- [ ] `python tools/estado_proyecto.py` genera `estado_proyecto.html`.
- [ ] Los artefactos locales no se versionan (`.gitignore`).

## Evidencia
- `d7e4289`: +3195 líneas en 4 archivos (`dashboard/visualizar_datos.py` 1584,
  `dashboard/visualizacion_datos.html` 681, `tools/estado_proyecto.py` 661,
  `estado_proyecto.html` 269).
- Tablero "avance global 86%", "Tests: 114" (este último contado **solo** sobre
  pytest; en la rama **Ivan** sin merge son **107**).
