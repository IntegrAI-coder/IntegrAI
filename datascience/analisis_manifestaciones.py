#!/usr/bin/env python3
"""Data Science · estadística de las manifestaciones categorizadas.

Enlaza el backend del proyecto (`src.config` + `src.plataforma`, el mismo SQLite
que usa `app.py` y el dashboard) y analiza **el catálogo de manifestaciones**
(nivel × dominio) frente a su uso real en las observaciones. Profundiza el
gráfico "Evidencias por nivel y dominio" del dashboard con gráficos
**comparativos** (observado vs. esperado) e **interpretados** (cada uno con
lectura en 4 tiempos: Qué veo / Qué significa / Por qué importa / Qué hago).

Uso:
    python datascience/analisis_manifestaciones.py            # genera el HTML
    python datascience/analisis_manifestaciones.py --abrir    # y lo abre
    python datascience/analisis_manifestaciones.py --csv      # ignora el SQLite
    python datascience/analisis_manifestaciones.py --datos ruta/a/csvs

Sin red: usa Plotly por CDN para el HTML.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import webbrowser
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

SALIDA = RAIZ / "datascience" / "analisis_manifestaciones.html"

COLOR = {"acento": "#2563eb", "acento2": "#0f766e", "alerta": "#b45309",
         "base": "#93c5fd", "ok": "#059669", "gris": "#cbd5e1"}
PALETA_DOM = ["#2563eb", "#0f766e", "#d97706", "#7c3aed", "#db2777"]


# --------------------------------------------------------------------------- #
# Backend
# --------------------------------------------------------------------------- #

def _dir_datos() -> Path:
    """Ubica los CSV con el backend (src.config.datos_dir) y cae a data/."""
    try:
        from src import config as _cfg

        d = Path(_cfg.datos_dir())
        if (d / "manifestaciones.csv").exists():
            return d
    except Exception:  # noqa: BLE001
        pass
    return RAIZ / "data"


def _leer(nombre: str, d: Path) -> pd.DataFrame:
    return pd.read_csv(d / nombre, encoding="utf-8-sig")


def _cargar_backend(d: Path) -> dict[str, pd.DataFrame] | None:
    """Lee observaciones y vínculos desde el SQLite de src.plataforma, si existe."""
    try:
        from src import config as _cfg
        from src.plataforma import Plataforma
    except Exception:  # noqa: BLE001
        return None
    if not Path(_cfg.DB_PATH).exists():
        return None
    try:
        pl = Plataforma()
        if pl.resumen()["ninos"] == 0 and (d / "observaciones.csv").exists():
            pl.cargar_dataset(d)
        if pl.resumen()["ninos"] == 0:
            return None
        con = pl.con
        return {
            "observaciones": pd.read_sql_query(
                "SELECT id_observacion,id_nino,fecha_observacion,formato_captura,nivel_estimado "
                "FROM observaciones", con),
            "observacion_manifestaciones": pd.read_sql_query(
                "SELECT id_observacion,id_manifestacion FROM observacion_manifestaciones", con),
            "ninos": pd.read_sql_query("SELECT id_nino,id_jardin,sala_grupo FROM ninos", con),
            "jardines": pd.read_sql_query("SELECT id_jardin,nombre_fantasia,region FROM jardines", con),
        }
    except Exception:  # noqa: BLE001
        return None


def cargar(datos_dir: Path | None = None, usar_backend: bool = True) -> tuple[dict[str, pd.DataFrame], str]:
    d = Path(datos_dir) if datos_dir else _dir_datos()
    base = _cargar_backend(d) if usar_backend else None
    origen = "backend SQLite (src.plataforma)"
    if base is None:
        origen = f"CSV ({d})"
        base = {
            "observaciones": _leer("observaciones.csv", d),
            "observacion_manifestaciones": _leer("observacion_manifestaciones.csv", d),
            "ninos": _leer("ninos.csv", d),
            "jardines": _leer("jardines.csv", d),
        }
    base["manifestaciones"] = _leer("manifestaciones.csv", d)
    base["ninos"]["id_jardin"] = base["ninos"]["id_jardin"].astype(str)
    base["jardines"]["id_jardin"] = base["jardines"]["id_jardin"].astype(str)
    return base, origen


DOMINIOS = [
    ("motor_grueso", "Motor grueso"),
    ("motor_fino", "Motor fino"),
    ("lenguaje_comunicacion", "Lenguaje"),
    ("socioemocional", "Socioemocional"),
    ("cognitivo", "Cognitivo"),
]
NOMBRE_DOM = dict(DOMINIOS)


# --------------------------------------------------------------------------- #
# Analítica
# --------------------------------------------------------------------------- #

def construir(datos: dict[str, pd.DataFrame]) -> dict:
    catalogo = datos["manifestaciones"].copy()
    catalogo["nivel"] = catalogo["nivel"].astype(int)
    om = datos["observacion_manifestaciones"].merge(
        catalogo[["id_manifestacion", "nivel", "dominio", "texto_observable"]],
        on="id_manifestacion", how="left",
    ).merge(
        datos["observaciones"][["id_observacion", "id_nino", "fecha_observacion",
                                "formato_captura", "nivel_estimado"]],
        on="id_observacion", how="left",
    )
    om = om.merge(datos["ninos"][["id_nino", "id_jardin"]], on="id_nino", how="left")
    om = om.merge(datos["jardines"][["id_jardin", "nombre_fantasia"]], on="id_jardin", how="left")
    om["mes"] = pd.to_datetime(om["fecha_observacion"], errors="coerce").dt.to_period("M").astype(str)

    uso = om.groupby("id_manifestacion").size()
    catalogo["usos"] = catalogo["id_manifestacion"].map(uso).fillna(0).astype(int)

    return {"catalogo": catalogo, "om": om, "uso": uso}


def metricas(an: dict) -> dict:
    catalogo, om = an["catalogo"], an["om"]
    total = len(om)
    n_cat = len(catalogo)
    usadas = int((catalogo["usos"] > 0).sum())
    nunca = catalogo[catalogo["usos"] == 0]

    dist_dom = om.groupby("dominio").size().reindex([d for d, _ in DOMINIOS]).fillna(0)
    dist_niv = om.groupby("nivel").size().reindex(range(1, 10)).fillna(0)

    # entropía normalizada sobre los usos del catálogo (0 = todo en una; 1 = uniforme)
    cuentas = catalogo["usos"].to_numpy()
    p = cuentas[cuentas > 0] / cuentas.sum()
    entropia = float(-(p * np.log(p)).sum() / math.log(n_cat)) if len(p) else 0.0

    dominios_por_jardin = (om.groupby("nombre_fantasia")["dominio"].nunique()
                           if "nombre_fantasia" in om else pd.Series(dtype=int))
    return {
        "total_links": total,
        "n_obs": int(om["id_observacion"].nunique()),
        "catalogo": n_cat,
        "usadas": usadas,
        "nunca": int(len(nunca)),
        "cobertura_pct": round(100 * usadas / n_cat) if n_cat else 0,
        "dist_dom": dist_dom,
        "dist_niv": dist_niv,
        "entropia": entropia,
        "dom_por_jardin": dominios_por_jardin,
        "meses": sorted(om["mes"].dropna().unique()),
        "n_jardines": int(dominios_por_jardin.shape[0]),
    }


# --------------------------------------------------------------------------- #
# Gráficos
# --------------------------------------------------------------------------- #

def _base_layout(**extra) -> dict:
    lay = dict(
        margin=dict(t=18, r=18, b=60, l=64),
        font=dict(family="system-ui, Segoe UI, Roboto, Arial", size=12, color="#334155"),
        paper_bgcolor="#fff", plot_bgcolor="#fff",
        xaxis=dict(gridcolor="#eef2f7"), yaxis=dict(gridcolor="#eef2f7"),
        showlegend=True, legend=dict(orientation="h", y=-0.22),
    )
    lay.update(extra)
    return lay


def fig_catalogo_heat(an: dict) -> go.Figure:
    cat = an["catalogo"]
    z = (cat.groupby(["nivel", "dominio"]).size().unstack(fill_value=0)
         .reindex(index=range(1, 10), columns=[d for d, _ in DOMINIOS]).fillna(0))
    fig = go.Figure(go.Heatmap(
        z=z.values, x=[NOMBRE_DOM[d] for d in z.columns], y=[f"Nivel {i}" for i in z.index],
        colorscale="Blues", showscale=False,
        text=[[f"{int(v)}" if v else "" for v in fila] for fila in z.values],
        texttemplate="%{text}", hovertemplate="Nivel %{y} · %{x}: %{z} manifestaciones<extra></extra>",
    ))
    fig.update_layout(**_base_layout(showlegend=False, yaxis=dict(autorange="reversed")))
    return fig


def fig_cobertura(m: dict) -> go.Figure:
    fig = go.Figure(go.Pie(
        values=[m["usadas"], m["nunca"]], labels=["Observadas ≥ 1 vez", "Nunca observadas"],
        hole=0.55, marker=dict(colors=[COLOR["ok"], COLOR["gris"]]), textinfo="label+value",
    ))
    fig.update_layout(**_base_layout(showlegend=False, margin=dict(t=10, r=10, b=10, l=10)))
    return fig


def fig_dominio_comparado(m: dict) -> go.Figure:
    obs = m["dist_dom"]
    esp = np.full(len(obs), m["total_links"] / len(obs))
    fig = go.Figure([
        go.Bar(name="Observado", x=[NOMBRE_DOM[d] for d in obs.index], y=obs.values, marker_color=COLOR["acento"]),
        go.Bar(name="Esperado (uniforme)", x=[NOMBRE_DOM[d] for d in obs.index], y=esp, marker_color=COLOR["base"]),
    ])
    fig.update_layout(**_base_layout(barmode="group", yaxis_title="vínculos observación↔manifestación"))
    return fig


def fig_nivel_comparado(m: dict) -> go.Figure:
    obs = m["dist_niv"]
    esp = np.full(len(obs), m["total_links"] / len(obs))
    fig = go.Figure([
        go.Bar(name="Observado", x=[f"{i}" for i in obs.index], y=obs.values, marker_color=COLOR["acento2"]),
        go.Bar(name="Esperado (uniforme)", x=[f"{i}" for i in obs.index], y=esp, marker_color=COLOR["base"]),
    ])
    fig.update_layout(**_base_layout(barmode="group", xaxis_title="nivel", yaxis_title="vínculos"))
    return fig


def fig_lorenz(an: dict) -> go.Figure:
    cuentas = np.sort(an["catalogo"]["usos"].to_numpy())
    acum = np.concatenate([[0], np.cumsum(cuentas) / cuentas.sum()])
    x = np.linspace(0, 1, len(acum))
    fig = go.Figure([
        go.Scatter(x=x, y=acum, mode="lines", name="Uso acumulado", line=dict(color=COLOR["acento"], width=3)),
        go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="Uniforme", line=dict(color=COLOR["gris"], dash="dash")),
    ])
    fig.update_layout(**_base_layout(xaxis_title="manifestaciones (ordenadas por uso)", yaxis_title="% acumulado"))
    return fig


def fig_top(an: dict) -> go.Figure:
    top = an["catalogo"].sort_values("usos", ascending=False).head(12).iloc[::-1]
    etq = [f"{t[:52]}…" if len(t) > 52 else t for t in top["texto_observable"].fillna("")]
    fig = go.Figure(go.Bar(
        x=top["usos"], y=etq, orientation="h", marker_color=COLOR["acento"],
        customdata=top[["nivel", "dominio"]].values,
        hovertemplate="Nivel %{customdata[0]} · %{customdata[1]}<br>%{y}<br>%{x} usos<extra></extra>",
    ))
    fig.update_layout(**_base_layout(showlegend=False, margin=dict(t=10, r=20, b=40, l=430)))
    return fig


def fig_formato_dominio(an: dict) -> go.Figure:
    om = an["om"]
    piv = (om.pivot_table(index="formato_captura", columns="dominio", aggfunc="size", fill_value=0)
           .reindex(columns=[d for d, _ in DOMINIOS]).fillna(0))
    propor = piv.div(piv.sum(axis=1).replace(0, np.nan), axis=0) * 100
    fig = go.Figure(go.Heatmap(
        z=propor.values, x=[NOMBRE_DOM[d] for d in propor.columns], y=list(propor.index),
        colorscale="Teal", showscale=True, colorbar=dict(title="%"),
        text=[[f"{v:.0f}%" if not np.isnan(v) else "" for v in fila] for fila in propor.values],
        texttemplate="%{text}", hovertemplate="%{y} · %{x}: %{z:.1f}%<extra></extra>",
    ))
    fig.update_layout(**_base_layout(showlegend=False))
    return fig


def fig_tiempo_dominio(an: dict) -> go.Figure:
    om = an["om"]
    piv = (om.pivot_table(index="mes", columns="dominio", aggfunc="size", fill_value=0)
           .reindex(columns=[d for d, _ in DOMINIOS]).fillna(0))
    fig = go.Figure()
    for i, (d, nombre) in enumerate(DOMINIOS):
        if d in piv:
            fig.add_trace(go.Scatter(x=list(piv.index), y=piv[d], name=nombre, mode="lines",
                                     stackgroup="uno", line=dict(color=PALETA_DOM[i])))
    fig.update_layout(**_base_layout(xaxis_title="mes", yaxis_title="vínculos", hovermode="x unified"))
    return fig


def fig_jardin_dominio(an: dict) -> go.Figure:
    om = an["om"].dropna(subset=["nombre_fantasia"])
    piv = (om.pivot_table(index="nombre_fantasia", columns="dominio", aggfunc="size", fill_value=0)
           .reindex(columns=[d for d, _ in DOMINIOS]).fillna(0))
    piv = piv.loc[piv.sum(axis=1).sort_values().index]
    fig = go.Figure(go.Heatmap(
        z=[(piv.loc[j] > 0).astype(int).values for j in piv.index],
        x=[NOMBRE_DOM[d] for d in piv.columns], y=list(piv.index),
        colorscale=[[0, "#f1f5f9"], [1, COLOR["acento2"]]], showscale=False,
        hovertemplate="%{y} · %{x}: %{z}<extra></extra>",
    ))
    fig.update_layout(**_base_layout(showlegend=False, margin=dict(t=10, r=20, b=50, l=170)))
    return fig


def fig_manif_por_nivel_dominio(an: dict) -> go.Figure:
    """Uso (no catálogo): dónde se concentran los vínculos observados."""
    om = an["om"]
    z = (om.groupby(["nivel", "dominio"]).size().unstack(fill_value=0)
         .reindex(index=range(1, 10), columns=[d for d, _ in DOMINIOS]).fillna(0))
    fig = go.Figure(go.Heatmap(
        z=z.values, x=[NOMBRE_DOM[d] for d in z.columns], y=[f"Nivel {i}" for i in z.index],
        colorscale="Viridis", colorbar=dict(title="vínculos"),
        hovertemplate="Nivel %{y} · %{x}: %{z} vínculos<extra></extra>",
    ))
    fig.update_layout(**_base_layout(showlegend=False, yaxis=dict(autorange="reversed")))
    return fig


# --------------------------------------------------------------------------- #
# Interpretación (4 tiempos) por gráfico
# --------------------------------------------------------------------------- #

def _interp(veo: str, significa: str, importa: str, hago: str) -> str:
    return (f'<div class="interp">'
            f'<p><b>Qué veo.</b> {veo}</p>'
            f'<p><b>Qué significa.</b> {significa}</p>'
            f'<p><b>Por qué importa.</b> {importa}</p>'
            f'<p><b>Qué hago con esto.</b> {hago}</p>'
            f'</div>')


def construir_tarjetas(an: dict, m: dict) -> list[dict]:
    om, cat = an["om"], an["catalogo"]
    total = m["total_links"]
    top_dom = m["dist_dom"].idxmax()
    top_dom_pct = round(100 * m["dist_dom"].max() / total) if total else 0
    bajo_dom = m["dist_dom"].idxmin()
    bajo_dom_pct = round(100 * m["dist_dom"].min() / total) if total else 0
    top_niv = int(m["dist_niv"].idxmax())
    top_niv_pct = round(100 * m["dist_niv"].max() / total) if total else 0
    fmt = om.groupby("formato_captura").size().sort_values(ascending=False)
    fmt_top = fmt.index[0] if len(fmt) else "—"
    fmt_top_pct = round(100 * fmt.iloc[0] / total) if len(fmt) and total else 0
    dmin = m["dom_por_jardin"].min() if m["n_jardines"] else 0
    jardines_bajos = int((m["dom_por_jardin"] < 5).sum()) if m["n_jardines"] else 0
    meses = m["meses"]
    nunca_ej = cat[cat["usos"] == 0].head(3)["texto_observable"].tolist()
    nunca_txt = "; ".join(t[:60] + ("…" if len(t) > 60 else "") for t in nunca_ej) or "—"

    return [
        {
            "panel": "catalogo", "id": "catalogo-heat", "titulo": "El catálogo: 9 niveles × 5 dominios",
            "proposito": "Todo el catálogo de manifestaciones observables (2 por celda).",
            "fig": fig_catalogo_heat(an),
            "interp": _interp(
                f"El catálogo completo tiene <b>{m['catalogo']}</b> manifestaciones repartidas de forma pareja: 9 niveles × 5 dominios × 2.",
                "Es una grilla balanceada: ninguna combinación nivel-dominio queda sin evidencia disponible.",
                "Si la observación se concentrara siempre en las mismas celdas, el resto del desarrollo del niño/a quedaría invisible.",
                "Úsalo como mapa de referencia: cada celda es una ventana de observación posible."),
        },
        {
            "panel": "catalogo", "id": "cobertura", "titulo": "Cobertura del catálogo",
            "proposito": "Cuántas manifestaciones se observaron al menos una vez.",
            "fig": fig_cobertura(m),
            "interp": _interp(
                f"Se usaron <b>{m['usadas']}</b> de {m['catalogo']} manifestaciones (<b>{m['cobertura_pct']}%</b>); "
                f"<b>{m['nunca']}</b> nunca aparecen en las observaciones.",
                "Hay evidencia del catálogo que el sistema nunca 've' con los datos actuales.",
                "Las manifestaciones nunca observadas son puntos ciegos: sesgos del registro, no necesariamente del desarrollo infantil.",
                f"Revisa las que faltan (p. ej. <i>{nunca_txt}</i>) y fomenta observaciones que las capturen."),
        },
        {
            "panel": "uso", "id": "nivel-dom-uso", "titulo": "Uso observado por nivel y dominio",
            "proposito": "Profundiza el heatmap 'Evidencias por nivel y dominio' del dashboard.",
            "fig": fig_manif_por_nivel_dominio(an),
            "interp": _interp(
                f"El nivel <b>{top_niv}</b> concentra <b>{top_niv_pct}%</b> de los vínculos; "
                f"el dominio <b>{NOMBRE_DOM[top_dom]}</b> lidera con <b>{top_dom_pct}%</b>.",
                "La observación real no es uniforme: se apoya en ciertos niveles y dominios.",
                "Un sesgo fuerte distorsiona las trayectorias y las alertas de rezago calculadas sobre estos datos.",
                "Equilibra: si el grupo está subobservado en un dominio, prográmalo en la próxima ronda."),
        },
        {
            "panel": "uso", "id": "dom-comparado", "titulo": "Dominios: observado vs. esperado",
            "proposito": "Compara el reparto real con un reparto uniforme.",
            "fig": fig_dominio_comparado(m),
            "interp": _interp(
                f"<b>{NOMBRE_DOM[top_dom]}</b> está sobre lo uniforme ({top_dom_pct}%); "
                f"<b>{NOMBRE_DOM[bajo_dom]}</b> está bajo ({bajo_dom_pct}%).",
                "La diferencia contra la línea 'esperado' mide el sesgo de registro por dominio.",
                "El desarrollo es integral: sobrevalorar un dominio deja otros sin evidencia para el plan.",
                f"Refuerza observaciones de <b>{NOMBRE_DOM[bajo_dom]}</b> en las próximas semanas."),
        },
        {
            "panel": "uso", "id": "nivel-comparado", "titulo": "Niveles: observado vs. esperado",
            "proposito": "Compara el reparto por nivel con un reparto uniforme.",
            "fig": fig_nivel_comparado(m),
            "interp": _interp(
                f"El nivel {top_niv} acumula {top_niv_pct}% de los vínculos del catálogo.",
                "Los niveles se observan de forma desigual a lo largo del tiempo.",
                "Las alertas de rezago comparan contra el nivel esperado por edad; un sesgo por nivel puede crear falsos positivos o puntos ciegos.",
                "Verifica que existan observaciones recientes en el tramo de edad de cada niño/a."),
        },
        {
            "panel": "uso", "id": "lorenz", "titulo": "Concentración del uso (Lorenz)",
            "proposito": f"Entropía normalizada: {m['entropia']:.2f} (1 = uso uniforme).",
            "fig": fig_lorenz(an),
            "interp": _interp(
                f"La curva se aleja de la diagonal (entropía normalizada <b>{m['entropia']:.2f}</b>).",
                "Unas pocas manifestaciones cargan la mayoría de las observaciones.",
                "Alta concentración = catálogo subutilizado; la riqueza de la rúbrica se pierde.",
                "Promueve usar manifestaciones 'de cola' para ampliar el registro."),
        },
        {
            "panel": "uso", "id": "top", "titulo": "Manifestaciones más usadas",
            "proposito": "Las 12 manifestaciones con más vínculos.",
            "fig": fig_top(an),
            "interp": _interp(
                "Unas pocas manifestaciones explican la mayor parte de las observaciones.",
                "Suelen ser las más fáciles de observar en la rutina de sala.",
                "Si se repiten siempre las mismas, el registro describe al niño/a de forma parcial.",
                "Varía el foco: observa conductas menos evidentes para completar el perfil."),
        },
        {
            "panel": "formato", "id": "formato-dom", "titulo": "Formato de captura × dominio",
            "proposito": "% del formato según el dominio que captura.",
            "fig": fig_formato_dominio(an),
            "interp": _interp(
                f"El formato <b>{fmt_top}</b> concentra <b>{fmt_top_pct}%</b> de los vínculos.",
                "Cada formato (texto, voz, imagen, video) tiende a capturar ciertos dominios mejor que otros.",
                "Un formato dominante puede introducir sesgo: lo que no se puede capturar con él queda fuera.",
                "Diversifica el formato según el dominio que quieras evidenciar (p. ej. video para motor)."),
        },
        {
            "panel": "formato", "id": "tiempo-dom", "titulo": "Evolución mensual por dominio",
            "proposito": "Cómo cambia la mezcla de dominios en el tiempo.",
            "fig": fig_tiempo_dominio(an),
            "interp": _interp(
                f"El periodo va de <b>{meses[0]}</b> a <b>{meses[-1]}</b> ({len(meses)} meses).",
                "La composición de dominios cambia mes a mes.",
                "Las caídas de un dominio señalan semanas con registro incompleto.",
                "Correlaciona los valles con la carga de trabajo para ajustar el acompañamiento."),
        },
        {
            "panel": "territorio", "id": "jardin-dom", "titulo": "Cobertura de dominios por jardín",
            "proposito": "Qué dominios tienen evidencia en cada jardín.",
            "fig": fig_jardin_dominio(an),
            "interp": _interp(
                f"El jardín con menor cobertura registra <b>{int(dmin)}</b> de 5 dominios; "
                f"<b>{jardines_bajos}</b> de {m['n_jardines']} jardines tienen cobertura incompleta.",
                "La cobertura de dominios no es la misma en todos los jardines.",
                "Los jardines con menos dominios tienen menos base para su plan de acompañamiento.",
                "Prioriza apoyo y formación donde la cobertura es más baja."),
        },
    ]


# --------------------------------------------------------------------------- #
# HTML
# --------------------------------------------------------------------------- #

CSS = """
:root{--fondo:#f5f7fa;--sup:#fff;--borde:#e4e8ee;--texto:#1e293b;--tenue:#64748b;
--acento:#2563eb;--acento2:#0f766e;--alerta:#b45309;--radio:14px}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;color:var(--texto);background:var(--fondo)}
main{max-width:1360px;margin:0 auto;padding:1.4rem 1.5rem 3rem}
header h1{font-size:1.4rem;margin:0 0 .2rem}
header p{margin:.15rem 0;color:var(--tenue);font-size:.9rem}
.badge{display:inline-block;background:#e8f0fe;color:var(--acento);border-radius:999px;padding:.1rem .6rem;font-size:.74rem;font-weight:700;margin-left:.4rem}
.badge.src{background:#f0fdfa;color:var(--acento2)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.9rem;margin:1rem 0}
.kpi{background:var(--sup);border:1px solid var(--borde);border-radius:var(--radio);padding:.85rem 1rem;box-shadow:0 1px 2px rgba(16,24,40,.05)}
.kpi .n{font-size:1.5rem;font-weight:800;color:var(--acento)}
.kpi .l{font-size:.75rem;color:var(--tenue);margin-top:.15rem}
nav.tabs{display:flex;gap:.25rem;flex-wrap:wrap;border-bottom:2px solid var(--borde);margin:1.1rem 0 0;position:sticky;top:0;background:var(--fondo);z-index:6;padding-top:.35rem}
nav.tabs button{background:transparent;color:var(--tenue);padding:.55rem .95rem;font-size:.88rem;border:0;border-bottom:3px solid transparent;cursor:pointer;border-radius:9px 9px 0 0;font-weight:600}
nav.tabs button.activo{color:var(--acento);border-bottom-color:var(--acento)}
.panel{display:none;padding-top:1rem}
.panel.activo{display:block}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:1rem}
.card{background:var(--sup);border:1px solid var(--borde);border-radius:var(--radio);padding:1rem 1.1rem;box-shadow:0 1px 3px rgba(16,24,40,.06)}
.card.wide{grid-column:1/-1}
.card h3{margin:0 0 .2rem;font-size:.98rem}
.card .purpose{margin:0 0 .5rem;color:var(--tenue);font-size:.82rem}
.interp{margin-top:.7rem;border-top:1px dashed var(--borde);padding-top:.6rem;font-size:.86rem;color:#475569;line-height:1.5}
.interp p{margin:.3rem 0}
.interp b{color:var(--texto)}
footer{color:var(--tenue);font-size:.8rem;text-align:center;padding:2rem 1rem}
@media(max-width:760px){.grid{grid-template-columns:1fr}}
"""

PLANTILLA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Data Science · Manifestaciones categorizadas · IntegrAI</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>__CSS__</style></head>
<body><main>
<header>
  <h1>Data Science · manifestaciones categorizadas<span class="badge">datos sintéticos</span></h1>
  <p>Análisis comparativo e interpretado del catálogo (nivel × dominio) frente a su uso en las observaciones.</p>
  <p>Fuente: <span class="badge src">__ORIGEN__</span> · generado el __GENERADO__.</p>
</header>
<div class="kpis" id="kpis"></div>
<nav class="tabs" id="tabs">
  <button data-tab="catalogo" class="activo">Catálogo</button>
  <button data-tab="uso">Uso y sesgo</button>
  <button data-tab="formato">Formato y tiempo</button>
  <button data-tab="territorio">Territorio</button>
</nav>
<section class="panel activo" data-panel="catalogo">__PANEL_CATALOGO__</section>
<section class="panel" data-panel="uso">__PANEL_USO__</section>
<section class="panel" data-panel="formato">__PANEL_FORMATO__</section>
<section class="panel" data-panel="territorio">__PANEL_TERRITORIO__</section>
<footer>Subcarpeta <code>datascience/</code> · profundiza el gráfico "Evidencias por nivel y dominio" del dashboard ·
lee del backend (src.plataforma) o de los CSV · datos 100 % sintéticos.</footer>
</main>
<script>
const KPIS = __KPIS__;
document.getElementById("kpis").innerHTML = KPIS.map(k =>
  `<div class="kpi"><div class="n">${k.n}</div><div class="l">${k.l}</div></div>`).join("");
document.querySelectorAll("nav.tabs button").forEach(b => b.addEventListener("click", () => {
  document.querySelectorAll("nav.tabs button").forEach(x => x.classList.remove("activo"));
  b.classList.add("activo");
  document.querySelectorAll(".panel").forEach(p => p.classList.toggle("activo", p.dataset.panel === b.dataset.tab));
  requestAnimationFrame(() => document.querySelectorAll(".js-plotly-plot").forEach(el => Plotly.Plots.resize(el)));
}));
</script>
</body></html>
"""


def _fig_html(fig: go.Figure) -> str:
    return pio.to_html(fig, include_plotlyjs=False, full_html=False,
                       config={"displaylogo": False, "responsive": True,
                               "modeBarButtonsToRemove": ["lasso2d", "select2d"]})


def render(tarjetas: list[dict], m: dict, origen: str, salida: Path) -> Path:
    paneles = {"catalogo": [], "uso": [], "formato": [], "territorio": []}
    for t in tarjetas:
        ancho = " wide" if t["id"] in ("catalogo-heat", "nivel-dom-uso", "jardin-dom", "tiempo-dom") else ""
        paneles[t["panel"]].append(
            f'<section class="card{ancho}"><h3>{t["titulo"]}</h3>'
            f'<p class="purpose">{t["proposito"]}</p>'
            f'{_fig_html(t["fig"])}{t["interp"]}</section>'
        )
    kpis = [
        {"n": f"{m['total_links']:,}".replace(",", "."), "l": "Vínculos observación↔manifestación"},
        {"n": f"{m['n_obs']:,}".replace(",", "."), "l": "Observaciones con evidencia"},
        {"n": f"{m['cobertura_pct']}%", "l": "Cobertura del catálogo"},
        {"n": m["usadas"], "l": f"Usadas de {m['catalogo']}"},
        {"n": m["nunca"], "l": "Nunca observadas"},
        {"n": f"{m['entropia']:.2f}", "l": "Entropía (uso uniforme=1)"},
    ]
    html = (PLANTILLA
            .replace("__CSS__", CSS)
            .replace("__ORIGEN__", origen)
            .replace("__GENERADO__", f"{date.today():%d-%m-%Y}")
            .replace("__KPIS__", json.dumps(kpis, ensure_ascii=False))
            .replace("__PANEL_CATALOGO__", '<div class="grid">' + "".join(paneles["catalogo"]) + "</div>")
            .replace("__PANEL_USO__", '<div class="grid">' + "".join(paneles["uso"]) + "</div>")
            .replace("__PANEL_FORMATO__", '<div class="grid">' + "".join(paneles["formato"]) + "</div>")
            .replace("__PANEL_TERRITORIO__", '<div class="grid">' + "".join(paneles["territorio"]) + "</div>"))
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(html, encoding="utf-8")
    return salida


def main() -> int:
    parser = argparse.ArgumentParser(description="Análisis de manifestaciones categorizadas (data science).")
    parser.add_argument("--salida", default=str(SALIDA))
    parser.add_argument("--datos", default=None, help="Carpeta de datos (por defecto: backend/dataset)")
    parser.add_argument("--csv", action="store_true", help="Forzar lectura desde CSV (ignorar SQLite)")
    parser.add_argument("--abrir", action="store_true")
    args = parser.parse_args()

    datos, origen = cargar(datos_dir=args.datos, usar_backend=not args.csv)
    analisis = construir(datos)
    m = metricas(analisis)
    tarjetas = construir_tarjetas(analisis, m)
    destino = render(tarjetas, m, origen, Path(args.salida))

    print(f"Fuente: {origen}")
    print(f"Catálogo: {m['catalogo']} · observadas: {m['usadas']} ({m['cobertura_pct']}%) · nunca: {m['nunca']}")
    print(f"Vínculos: {m['total_links']} · entropía normalizada: {m['entropia']:.2f}")
    print(f"Generado: {destino}  ({destino.stat().st_size // 1024} KB)")
    if args.abrir:
        webbrowser.open(destino.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
