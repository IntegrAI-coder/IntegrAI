"""IntegrAI — servicio de decisión (EC2). Expone /procesar y /clasificar.

/procesar  : texto + remitente -> RESOLVER (determinista) -> CLASIFICAR (ensemble) -> registrar
             Si NO identifica al niño -> NO registra y pide rectificar el nombre.
/clasificar: texto -> nivel + margen (sin registrar)

El enrutamiento nombre->id es DETERMINISTA: ante duda, NO adivina (pide corrección).
La verificación humana en la plataforma queda SOLO para el nivel de la rúbrica.
"""
from __future__ import annotations

import base64
import os
import tempfile
from datetime import date, datetime

import hmac
import os as _os
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.plataforma import Plataforma
from src.resolver import Resolver, DIMINUTIVOS, normalizar
from src.marco import STOPWORDS
from src import config
from src.clasificador import Clasificador
from src import marco

JARDIN_DEMO = os.getenv("INTEGRA_JARDIN", "JAR-0001")
EDUCADORA_DEMO = os.getenv("INTEGRA_EDUCADORA", "EDU-DEMO")
BACKEND = os.getenv("BACKEND_DECISION", "ensemble")
SALA_DEMO = os.getenv("INTEGRA_SALA", "")          # "" = todo el jardín demo
# 1 = número no registrado usa el jardín demo; 0 = rechaza
FALLBACK_DEMO = os.getenv("INTEGRA_FALLBACK_DEMO", "1") == "1"

API_TOKEN = os.getenv("INTEGRA_API_TOKEN", "")
# U2: la nota pasa a conductas observables antes del ensemble (docs/EVAL_ENSEMBLE.md §5: 47 % -> 72 %)
U2_CONDUCTAS = os.getenv("U2_CONDUCTAS", "1") == "1"
MAX_MEDIA = int(os.getenv("MAX_MEDIA_BYTES", str(16 * 1024 * 1024)))
_docs = os.getenv("INTEGRA_DOCS", "0") == "1"   # Swagger solo en desarrollo

app = FastAPI(title="IntegrAI · decisión (EC2)", docs_url="/docs" if _docs else None,
              redoc_url=None, openapi_url="/openapi.json" if _docs else None)
if not API_TOKEN:
    print("[seguridad] INTEGRA_API_TOKEN no definido: la API queda ABIERTA (solo para desarrollo)", flush=True)


def requiere_token(x_api_key: str = Header(default="")) -> None:
    """Token compartido con el webhook. Ley 21.459: la barrera de acceso debe existir."""
    if API_TOKEN and not hmac.compare_digest(x_api_key, API_TOKEN):
        raise HTTPException(status_code=401, detail="no autorizado")


def _a_conductas(texto: str) -> str:
    """Texto para el clasificador: conductas U2 (sin nombres) o el texto original si U2 falla."""
    if not U2_CONDUCTAS or config.usar_mock():
        return texto
    try:
        from types import SimpleNamespace
        from src.multimodal import normalizar_entradas
        try:   # MM v2: guiado por el marco activo (rúbrica de Integra); sin rúbrica instalada -> v1
            from src.marcos import marco_activo
            guia = marco_activo()
        except Exception:  # noqa: BLE001
            guia = None
        obs = normalizar_entradas([SimpleNamespace(tipo="texto", ref="", pie=texto, texto_extraido="")], guia=guia)
        return obs.texto_para_matcher() or texto
    except Exception as e:  # noqa: BLE001
        print(f"[u2] fallo, uso texto original: {type(e).__name__}", flush=True)
        return texto
plat = Plataforma()
try:
    clas = Clasificador(backend=BACKEND)
except Exception as e:  # noqa: BLE001
    print(f"[clas] backend {BACKEND} falló ({e!r}); uso hibrido", flush=True)
    clas = Clasificador(backend="hibrido")

_roster_cache: dict[str, object] = {}


def _filas(jardin: str) -> list[dict]:
    if jardin not in _roster_cache:
        _roster_cache[jardin] = plat.roster_sala(id_jardin=jardin)
    return _roster_cache[jardin]  # type: ignore[return-value]


def _ctx_remitente(from_: str) -> list[dict]:
    """Rutea el número entrante -> educadora(s) + sala(s). Sin número registrado:
    usa la sala demo (FALLBACK_DEMO=1) o rechaza (0)."""
    ctx = plat.ruta_de_whatsapp(from_ or "")
    if ctx:
        return ctx
    if FALLBACK_DEMO:
        return [{"id_educadora": EDUCADORA_DEMO, "id_jardin": JARDIN_DEMO,
                 "sala_grupo": SALA_DEMO, "_fallback": True}]
    return []


