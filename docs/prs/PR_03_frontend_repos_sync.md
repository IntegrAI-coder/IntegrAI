# PR 03 — Frontend: página de sincronización de repositorios

## Contexto
Con los endpoints del PR 02 disponibles, falta la interfaz para que el equipo
vea, clone y escanee repositorios desde el panel. Este PR agrega la página
`/sincronizacion` y el cliente de API correspondiente.

## Objetivo
Permitir, desde la UI: listar repos clonados, clonar/actualizar un repo (por URL
o atajo `owner/repo`), escanear sus archivos y, opcionalmente, indexarlo en el RAG.

## Qué incluye
Verificado con `git log --oneline origin/main..Ivan -- frontend/src/pages/Sincronizacion.tsx frontend/src/domain/repos.ts frontend/src/data/api.ts frontend/src/App.tsx`:

| Archivo | Qué aporta |
|---|---|
| `frontend/src/pages/Sincronizacion.tsx` | Página: tabla de repos, formulario de clonado, acciones, estados |
| `frontend/src/domain/repos.ts` | `parsearUrlRepo` y utilidades de dominio |
| `frontend/src/domain/repos.test.ts` | Tests (3) |
| `frontend/src/data/api.ts` | Cliente `clonarRepo`, `listarRepos`, tipos `RepoResumen`, `ArchivoRepo` |
| `frontend/src/App.tsx` | Ruta `/sincronizacion` |
| `frontend/src/estilos.css` | Estilos de la vista |

Commit: `c8a3ed8 feat(frontend): pagina de sincronizacion de repositorios (clonar, escanear, indexar)`.

## Por qué merece su propio PR
Es una **feature de frontend con su propio test de dominio** y depende del
contrato del PR 02. Temáticamente distinta de la página de acompañamiento
(PR 04), aunque comparta `App.tsx` y `estilos.css`.

## Decisiones y notas técnicas
- **Reutiliza patrones existentes:** `Breadcrumbs`, `Tabla`, `Estado`
  (`Cargando`/`ErrorEstado`/`Vacio`), coherente con el resto del frontend.
- **Cliente API configurable:** `VITE_API_URL` (por defecto `http://localhost:8000`)
  y `VITE_API_TOKEN`.
- **UX de estados:** carga, error, vacío, aviso y envío en curso; selección de
  repo para ver detalle de archivos.

## Cómo probarlo
```powershell
& "C:\Program Files\nodejs\npm.cmd" test --silent -- --run   # en frontend/
& "C:\Program Files\nodejs\npm.cmd" run build
```
Requiere el backend (`webhook_ec2.py`) arriba para las llamadas reales; el
dominio (`repos.ts`) se testea sin red.

## Riesgos y limitaciones
- **Depende del PR 02** (endpoints `/api/repos/*`): sin él, la página carga pero
  las acciones fallan.
- **Solapamiento de archivos:** `App.tsx` y `estilos.css` también los toca el
  PR 04. Integrar en orden (02 → 03 → 04) o resolver el solapamiento al mergear.

## Criterios de aceptación
- [ ] `repos.test.ts` pasa (3 tests).
- [ ] `npm run build` compila.
- [ ] La página lista repos y permite clonar/escancar contra el backend.

## Evidencia
- `vitest` en la rama **Ivan**: **38 passed** en 5 archivos, incluido
  `src/domain/repos.test.ts (3 tests)` (verificado 2026-10-15).
