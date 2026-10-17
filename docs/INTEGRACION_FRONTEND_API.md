# 🔌 Integración Frontend ↔ Backend — IntegrAI

El dashboard React (`frontend/`) puede leer los datos **vivos de la base** en vez del
dataset sintético estático. Lo hace vía un endpoint de **solo lectura** del backend.

## Contrato

### `GET /api/datos`
Devuelve el dataset completo, con **las mismas columnas que los CSV** que el frontend
ya parseaba (así la lógica de dominio no cambia). Leído de la BD (`plataforma.db`),
por lo que **incluye `JAR-EQUIPO` y las observaciones que llegan por WhatsApp**.

```jsonc
{
  "ruta_niveles": [ {"nivel":1,"nombre_nivel":"...","edad_min_meses":0,"edad_max_meses":2,"dominios":"...","descripcion":"..."}, ... ],
  "manifestaciones": [ {"id_manifestacion":"MAN-L01-CO-01","nivel":1,"dominio":"cognitivo","texto_observable":"..."}, ... ],
  "jardines":  [ {"id_jardin":"JAR-EQUIPO","nombre_fantasia":"Jardín Equipo — Demo","comuna":"Providencia","region":"Metropolitana"}, ... ],
  "ninos":     [ {"id_nino":"NINO-1C-01","fecha_nacimiento":"2022-05-15","id_jardin":"JAR-EQUIPO","sala_grupo":"Sala Girasol","fecha_ingreso":"2026-03-01"}, ... ],
  "observaciones": [ {"id_observacion":"OBS-9...","id_nino":"...","fecha_observacion":"2026-10-15","formato_captura":"texto","nivel_estimado":7}, ... ],
  "observacion_manifestaciones": [ {"id_observacion":"...","id_manifestacion":"..."}, ... ]
}
```

- 🔒 **Privacidad:** NUNCA expone `nombre_pila`/`apellidos`, la nota ni RUT. Solo códigos y niveles.
- 🔓 **Sin token** (a diferencia de `/procesar`): es de solo lectura y el dashboard es público.
  CORS configurable con `INTEGRA_CORS_ORIGINS` (por defecto `*`, solo `GET`).

### `GET /api/resumen`
Conteos rápidos (cabecera/estado): `{ok, jardines, ninos, observaciones, ...}`.

## Cómo se activa en el frontend

`frontend/src/data/cargar.ts` decide la fuente según `VITE_API_BASE`:

| `VITE_API_BASE` | Fuente |
|---|---|
| **sin definir** | CSV estáticos (`data/*.csv`) — GitHub Pages |
| **`""`** (vacío) | Mismo origen → **datos vivos** (CloudFront enruta `/api/*` al backend) |
| **URL absoluta** | Backend directo (ej. `https://<tu-backend>`) — requiere CORS |

Si la API no responde, **cae automáticamente a los CSV** (el dashboard nunca se rompe).

## Deploy (CloudFront)

`tools/desplegar_frontend.py configurar` agrega el comportamiento `/api/*` → API `:8000`
(mismo origen que `/procesar`, `/clasificar`, `/health`). Luego `subir` con:

```bash
cd frontend && VITE_API_BASE="" npm run build -- --base=/   # (o definir en .env)
```

## Fuera de alcance de esta integración (next)

- **Reconciliar la lógica de nivel/alerta:** hoy el front calcula el nivel vigente desde
  la observación más reciente y la alerta por banda etaria (`brecha ≤ -2`); el backend ya
  usa `evaluaciones` consolidadas + alerta **rubric-aware** (`nivel ≤ REZAGO_UMBRAL`).
- **Vista de la cola "por verificar"** (HITL): consumir `GET /pendientes?from=<número>`.

---
*Shiva · IntegrAI (AWS Breaking Barriers Chile 2026).*
