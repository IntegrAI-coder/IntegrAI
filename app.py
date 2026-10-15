"""IntegraAI · Dashboard — Fundación Integra (desafío E-1).

Panel amistoso para educadoras y direcciones:
  1) Registrar una observación (simula lo que llega por WhatsApp) y ver la decisión.
  2) Trayectoria de un niño/a + alertas.
  3) Panorama del aula/jardín (detección temprana de rezagos).
  4) Marco (ruta de niveles + manifestaciones).

Incluye un selector de MOTOR DE DECISIÓN para comparar en vivo el híbrido vs el
modelo typesafe Laya (diferencial de "innovación técnica").
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from src import config, marco
from src.agente import AgenteIntegra
from src.clasificador import Clasificador
from src.plataforma import Plataforma
from src.procesadores import Entrada
from src.whatsapp import CanalConsola, MensajeEntrante

st.set_page_config(page_title="IntegraAI · Fundación Integra", page_icon="🧒", layout="wide")

DATOS = config.datos_dir()
FECHA_REF = "2026-10-13"
MOTORES = {"ensemble": "🏆 Ensemble (híbrido ⊕ Laya) — 94% exacto",
           "hibrido": "Híbrido (matcher + etario) — rápido",
           "laya": "Laya typesafe (calibrado, on-prem)"}


@st.cache_resource
def get_plataforma() -> Plataforma:
    p = Plataforma()
    if p.resumen()["ninos"] == 0 and DATOS.exists():
        p.cargar_dataset(DATOS)
    return p


@st.cache_resource(show_spinner="Cargando motor de decisión…")
def get_agente(backend: str) -> AgenteIntegra:
    cl = Clasificador(backend=backend)
    return AgenteIntegra(canal=CanalConsola(), plataforma=get_plataforma(), clasificador=cl)


pl = get_plataforma()
r = pl.resumen()

st.title("🧒 IntegraAI")
st.caption("De la observación a la acción · 4 h/semana en escritorio → 0 h · Brecha documental de educación parvularia")

with st.sidebar:
    st.header("⚙️ Motor de decisión")
    motor = st.radio("Modelo que decide", list(MOTORES), format_func=lambda x: MOTORES[x])
    st.caption("El matcher propone la evidencia; el decision model decide el nivel. "
               "Laya entrega probabilidades **calibradas** on-prem.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Jardines", r["jardines"])
c2.metric("Niños/as", r["ninos"])
c3.metric("Observaciones", r["observaciones"])
c4.metric("Vínculos de evidencia", r["observacion_manifestaciones"])

tab_reg, tab_nino, tab_aula, tab_marco = st.tabs(
    ["📲 Registrar observación", "🧒 Trayectoria de un niño/a", "🏫 Panorama de aula", "📚 Marco"])

# ----------------------------------------------------------------------------
with tab_reg:
    st.subheader("Registrar una observación (llega por WhatsApp)")
    jardines = pl.jardines()
    jn = st.selectbox("Jardín", [j["id_jardin"] for j in jardines],
                      format_func=lambda x: f"{x} · {next(j['nombre_fantasia'] for j in jardines if j['id_jardin']==x)}")
    ninos = pl.ninos_de(id_jardin=jn)
    sala = st.selectbox("Sala", sorted({n["sala_grupo"] for n in ninos}))
    nino = st.selectbox("Niño/a", [n["id_nino"] for n in ninos if n["sala_grupo"] == sala])
    formato = st.selectbox("Formato del registro", ["texto", "audio", "imagen", "video"])
    nota = st.text_area("Nota de la educadora (o descripción de lo observado)",
                        "Hoy la observé: se sacó y guardó sus zapatos solo, armó una torre de cuatro bloques "
                        "y contó hasta cinco. Compartió los materiales por turnos.")
    archivo = st.file_uploader("Adjunto (opcional): audio, imagen o video",
                               type=["wav","mp3","ogg","m4a","jpg","jpeg","png","mp4"])
    if st.button("🚀 Procesar observación", type="primary"):
        adj: list[Entrada] = []
        if archivo is not None:
            tmp = Path(tempfile.mktemp(suffix=Path(archivo.name).suffix))
            tmp.write_bytes(archivo.getvalue())
            adj.append(Entrada(tipo=formato, ref=str(tmp), pie=nota))
        agente = get_agente(motor)
        msg = MensajeEntrante(de="+56 9 0000 0000", texto="" if adj else nota, adjuntos=adj,
                              ts=FECHA_REF, id_nino=nino, formato=formato)
        res = agente.procesar_mensaje(msg)
        cl = res["clasificacion"]
        st.success(f"Observación procesada y guardada ✔️ · motor: **{cl.get('backend')}**")
        cc1, cc2, cc3 = st.columns(3)
        cc1.metric("Nivel estimado", f"{cl['nivel']} · {cl['nombre_nivel']}" if cl['nivel'] else "sin evidencia")
        cc2.metric("Confianza", f"{int(cl['confianza']*100)}%")
        cc3.metric("¿Evidencia suficiente?", "Sí" if cl['evidencia_suficiente'] else "No")
        if cl.get("alerta_rezago"):
            st.warning("⚠️ Alerta de rezago: nivel por debajo de la banda etaria esperada.")
        st.markdown(f"**Dominios con evidencia:** {', '.join(marco.nombre_dominio(d) for d in cl['dominios']) or '—'}")
        if cl.get("probabilidades"):
            dfp = pd.DataFrame({"nivel": list(cl["probabilidades"].keys()),
                                "probabilidad": list(cl["probabilidades"].values())}).sort_values("nivel")
            st.markdown("**Distribución calibrada sobre los niveles (decision model):**")
            st.bar_chart(dfp, x="nivel", y="probabilidad", height=220)
        with st.expander("Manifestaciones detectadas (evidencia del matcher)"):
            st.dataframe(pd.DataFrame(cl["manifestaciones"]), use_container_width=True, hide_index=True)
        st.markdown("**Respuesta enviada por WhatsApp:**")
        st.info(res["respuesta"])

# ----------------------------------------------------------------------------
with tab_nino:
    st.subheader("Trayectoria de aprendizaje")
    todos = pl.ninos_de()
    nj = st.selectbox("Jardín  ", sorted({n["id_jardin"] for n in todos}), key="tj")
    ns = sorted({n["sala_grupo"] for n in todos if n["id_jardin"] == nj})
    nsala = st.selectbox("Sala  ", ns, key="ts")
    ids = [n["id_nino"] for n in todos if n["id_jardin"] == nj and n["sala_grupo"] == nsala]
    nino2 = st.selectbox("Niño/a  ", ids, key="tn")
    t = pl.trayectoria(nino2, FECHA_REF)
    m1, m2, m3 = st.columns(3)
    m1.metric("Nivel actual", f"{t.get('nivel_actual')} · {marco.nombre_nivel(t['nivel_actual'])}" if t.get("nivel_actual") else "—")
    m2.metric("Tendencia", t.get("tendencia", "—"))
    m3.metric("Observaciones", t.get("n_observaciones", 0))
    for a in t.get("alertas", []):
        st.warning("⚠️ " + a)
    if t.get("puntos"):
        df = pd.DataFrame(t["puntos"])
        st.line_chart(df, x="fecha", y="nivel", height=260)
        st.dataframe(df, use_container_width=True, hide_index=True)

# ----------------------------------------------------------------------------
with tab_aula:
    st.subheader("Panorama de aula — detección temprana")
    ja = st.selectbox("Jardín   ", sorted({j["id_jardin"] for j in pl.jardines()}), key="aj")
    nja = pl.ninos_de(id_jardin=ja)
    sala_a = st.selectbox("Sala   ", sorted({n["sala_grupo"] for n in nja}), key="as")
    solo_alertas = st.checkbox("Mostrar solo casos con alerta")
    pan = pl.panorama(id_jardin=ja, sala_grupo=sala_a, fecha_ref=FECHA_REF, solo_alertas=solo_alertas)
    t1, t2, t3 = st.columns(3)
    t1.metric("Niños/as", len(pan))
    t2.metric("Con alerta", sum(1 for f in pan if f["alertas"]))
    t3.metric("Tendencia subiendo", sum(1 for f in pan if f["tendencia"] == "subiendo"))
    dfp = pd.DataFrame([{**f, "alertas": " | ".join(f["alertas"])} for f in pan])
    st.dataframe(dfp, use_container_width=True, hide_index=True)

# ----------------------------------------------------------------------------
with tab_marco:
    st.subheader("Ruta de niveles (9) y dominios (5)")
    st.dataframe(pd.DataFrame(marco.ruta_niveles()), use_container_width=True, hide_index=True)
    st.subheader(f"Manifestaciones observables ({len(marco.manifestaciones())})")
    dfm = pd.DataFrame(marco.manifestaciones())
    niv = st.multiselect("Filtrar por nivel", sorted(dfm["nivel"].unique()), default=[6])
    st.dataframe(dfm[dfm["nivel"].isin(niv)] if niv else dfm, use_container_width=True, hide_index=True)
