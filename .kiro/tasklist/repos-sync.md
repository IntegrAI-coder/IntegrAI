# Tasklist · Sincronización de repos + RAG

Estado: **completado** (backend + frontend + tests). Rama: `Ivan`.

## Fase A · Backend (core)

- [x] `src/repos/sincronizacion.py` — validación de URL, `clonar_repo`,
      `escanear_repo`, `listar_repos`, `resumen`, confinamiento de rutas.
- [x] `src/repos/rag.py` — `trocear`, `embedding` (Bedrock Titan / MOCK),
      `ingestar_archivo`, `ingestar_repo` con metadatos `synthetic_code`.
- [x] `src/repos/endpoints.py` — router `/api/repos/*` con token.
- [x] `src/repos/__init__.py` — API pública.

## Fase B · Integración

- [x] `webhook_ec2.py` — `include_router` de los endpoints de repos.
- [x] `.gitignore` — excluir `repos/` (código de terceros).

## Fase C · Frontend

- [x] `frontend/src/domain/repos.ts` — `parsearUrlRepo` (espejo del backend).
- [x] `frontend/src/data/api.ts` — cliente HTTP (`VITE_API_URL`, `VITE_API_TOKEN`).
- [x] `frontend/src/pages/Sincronizacion.tsx` — clonar/escanear/indexar + tablas.
- [x] `App.tsx` — ruta `/sincronizacion` y navegación.
- [x] `estilos.css` — estilos de formulario, botón, chips.

## Fase D · Verificación

- [x] `tests/test_repos.py` — 29 casos (URL, escaneo, troceado, embeddings,
      endpoints).
- [x] `python -m pytest -q -o addopts=` → 81 passed.
- [x] `frontend`: `npm run build` OK, `npm test` → 23 passed.