def _filas_ctx(ctx: list[dict]) -> list[dict]:
    """Roster unión de las salas del remitente (dedup por id_nino+nombre)."""
    key = tuple(sorted((c.get("id_jardin"), c.get("sala_grupo")) for c in ctx))
    if key not in _roster_cache:
        vistos: dict = {}
        for c in ctx:
            for f in plat.roster_sala(id_jardin=c.get("id_jardin"), sala_grupo=c.get("sala_grupo")):
                vistos[(f["id_nino"], f.get("nombre_pila"))] = f
        _roster_cache[key] = list(vistos.values())
    return _roster_cache[key]


def _nivel_ponderado(id_nino: str) -> tuple:
    """Nivel PONDERADO del niño/a (media de sus notas por confianza) + nº de notas."""
    obs = [o for o in plat.observaciones_de(id_nino) if o.get("nivel")]
    if not obs:
        return None, 0
    num = sum(o["nivel"] * max(float(o.get("confianza") or 0.5), 0.01) for o in obs)
    den = sum(max(float(o.get("confianza") or 0.5), 0.01) for o in obs)
    return round(num / den), len(obs)


def _es_apellido_del_roster(cand: str, aps: list[str]) -> bool:
    """¿`cand` coincide con (o es prefijo de) algún apellido del roster?"""
    return any(a == cand or a.startswith(cand + " ") or cand.startswith(a) for a in aps if a)


def extraer_mencion(texto: str, filas: list[dict]) -> str:
    """Heurística determinista: busca un nombre de pila del roster (o diminutivo)
    y toma el nombre + los tokens siguientes SOLO si son **apellidos del roster**
    (evita confundir el verbo de la frase con un apellido). Máx. 2 apellidos."""
    toks = normalizar(texto).split()
    pila = {normalizar(f["nombre_pila"]) for f in filas if f.get("nombre_pila")}
    aps = [normalizar(f.get("apellidos") or "") for f in filas if f.get("apellidos")]
    aliases = set(DIMINUTIVOS.keys())
    for i, t in enumerate(toks):
        if t in pila or t in aliases:
            nombre = [t]
            j = i + 1
            while j < len(toks) and len(nombre) < 3 and _es_apellido_del_roster(toks[j], aps):
                nombre.append(toks[j]); j += 1
            return " ".join(nombre)
    return toks[0] if toks else ""


def _ack_no_identificado(palabra: str, res) -> str:
    if res.estado == "ambiguo":
        return (f"⚠️ Hay más de un niño/a con el nombre «{palabra}». "
                f"Reenvía indicando nombre y apellido (ej. «{palabra} + apellido»).")
    extra = f" (no está en la sala)" if palabra else ""
    return (f"⚠️ No pude identificar al niño/a «{palabra}»{extra}. "
            f"Por favor reenvía la observación indicando nombre y apellido.")


class Msg(BaseModel):
    from_: str = Field(alias="from")
    texto: str
    fecha: str | None = None

    class Config:
        populate_by_name = True


def _procesar(from_: str, texto: str, fecha: str | None = None) -> dict:
    fecha = fecha or date.today().isoformat()
    ctx = _ctx_remitente(from_)
    if not ctx:
        return {"ok": False, "estado": "remitente_desconocido",
                "ack": "⚠️ No reconozco este número. Pídele a tu coordinadora que lo registre."}
    filas = _filas_ctx(ctx)
    educadora = ctx[0]["id_educadora"]
    res = Resolver(filas).resolver(extraer_mencion(texto, filas))

    if res.estado != "resuelto":
        return {"ok": False, "estado": res.estado, "metodo": res.metodo,
                "candidatos": res.candidatos,
                "ack": _ack_no_identificado(extraer_mencion(texto, filas), res)}

    nin = plat.nino(res.id_nino) or {}
    edad = marco.edad_meses(nin["fecha_nacimiento"], fecha) if nin.get("fecha_nacimiento") else None
    # el clasificador recibe conductas sin nombres; se guarda eso, no la nota cruda con el nombre
    texto_clas = _a_conductas(texto)
    cl = clas.clasificar(texto_clas, edad)
    estado = "por_verificar" if cl.requiere_revision else "auto"

    oid = plat.registrar_observacion(
        id_nino=res.id_nino, id_educadora=educadora, fecha=fecha, formato="texto",
        nivel=cl.nivel, nota=texto_clas, dominios=cl.dominios,
        manifestaciones=[m.manifestacion["id"] for m in cl.matches],
        confianza=cl.confianza, origen="whatsapp", metodo_resolucion=res.metodo,
        margen=cl.margen, estado=estado)

    # El ACK SIEMPRE responde el nivel PONDERADO del niño/a (media de sus notas), no el de la nota suelta.
    pond, n_notas = _nivel_ponderado(res.id_nino)
    ack = f"registrado ✓ — {nin.get('nombre_pila','')} · nivel {pond} (promedio de {n_notas} notas)"
    if estado != "auto":
        ack += " · la nota quedó por confirmar en la plataforma"
    return {"ok": True, "id_nino": res.id_nino, "nivel_nota": cl.nivel, "nivel_ponderado": pond,
            "n_notas": n_notas, "margen": cl.margen, "metodo": res.metodo,
            "estado_resolucion": estado, "observacion_id": oid, "ack": ack}


