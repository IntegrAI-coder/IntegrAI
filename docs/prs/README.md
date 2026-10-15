# Descripción de PRs — rama `Ivan`

Documentación de los cambios que aporta la rama **`Ivan`** frente a `origin/main`,
agrupados en PRs pequeños por tema. **Sin abrir PRs, sin push y sin cambios de
código**: solo descripciones para facilitar la revisión e integración.

## Reconocimiento previo

- Rango: `git log --oneline origin/main..Ivan` (base = `36a4668`, el merge-base).
  → **11 commits**, todos del autor `icortesve` (la rama `Ivan`).
- Diff: `git diff --stat origin/main...Ivan` → **41 archivos**.
- `git status --porcelain` → **vacío** (no hay archivos sin commit en la rama).
- Template de PR: **no existe** `.github/pull_request_template.md`.
- `gh`: **no instalado** en el entorno → no se pudieron listar/ver PRs ni generar
  `REVISION_PR_*` (paso omitido, según lo indicado).
- `docs/CUMPLIMIENTO_DESAFIO.md`: **no existe**.

### Hallazgo importante (criterio de agrupación)
El trabajo de **infraestructura AWS / seguridad / TLS / CloudFront / IaC** **ya
está en `origin/main`** (`tools/*_aws.py`, `infra/`, `docs/INFRA.md`,
`docs/SEGURIDAD.md`), por lo que **no forma parte del diff de `Ivan`**. Por eso no
hay un "PR de Infra y seguridad": se agrupa **solo lo que realmente difiere** en
la rama, que es el **guardrail de seguridad IA** (`src/guardrails/*`).

## Índice de PRs

| PR | Tema | Commits | Depende de | Prioridad |
|---|---|---|---|---|
| [PR 01](PR_01_seguridad_guardrail_kiro.md) | Seguridad IA — guardrail preclasificador "Kiro" | `00ec0ab` | — | Independiente |
| [PR 02](PR_02_backend_repos_sync_rag.md) | Backend — sincronización de repos + RAG `/api/repos` | `01f40c8`, `d8084b4` | — | **Antes de PR 03** |
| [PR 03](PR_03_frontend_repos_sync.md) | Frontend — página de sincronización de repos | `c8a3ed8` | PR 02 | Alta |
| [PR 04](PR_04_frontend_acompanamiento.md) | Frontend — acompañamiento (parvularia/directora) y legibilidad | `882d69a`, `74eaf6e`, `0503c1e`, `1e03f0d` | — | Alta |
| [PR 05](PR_05_dashboards_datos_estado.md) | Visualización de datos y tablero de estado | `d7e4289`, `ef5caf4` | — | Media |
| [PR 06](PR_06_datascience_manifestaciones.md) | Data science — análisis de manifestaciones | `b2c8a6c` | — | Media |
| [PR 07](PR_07_documentacion_handoff.md) | Documentación y handoff — **PENDIENTE** | _(ninguno aún)_ | PRs 01–06 | Al final |

## Orden de integración recomendado

1. **PR 02** (backend repos) → habilita el PR 03.
2. **PR 03** (frontend repos).
3. **PR 01** (seguridad IA) — independiente, se puede integrar en cualquier momento.
4. **PR 04** (frontend acompañamiento) — independiente.
5. **PR 05** y **PR 06** (dashboards y datascience) — independientes.
6. **PR 07** (documentación) — al final, con todo integrado.

## Dependencias y solapamientos de archivos

- **PR 03 depende de PR 02** (necesita los endpoints `/api/repos/*`).
- **`frontend/src/App.tsx`** y **`frontend/src/estilos.css`** los tocan **PR 03 y
  PR 04**. Al integrar por separado hay que resolver ese solapamiento (cada PR
  agrega su propia ruta/bloque); recomendado integrar 03 y 04 juntos o en orden.
- **`.gitignore`** lo tocan **PR 02** (`/repos/`) y **PR 05** (artefactos locales).
- Los commits de merge (`d8084b4`) integran el trabajo del equipo desde `main`;
  verificar que no se reabran conflictos ya resueltos (ver PR 07 / guía de merge).

## Notas de verificación (rama `Ivan`, 2026-10-15)

- `python -m pytest -q -o addopts= --no-header` → **107 passed**.
- `npm test` (frontend, vitest) → **38 passed** (5 archivos):
  `metrics` 14, `consultas` 9, `experiencia` 8, `estimulacion` 4, `repos` 3.
- `npm run build` (frontend) → compila.
- [[PENDIENTE DE VERIFICAR]]: cifras tras integrar con `origin/main` (en una
  prueba previa con merge, pytest daba **114** y el build requería ajustar
  fixtures por campos nuevos `FichaNino.ajustadoManual` y `Datos.educadoras`).

> Estos documentos **no** se commitean ni se pushean hasta confirmación explícita.
