# Steering · Sincronización de repositorios + RAG

Guía vinculante para cualquier cambio en el módulo de sincronización. Rige el
comportamiento del backend (`src/repos/`) y del frontend (`Sincronizacion.tsx`).

## Alcance

Sincronizar repositorios **sintéticos** de GitHub (clonar → escanear → indexar en
el pipeline RAG) para alimentar la base de conocimiento del equipo. **Nunca**
datos reales de niños, niñas o apoderados: todo lo indexado lleva
`data_type = "synthetic_code"`.

## Requisitos (EARS)

- **R1** — *Cuando* el usuario envía una referencia de repo, el sistema *debe*
  validar la URL en cliente y servidor antes de ejecutar cualquier comando.
- **R2** — *El sistema no debe* aceptar más que `https://` del host permitido
  (`INTEGRA_REPOS_HOSTS`, por defecto `github.com`); cualquier otro esquema/host
  → error 400.
- **R3** — *Cuando* el clonado es exitoso, el sistema *debe* dejar el repo en
  `repos/[owner]/[repo]` confinado a `INTEGRA_REPOS_DIR` (sin path traversal).
- **R4** — *El sistema debe* clonar con `--depth 1` y sin `shell=True`, con
  `GIT_TERMINAL_PROMPT=0` (no autenticación interactiva) y timeout.
- **R5** — *Cuando* se escanea, el sistema *debe* ignorar `node_modules`, `.git`,
  `dist`, `build`, `data`, `.venv`, `vendor`, `target`, `coverage`, `__pycache__`,
  archivos ocultos y archivos > `INTEGRA_REPOS_MAX_BYTES`.
- **R6** — *Cuando* se indexa, el sistema *debe* trocear con solape y adjuntar
  metadatos `{source_repo, file_path, data_type, chunk_index, lenguaje}`.
- **R7** — *El sistema debe* generar embeddings con Bedrock Titan y degradar a
  MOCK determinista si no hay credenciales (`config.usar_mock()`).
- **R8** — *El sistema debe* acotar la indexación a `INTEGRA_MAX_CHUNKS` trozos e
  informar `truncado`.
- **R9** — *El sistema debe* exigir `INTEGRA_API_TOKEN` (cabecera `X-Api-Key`)
  cuando el token esté configurado (fail-closed).

## Superficie HTTP (FastAPI · `webhook_ec2.py`)

| Método | Ruta | Cuerpo | Devuelve |
| --- | --- | --- | --- |
| GET | `/api/repos` | — | `{repos: [...]}` |
| POST | `/api/repos/scan` | `{repo?}` | repos y/o archivos |
| POST | `/api/repos/clone` | `{url, indexar?}` | clon + escaneo (+ indexado) |
| POST | `/api/repos/index` | `{repo, max_trozos?}` | resumen de trozos/embeddings |

## Variables de entorno

`INTEGRA_REPOS_DIR`, `INTEGRA_REPOS_HOSTS`, `INTEGRA_REPOS_MAX_BYTES`,
`INTEGRA_CHUNK_CHARS`, `INTEGRA_CHUNK_OVERLAP`, `INTEGRA_MAX_CHUNKS`,
`INTEGRA_EMBED_DIM`, `MODELO_EMBEDDING`, `INTEGRA_API_TOKEN`.

## Reglas de estilo y seguridad

- Español en docstrings/UI; sin comentarios superfluos.
- Backend: stdlib + boto3 perezoso; funcional y testeable en MOCK.
- Frontend: React + TS estricto, sin dependencias nuevas; reutilizar
  `Tabla`, `Estado`, `Breadcrumbs`.
- Repo **público**: sin tokens, IDs de cuenta ni dominios reales.