@app.get("/health")
def health() -> dict:
    # sin jardín ni tamaño del roster (no exponer datos operativos sin autenticación)
    return {"ok": True}


@app.post("/procesar", dependencies=[Depends(requiere_token)])
def procesar(m: Msg) -> dict:
    return _procesar(m.from_, m.texto, m.fecha)

# GET /procesar eliminado: ponía la nota (datos de menores) en la URL y en los logs de acceso.


@app.post("/clasificar", dependencies=[Depends(requiere_token)])
def clasificar(texto: str, edad_meses: int | None = None) -> dict:
    cl = clas.clasificar(texto, edad_meses)
    return cl.to_dict()


# --------------------------------------------------------------------------- #
# COLA "POR VERIFICAR" (human-in-the-loop) — la tía consulta y resuelve SU cola
# --------------------------------------------------------------------------- #
@app.get("/pendientes", dependencies=[Depends(requiere_token)])
def pendientes(from_: str = Query("", alias="from")) -> dict:
    """La cola de verificación de la tía identificada por su número de WhatsApp."""
    ctx = _ctx_remitente(from_ or "")
    educadora = ctx[0]["id_educadora"] if ctx else None
    items = plat.pendientes_de(educadora) if educadora else []
    return {"ok": True, "educadora": educadora, "n": len(items),
            "pendientes": [{k: it.get(k) for k in
                            ("id_pendiente", "id_nino_propuesto", "nivel_propuesto", "margen",
                             "motivo", "evidencia", "estado", "creado_en")} for it in items]}


class ResolverPendiente(BaseModel):
    id_pendiente: str
    accion: str                      # aprobado | editado | rechazado
    nivel: int | None = None         # requerido si accion=editado
    resuelto_por: str | None = None


@app.post("/pendiente/resolver", dependencies=[Depends(requiere_token)])
def pendiente_resolver(m: ResolverPendiente) -> dict:
    """Aprueba / edita / rechaza un pendiente. Aprobar o editar ESCRIBE en `evaluaciones`."""
    row = plat.con.execute("SELECT * FROM evaluaciones_pendientes WHERE id_pendiente=?",
                           (m.id_pendiente,)).fetchone()
    if not row:
        return {"ok": False, "error": "pendiente no encontrado"}
    d = dict(row)
    nivel = m.nivel if m.nivel is not None else d.get("nivel_propuesto")
    plat.resolver_pendiente(m.id_pendiente, m.accion, m.resuelto_por or d.get("id_educadora") or "tia",
                            id_nino=d.get("id_nino_propuesto"), nivel=nivel,
                            dominio=d.get("dominio"), cuando=datetime.now().isoformat(timespec="seconds"))
    return {"ok": True, "id_pendiente": m.id_pendiente, "accion": m.accion,
            "id_nino": d.get("id_nino_propuesto"), "nivel": nivel}


# --------------------------------------------------------------------------- #
def extraer_texto_ocr(img_bytes: bytes, fmt: str = "jpeg") -> str:
    """OCR literal con Amazon Nova Pro (Bedrock). Devuelve el texto transcrito."""
    try:
        import boto3
        cliente = boto3.client("bedrock-runtime", region_name=config.AWS_REGION)
        prompt = ("Transcribe EXACTAMENTE y literalmente TODO el texto manuscrito o impreso de esta imagen "
                  "(suele ser un post-it con el nombre de un niño/a y una observación). "
                  "Devuelve SOLO el texto transcrito, sin comentarios, sin comillas.")
        r = cliente.converse(
            modelId="us.amazon.nova-pro-v1:0",
            messages=[{"role": "user", "content": [
                {"image": {"format": fmt, "source": {"bytes": img_bytes}}},
                {"text": prompt}]}],
            inferenceConfig={"maxTokens": 250, "temperature": 0.0})
        return r["output"]["message"]["content"][0]["text"].strip()
    except Exception as e:  # noqa: BLE001
        print(f"[ocr] error: {type(e).__name__}", flush=True)
        return ""


