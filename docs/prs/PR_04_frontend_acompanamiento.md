# PR 04 — Frontend: acompañamiento (parvularia/directora) y legibilidad

## Contexto
El objetivo de producto es que la persona que acompaña al niño/a vea no solo el
dato, sino **qué significa y qué hacer**. Este PR convierte la página de
experiencia en un tablero de acompañamiento por rol, con foco en las
**manifestaciones por niño**, las **acciones de estimulación** y el **origen de
la alerta** de rezago, más mejoras de legibilidad en otras vistas.

## Objetivo
Que parvularias y directoras puedan: filtrar (sala/niño/dominio/foco), ver
manifestaciones por dominio, recibir acciones de estimulación priorizadas y
entender de dónde viene una alerta; y que los gráficos de las demás vistas sean
legibles (títulos, unidades, leyenda, notas).

## Qué incluye
Verificado con `git log --oneline origin/main..Ivan -- <rutas>`:

| Archivo | Qué aporta |
|---|---|
| `frontend/src/pages/Experiencia.tsx` | `PanelParvularia`, `FichaAcompanamiento`, `PanelDirectora`, `OrigenAlertas`, `Pipeline`; filtros y gráficos por rol |
| `frontend/src/domain/experiencia.ts` | `DOMINIOS` (5), `nombreDominio`, `dominiosCubiertos/Faltantes`, `diagnostico`, `resumenTrayectorias` |
| `frontend/src/domain/experiencia.test.ts` | Tests (8) |
| `frontend/src/domain/estimulacion.ts` | `ACCIONES_POR_DOMINIO`, `estadoManifestaciones`, `planEstimulacion(ficha, max=3)` |
| `frontend/src/domain/estimulacion.test.ts` | Tests (4) |
| `frontend/src/components/GraficoBarras.tsx` | Barras horizontales reutilizables (dominios, salas) |
| `frontend/src/components/GraficoDistribucion.tsx`, `GraficoTrayectoria.tsx`, `Tarjeta.tsx` | Legibilidad: títulos, unidades, leyenda, notas |
| `frontend/src/pages/Curso.tsx`, `Cursos.tsx`, `Nino.tsx` | Legibilidad y etiquetas claras |
| `frontend/src/App.tsx` | Ruta `/experiencia` |
| `frontend/src/estilos.css` | `.vista-filtrada`, `.columna-filtros`, `.origen-*`, `.lista-alertas`, `.estado-dominios`, `.estimulo__*`, `.foco`, `@media (max-width:820px)` |

Commits:
- `882d69a feat(frontend): pagina de acompanamiento (parvularia/directora) con trayectoria, dominios y pipeline; ruteada en /experiencia`
- `74eaf6e feat(parvularia): dashboard de manifestaciones y foco de apoyo en Experiencia`
- `0503c1e feat(dashboard): columna de filtros y graficos por rol, con estado y origen de las manifestaciones`
- `1e03f0d feat(dashboard): legibilidad para parvularias - titulos y unidades en graficos, leyenda, notas y etiquetas claras`

## Por qué merece su propio PR
Es la feature de **producto/frontend** más voluminosa y con más lógica de dominio
testeada. Se puede revisar por sí sola y es independiente de los PRs de backend.

## Decisiones y notas técnicas
- **Tres roles con distinto enfoque:** `PanelParvularia` (niño/foco), `PanelDirectora`
  (sala/jardín, salas al 100% de alerta), `Pipeline`/trayectoria.
- **Foco de apoyo:** `planEstimulacion` prioriza dominios **sin evidencia** y de
  **menor nivel**; devuelve hasta 3 acciones.
- **Transparencia de la alerta:** sección "De dónde viene esta alerta" +
  componente `OrigenAlertas` (regla + agregados) para que el sistema **proponga**
  y la educadora **decida**.
- **Gráfico de barras propio** (`GraficoBarras.tsx`) en vez de librería pesada;
  helper `pluralizar` evita template literals anidados que rompían `tsc`.

## Cómo probarlo
```powershell
& "C:\Program Files\nodejs\npm.cmd" test --silent -- --run   # en frontend/
& "C:\Program Files\nodejs\npm.cmd" run build
```

## Riesgos y limitaciones
- **Datos sintéticos:** el "100% de alerta" que a veces aparece al filtrar es un
  **artefacto del dataset E-1** (edades concentradas 18–31 meses → nivel esperado
  8–9, con nivel vigente casi uniforme 1–9), **no** un problema del cálculo. El
  dashboard ahora lo explica en la sección de origen.
- **Solapamiento de archivos** con el PR 03 en `App.tsx` y `estilos.css`.

## Criterios de aceptación
- [ ] `experiencia.test.ts` (8) y `estimulacion.test.ts` (4) pasan.
- [ ] `npm run build` compila.
- [ ] Los filtros (sala/niño/dominio/foco) recalculan la ficha.
- [ ] La ficha muestra manifestaciones, acciones y origen de la alerta.

## Evidencia
- `vitest` en la rama **Ivan**: **38 passed** (incluye `experiencia.test.ts` 8,
  `estimulacion.test.ts` 4) (verificado 2026-10-15).
