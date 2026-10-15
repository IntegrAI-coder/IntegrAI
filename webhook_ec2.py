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
from datetime import date

import os as _os
from fastapi import FastAPI
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

app = FastAPI(title="IntegrAI · decisión (EC2)")
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


def extraer_mencion(texto: str, filas: list[dict]) -> str:
    """Heurística determinista: busca un nombre de pila del roster (o diminutivo)
    y toma el nombre + el siguiente token SOLO si es plausible apellido (no stopword)."""
    toks = normalizar(texto).split()
    pila = {normalizar(f["nombre_pila"]) for f in filas if f.get("nombre_pila")}
    aliases = set(DIMINUTIVOS.keys())
    for i, t in enumerate(toks):
        if t in pila or t in aliases:
            nombre = [t]
            if i + 1 < len(toks) and toks[i + 1] not in STOPWORDS and len(toks[i + 1]) > 1:
                nombre.append(toks[i + 1])   # apellido plausible
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
    filas = _filas(JARDIN_DEMO)
    res = Resolver(filas).resolver(extraer_mencion(texto, filas))

    if res.estado != "resuelto":
        return {"ok": False, "estado": res.estado, "metodo": res.metodo,
                "candidatos": res.candidatos,
                "ack": _ack_no_identificado(extraer_mencion(texto, filas), res)}

    nin = plat.nino(res.id_nino) or {}
    edad = marco.edad_meses(nin["fecha_nacimiento"], fecha) if nin.get("fecha_nacimiento") else None
    cl = clas.clasificar(texto, edad)
    estado = "por_verificar" if cl.requiere_revision else "auto"

    oid = plat.registrar_observacion(
        id_nino=res.id_nino, id_educadora=EDUCADORA_DEMO, fecha=fecha, formato="texto",
        nivel=cl.nivel, nota=texto, dominios=cl.dominios,
        manifestaciones=[m.manifestacion["id"] for m in cl.matches],
        confianza=cl.confianza, origen="whatsapp", metodo_resolucion=res.metodo,
        margen=cl.margen, estado=estado)

    if estado == "auto":
        ack = f"registrado ✓ — {nin.get('nombre_pila','')} · nivel {cl.nivel}"
    else:
        ack = f"registrado ✓ — {nin.get('nombre_pila','')} · nivel {cl.nivel} (quedó por confirmar en la plataforma)"
    return {"ok": True, "id_nino": res.id_nino, "nivel": cl.nivel, "margen": cl.margen,
            "metodo": res.metodo, "estado_resolucion": estado, "observacion_id": oid,
            "ack": ack}


@app.get("/health")
def health() -> dict:
    return {"ok": True, "jardin": JARDIN_DEMO, "backend": clas.decisor.nombre,
            "ninos_roster": len(_filas(JARDIN_DEMO))}


@app.post("/procesar")
def procesar(m: Msg) -> dict:
    return _procesar(m.from_, m.texto, m.fecha)


@app.get("/procesar")
def procesar_get(from_: str, texto: str, fecha: str | None = None) -> dict:
    return _procesar(from_, texto, fecha)


@app.post("/clasificar")
def clasificar(texto: str, edad_meses: int | None = None) -> dict:
    cl = clas.clasificar(texto, edad_meses)
    return cl.to_dict()


# --------------------------------------------------------------------------- #
def extraer_texto_ocr(img_bytes: bytes) -> str:
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
                {"image": {"format": "jpeg", "source": {"bytes": img_bytes}}},
                {"text": prompt}]}],
            inferenceConfig={"maxTokens": 250, "temperature": 0.0})
        return r["output"]["message"]["content"][0]["text"].strip()
    except Exception as e:  # noqa: BLE001
        print(f"[ocr] error: {e!r}", flush=True)
        return ""


def transcribir_audio_bytes(data: bytes, ext: str = ".ogg") -> str:
    try:
        from src.procesadores import transcribir_audio
        f = tempfile.mktemp(suffix=ext)
        open(f, "wb").write(data)
        return transcribir_audio(f)
    except Exception as e:  # noqa: BLE001
        print(f"[whisper] error: {e!r}", flush=True)
        return ""


class MediaMsg(BaseModel):
    from_: str = Field(alias="from")
    tipo: str            # image | audio | video
    media_b64: str
    caption: str = ""

    class Config:
        populate_by_name = True


@app.post("/procesar_media")
def procesar_media(m: MediaMsg) -> dict:
    try:
        data = base64.b64decode(m.media_b64)
    except Exception:
        return {"ok": False, "estado": "media_invalida",
                "ack": "\u26a0\ufe0f No pude decodificar el archivo recibido."}
    if m.tipo == "audio":
        texto = transcribir_audio_bytes(data)
    else:  # image / video -> OCR
        texto = extraer_texto_ocr(data)
    texto = (texto + " " + (m.caption or "")).strip()
    if not texto:
        return {"ok": False, "estado": "sin_texto",
                "ack": "\u26a0\ufe0f Recib\u00ed el archivo pero no pude leer un nombre en \u00e9l. "
                       "Reenv\u00eda con el nombre del ni\u00f1o/a (o escr\u00edbelo en el mensaje)."}
    print(f"[ocr-texto] {texto!r}", flush=True)
    return _procesar(m.from_, texto)


# --- estático (index.html del demo) como fallback en "/" ---
if _os.path.isdir("/opt/integra/www"):
    app.mount("/", StaticFiles(directory="/opt/integra/www", html=True), name="www")