def _con_temporal(data: bytes, ext: str, fn):
    """Escribe el medio en un temporal dentro de DIR_MEDIOS, aplica `fn(ruta)` y SIEMPRE lo borra."""
    from src.seguridad.archivos import directorio_medios
    d = directorio_medios(); d.mkdir(parents=True, exist_ok=True)
    f = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False, dir=d) as t:
            t.write(data)
            f = t.name
        return fn(f)
    finally:
        if f and _os.path.exists(f):
            _os.unlink(f)


def transcribir_audio_bytes(data: bytes, ext: str = ".ogg") -> str:
    try:
        from src.procesadores import transcribir_audio
        return _con_temporal(data, ext, transcribir_audio)
    except Exception as e:  # noqa: BLE001
        print(f"[whisper] error: {type(e).__name__}", flush=True)
        return ""


def analizar_video_bytes(data: bytes, ext: str = ".mp4") -> tuple[str, str]:
    """(texto_visual, texto_audio). Lo VISUAL es lo principal: Pegasus 1.2 describe postura, apoyo,
    control de cabeza, desplazamiento y manos con timestamps (fallback Nova 2 Lite).
    El audio (Whisper) complementa: comentarios de la tía o el nombre del niño/a."""
    def _ambos(ruta: str) -> tuple[str, str]:
        from src.multimodal.video import describir_video
        from src.procesadores import extraer_audio_video   # ruta ffmpeg que ya funciona en la EC2
        visual = describir_video(ruta).texto
        try:
            audio = extraer_audio_video(ruta)
        except Exception:  # noqa: BLE001
            audio = ""
        return visual, audio
    try:
        return _con_temporal(data, ext, _ambos)
    except Exception as e:  # noqa: BLE001
        print(f"[video] error: {type(e).__name__}", flush=True)
        return "", ""


class MediaMsg(BaseModel):
    from_: str = Field(alias="from")
    tipo: str            # image | audio | video
    media_b64: str
    caption: str = ""

    class Config:
        populate_by_name = True


@app.post("/procesar_media", dependencies=[Depends(requiere_token)])
def procesar_media(m: MediaMsg) -> dict:
    from src.seguridad.archivos import tipo_real
    invalido = {"ok": False, "estado": "media_invalida",
                "ack": "\u26a0\ufe0f No pude procesar el archivo recibido (tipo o tama\u00f1o no permitido)."}
    if len(m.media_b64) > MAX_MEDIA * 4 // 3 + 16:   # tope antes de decodificar
        return invalido
    try:
        data = base64.b64decode(m.media_b64, validate=True)
    except Exception:
        return invalido
    real = tipo_real(data[:16])   # magic bytes, no la extensi\u00f3n ni lo que diga el cliente
    if m.tipo == "audio" and real in ("ogg", "mp3", "wav", "mp4"):
        texto = transcribir_audio_bytes(data, ext=f".{real}")
    elif m.tipo == "video" and real in ("mp4", "webm"):
        visual, audio = analizar_video_bytes(data, ext=f".{real}")
        if not visual:
            return {"ok": False, "estado": "video_sin_analisis",
                    "ack": "⚠️ No pude analizar el video. Reenvíalo (máx. 16 MB) o describe lo que viste."}
        # el pie de foto y el audio van primero: ahí suele venir el nombre que usa el resolver;
        # la descripción visual (sin nombres) es la observación que se clasifica
        texto = " ".join(p for p in ((m.caption or ""), audio, visual) if p).strip()
        print(f"[media] video -> visual {len(visual)} chars, audio {len(audio)} chars", flush=True)
        return _procesar(m.from_, texto)
    elif m.tipo == "image" and real in ("jpeg", "png", "webp", "gif"):
        texto = extraer_texto_ocr(data, fmt=real)
    else:
        return invalido
    texto = (texto + " " + (m.caption or "")).strip()
    if not texto:
        return {"ok": False, "estado": "sin_texto",
                "ack": "\u26a0\ufe0f Recib\u00ed el archivo pero no pude leer un nombre en \u00e9l. "
                       "Reenv\u00eda con el nombre del ni\u00f1o/a (o escr\u00edbelo en el mensaje)."}
    print(f"[media] {m.tipo} -> {len(texto)} chars", flush=True)   # sin el texto (PII)
    return _procesar(m.from_, texto)


# --- estático (index.html del demo) como fallback en "/" ---
if _os.path.isdir("/opt/integra/www"):
    app.mount("/", StaticFiles(directory="/opt/integra/www", html=True), name="www")
