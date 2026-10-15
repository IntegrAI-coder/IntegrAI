# PR 02 — Backend: sincronización de repos (clonar/escanear) + RAG `/api/repos`

## Contexto
El desafío pide poder **sincronizar repositorios de terceros** y usarlos como
contexto (RAG). Este PR implementa el pipeline en el backend: clonado seguro,
escaneo de archivos, troceo + embeddings y los endpoints HTTP que lo exponen.
Es la base sobre la que se apoya la UI del PR 03.

## Objetivo
Clonar repositorios **sintéticos** de forma higiénica, escanear su código y
prepararlo como ítems indexables (embeddings Bedrock Titan, o MOCK sin AWS),
exponiéndolo en `/api/repos/*`.

## Qué incluye
Verificado con `git log --oneline origin/main..Ivan -- src/repos tests/test_repos.py webhook_ec2.py .kiro`:

| Archivo | Qué aporta |
|---|---|
| `src/repos/sincronizacion.py` | Clonado seguro (`git clone --depth 1`), escaneo, utilidades de URL |
| `src/repos/rag.py` | Troceo + embeddings (Bedrock Titan o MOCK determinista), metadatos de trazabilidad |
| `src/repos/endpoints.py` | `APIRouter /api/repos` (`GET ""`, `POST /scan`, `POST /clone`, `POST /index`) protegido por token |
| `src/repos/__init__.py` | Reexporta la API del módulo |
| `tests/test_repos.py` | Tests del pipeline |
| `webhook_ec2.py` | Monta el router: `app.include_router(_repos_router)` |
| `.kiro/steering/repos-rag.md`, `.kiro/tasklist/repos-sync.md` | Guía/plan del trabajo (método AI-DLC) |
| `.gitignore` | Ignora `/repos/` (código de terceros clonado, no se versiona) |

Commits:
- `01f40c8 feat(repos): sincronizacion de repos con git seguro, escaneo y RAG (Bedrock/MOCK) + endpoints /api/repos/*`
- Parte de `d8084b4` (merge) integra `webhook_ec2.py`.

## Por qué merece su propio PR
Es una unidad de backend completa (seguridad de clonado + RAG + API) con su
propio test y contrato HTTP. Además **es dependencia** del PR 03 (frontend de
sincronización), por lo que conviene integrarlo antes.

## Decisiones y notas técnicas
- **Clonado higiénico (seguridad):** sin `shell=True` (lista de argumentos → sin
  inyección de comandos); URL validada a **https** de un **allowlist de hosts**
  (`INTEGRA_REPOS_HOSTS`, por defecto `github.com`); destino confinado a
  `REPOS_DIR` (fail-closed, sin path traversal).
- **Solo repos sintéticos:** metadatos `data_type="synthetic_code"`.
- **RAG sin nube:** sin credenciales AWS el embedding es determinista (hash →
  vector), para que el flujo sea demostrable y testeable offline.
- **Trazabilidad por ítem:** metadata con `source_repo`, `file_path`,
  `data_type`, `chunk_index`, `lenguaje`.
- **Auth:** los endpoints usan el token compartido `INTEGRA_API_TOKEN`
  (`hmac.compare_digest`). Si el token está vacío, la API queda abierta **solo
  para desarrollo**.
- Config por entorno: `INTEGRA_REPOS_DIR`, `INTEGRA_REPOS_HOSTS`,
  `MODELO_EMBEDDING` (por defecto `amazon.titan-embed-text-v2:0`),
  `INTEGRA_EMBED_DIM`, `INTEGRA_CHUNK_*`, `INTEGRA_MAX_CHUNKS`.

## Cómo probarlo
```powershell
python -m pytest tests/test_repos.py -q -o addopts=
# con el servicio arriba (webhook_ec2.py):
# GET  /api/repos
# POST /api/repos/clone   {"url": "owner/repo", "indexar": true}
# POST /api/repos/index   {"repo": "owner/repo", "max_trozos": 500}
```

## Riesgos y limitaciones
- El `/index` con Bedrock real requiere credenciales AWS (no disponibles en el
  entorno local); sin ellas opera en MOCK.
- No se versiona `/repos/` (correcto por licencias/tamaño), por lo que un repo
  clonado localmente no viaja en el PR.

## Criterios de aceptación
- [ ] `tests/test_repos.py` pasa.
- [ ] URL fuera del allowlist / con path traversal ⇒ rechazada.
- [ ] `POST /clone` con token inválido ⇒ `401`.
- [ ] `/index` produce ítems con la metadata de trazabilidad exigida.

## Evidencia
- `python -m pytest -q` en la rama **Ivan**: **107 passed** (verificado 2026-10-15).
- Contrato de endpoints en `src/repos/endpoints.py`.
