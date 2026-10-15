#!/usr/bin/env python3
"""Dashboard de datos con relato visual para parvularias.

Convierte las observaciones en un tablero que no solo muestra el dato, sino que
explica, en cuatro tiempos (**Qué veo / Qué significa / Por qué importa / Qué
hago**), por qué cada dato le sirve a quien acompaña a los niños y niñas. Incluye
un relato guiado ("la historia de un dato") y se adapta al rol (parvularia,
directora, equipo).

Hace ingeniería de features (edad, tramo, nivel vigente/esperado, brecha, alerta
de rezago, cobertura de dominios, etc.) y arma un HTML autocontenido con KPIs y
gráficos interactivos.

Uso:
    python dashboard/visualizar_datos.py                 # dashboard interactivo (por defecto)
    python dashboard/visualizar_datos.py --abrir         # además lo abre en el navegador
    python dashboard/visualizar_datos.py --estatico      # reporte estático con plotly.express
    python dashboard/visualizar_datos.py --salida ruta.html

Sin red: no requiere credenciales; usa Plotly por CDN para el HTML.
"""
from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))


def _dir_datos() -> Path:
    """Ubica los CSV usando el backend (src.config.datos_dir) y cae a data/."""
    try:
        from src import config as _cfg

        d = Path(_cfg.datos_dir())
        if (d / "observaciones.csv").exists():
            return d
    except Exception:
        pass
    return RAIZ / "data"


DATA = _dir_datos()

# Umbral de alerta de rezago (igual que el frontend: brecha <= -2 niveles).
UMBRAL_ALERTA = -2

COLOR_NIVEL = px.colors.sequential.Blues[6]
COLOR_ALERTA = "#b45309"

# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------


def _leer(nombre: str, dir_datos: Path | None = None) -> pd.DataFrame:
    return pd.read_csv((dir_datos or DATA) / nombre, encoding="utf-8-sig")


def _cargar_backend(dir_datos: Path) -> dict[str, pd.DataFrame] | None:
    """Lee del backend (SQLite de src.plataforma) si la base ya existe.

    Devuelve None para que cargar() caiga a los CSV cuando no hay backend.
    """
    try:
        from src import config as _cfg
        from src.plataforma import Plataforma
    except Exception:
        return None
    if not Path(_cfg.DB_PATH).exists():
        return None
    try:
        pl = Plataforma()
        if pl.resumen()["ninos"] == 0 and (dir_datos / "observaciones.csv").exists():
            pl.cargar_dataset(dir_datos)
        if pl.resumen()["ninos"] == 0:
            return None
        con = pl.con
        return {
            "jardines": pd.read_sql_query("SELECT * FROM jardines", con),
            "educadoras": pd.read_sql_query("SELECT * FROM educadoras", con),
            "ninos": pd.read_sql_query(
                "SELECT id_nino,fecha_nacimiento,sexo_registrado,id_jardin,sala_grupo,fecha_ingreso FROM ninos", con
            ),
            "observaciones": pd.read_sql_query(
                "SELECT id_observacion,id_nino,id_educadora,fecha_observacion,formato_captura,"
                "nivel_estimado,nota_breve FROM observaciones",
                con,
            ),
            "observacion_manifestaciones": pd.read_sql_query(
                "SELECT id_observacion,id_manifestacion FROM observacion_manifestaciones", con
            ),
        }
    except Exception:
        return None


def cargar(usar_backend: bool = True, datos_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    """Carga los datos del panel.

    Primero intenta el backend (SQLite de src.plataforma, usado por app.py); si
    no existe la base, cae a los CSV del dataset. `datos_dir` fuerza una carpeta.
    """
    d = Path(datos_dir) if datos_dir else DATA
    base = _cargar_backend(d) if usar_backend else None
    if base is None:
        base = {
            "jardines": _leer("jardines.csv", d),
            "educadoras": _leer("educadoras.csv", d),
            "ninos": _leer("ninos.csv", d),
            "observaciones": _leer("observaciones.csv", d),
            "observacion_manifestaciones": _leer("observacion_manifestaciones.csv", d),
        }
    base["manifestaciones"] = _leer("manifestaciones.csv", d)
    base["ruta_niveles"] = _leer("ruta_niveles.csv", d)
    for clave in ("ninos", "observaciones"):
        for col in ("fecha_nacimiento", "fecha_ingreso", "fecha_observacion"):
            if col in base[clave].columns:
                base[clave][col] = pd.to_datetime(base[clave][col], errors="coerce")
    return base


# ---------------------------------------------------------------------------
# Ingeniería de features
# ---------------------------------------------------------------------------


def edad_meses(nacimiento: pd.Timestamp, referencia: pd.Timestamp) -> float:
    """Meses completos (misma regla que el dashboard y el diccionario)."""
    if pd.isna(nacimiento) or pd.isna(referencia):
        return np.nan
    meses = (referencia.year - nacimiento.year) * 12 + (referencia.month - nacimiento.month)
    if referencia.day < nacimiento.day:
        meses -= 1
    return max(0, meses)


def _nivel_esperado(meses: float, ruta: pd.DataFrame) -> float:
    if pd.isna(meses):
        return np.nan
    orden = ruta.sort_values("nivel")
    for _, fila in orden.iterrows():
        if fila["edad_min_meses"] <= meses < fila["edad_max_meses"]:
            return fila["nivel"]
    ultimo = orden.iloc[-1]
    if meses >= ultimo["edad_max_meses"]:
        return ultimo["nivel"]
    return np.nan


def _tramo(meses: float) -> str:
    if pd.isna(meses):
        return "Sin dato"
    if meses < 24:
        return "Sala Cuna (0-23 m)"
    if meses < 48:
        return "Nivel Medio (24-47 m)"
    if meses < 72:
        return "Transición (48-71 m)"
    return "Fuera de rango (>=72 m)"


def construir_features(datos: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Un registro por niño/a con features derivadas para el análisis."""
    ninos = datos["ninos"].copy()
    obs = datos["observaciones"].copy()
    ruta = datos["ruta_niveles"]
    man = datos["manifestaciones"]
    om = datos["observacion_manifestaciones"]

    obs = obs.sort_values("fecha_observacion")
    ultima = obs.groupby("id_nino").tail(1).set_index("id_nino")
    obs["_mes"] = obs["fecha_observacion"].dt.to_period("M")
    n_obs = obs.groupby("id_nino").size().rename("n_observaciones")
    n_formatos = obs.groupby("id_nino")["formato_captura"].nunique().rename("formatos_distintos")
    primera = obs.groupby("id_nino")["fecha_observacion"].min().rename("primera_observacion")
    ultima_fecha = obs.groupby("id_nino")["fecha_observacion"].max().rename("ultima_observacion")
    es_video = obs.groupby("id_nino")["formato_captura"].apply(
        lambda s: bool((s == "video").any())
    ).rename("tiene_video")

    # dominios cubiertos por niño/a (vía observación -> manifestación -> dominio)
    om_man = om.merge(man[["id_manifestacion", "dominio"]], on="id_manifestacion", how="left")
    om_man = om_man.merge(obs[["id_observacion", "id_nino"]], on="id_observacion", how="left")
    dominios = (
        om_man.groupby("id_nino")["dominio"].nunique().rename("dominios_cubiertos")
    )

    df = ninos.merge(n_obs, on="id_nino", how="left")
    for serie in (n_formatos, primera, ultima_fecha, es_video, dominios):
        df = df.merge(serie, on="id_nino", how="left")

    df["nivel_vigente"] = ultima["nivel_estimado"].reindex(df["id_nino"]).to_numpy()
    df["fecha_ultima_obs"] = ultima["fecha_observacion"].reindex(df["id_nino"]).to_numpy()

    # edad a la última observación (o al día de hoy si no hay observación)
    referencia = df["fecha_ultima_obs"].fillna(pd.Timestamp(date.today()))
    df["edad_meses"] = [
        edad_meses(nac, ref) for nac, ref in zip(df["fecha_nacimiento"], referencia)
    ]
    df["nivel_esperado"] = [_nivel_esperado(m, ruta) for m in df["edad_meses"]]
    df["brecha"] = df["nivel_vigente"] - df["nivel_esperado"]
    df["alerta"] = df["brecha"] <= UMBRAL_ALERTA
    # Rezago relativo a la sala (definición del FAQ): compara cada niño/a con la
    # mediana de su propia sala, no con la curva por edad.
    df["mediana_sala"] = df.groupby(["id_jardin", "sala_grupo"])["nivel_vigente"].transform("median")
    df["brecha_sala"] = df["nivel_vigente"] - df["mediana_sala"]
    df["alerta_sala"] = df["brecha_sala"] <= UMBRAL_ALERTA
    df["tramo"] = df["edad_meses"].map(_tramo)
    df["n_observaciones"] = df["n_observaciones"].fillna(0).astype(int)
    df["formatos_distintos"] = df["formatos_distintos"].fillna(0).astype(int)
    df["dominios_cubiertos"] = df["dominios_cubiertos"].fillna(0).astype(int)
    df["tiene_video"] = df["tiene_video"].fillna(False)
    df["dias_desde_ingreso_a_obs"] = (
        (df["fecha_ultima_obs"] - df["fecha_ingreso"]).dt.days
    )
    return df


def features_jardin(feats: pd.DataFrame, jardines: pd.DataFrame) -> pd.DataFrame:
    agg = feats.groupby("id_jardin").agg(
        n_ninos=("id_nino", "size"),
        nivel_promedio=("nivel_vigente", "mean"),
        n_alertas=("alerta_sala", "sum"),
        obs_por_nino=("n_observaciones", "mean"),
    )
    agg["pct_alertas"] = 100 * agg["n_alertas"] / agg["n_ninos"]
    return agg.reset_index().merge(
        jardines[["id_jardin", "nombre_fantasia", "comuna", "region"]],
        on="id_jardin",
        how="left",
    )


# ---------------------------------------------------------------------------
# Calidad de datos
# ---------------------------------------------------------------------------


def resumen_calidad(datos: dict[str, pd.DataFrame]) -> pd.DataFrame:
    filas = []
    for nombre, df in datos.items():
        filas.append(
            {
                "tabla": nombre,
                "filas": len(df),
                "columnas": df.shape[1],
                "nulos": int(df.isna().sum().sum()),
                "duplicados_PK": int(df.duplicated().sum()),
            }
        )
    tabla = pd.DataFrame(filas)

    ninos, obs = datos["ninos"], datos["observaciones"]
    checks = [
        (
            "obs con id_nino inexistente",
            int((~obs["id_nino"].isin(ninos["id_nino"])).sum()),
        ),
        (
            "niños sin observaciones",
            int((~ninos["id_nino"].isin(obs["id_nino"])).sum()),
        ),
        (
            "niveles fuera de 1-9",
            int((~obs["nivel_estimado"].between(1, 9)).sum()),
        ),
        (
            "observaciones por niño (mín-máx)",
            f"{int(obs.groupby('id_nino').size().min())}-{int(obs.groupby('id_nino').size().max())}",
        ),
        (
            "fechas de observación (rango)",
            f"{obs['fecha_observacion'].min():%Y-%m-%d} a {obs['fecha_observacion'].max():%Y-%m-%d}",
        ),
    ]
    return tabla, checks


# ---------------------------------------------------------------------------
# Gráficos (Plotly Express)
# ---------------------------------------------------------------------------


def _vacio(px_fig, mensaje: str):
    px_fig.update_layout(
        annotations=[
            dict(text=mensaje, showarrow=False, xref="paper", yref="paper", x=0.5, y=0.5)
        ]
    )
    return px_fig


def construir_graficos(datos: dict[str, pd.DataFrame], feats: pd.DataFrame):
    """Devuelve una lista de secciones: (id, titulo, descripcion, figura)."""
    jardines = datos["jardines"]
    obs = datos["observaciones"]
    man = datos["manifestaciones"]
    om = datos["observacion_manifestaciones"]
    educadoras = datos["educadoras"]
    graficos = []

    # 1. Composición de las entidades
    entidades = pd.DataFrame(
        {
            "entidad": ["Jardines", "Salas", "Niños/as", "Educadoras", "Observaciones", "Manifestaciones"],
            "total": [
                jardines["id_jardin"].nunique(),
                feats[["id_jardin", "sala_grupo"]].drop_duplicates().shape[0],
                len(feats),
                len(educadoras),
                len(obs),
                len(man),
            ],
        }
    ).sort_values("total")
    fig = px.bar(
        entidades,
        x="total",
        y="entidad",
        orientation="h",
        text="total",
        title="Volumen de datos sintéticos",
        color="total",
        color_continuous_scale="Blues",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(coloraxis_showscale=False, yaxis_title="", xaxis_title="registros")
    graficos.append(("entidades", "Volumen de datos", "Cuántos registros de cada entidad trae el dataset sintético.", fig))

    # 2. Composición por sexo registrado
    fig = px.pie(
        feats,
        names="sexo_registrado",
        title="Composición por sexo registrado",
        hole=0.45,
    )
    fig.update_traces(textinfo="percent+label")
    graficos.append(("sexo", "Sexo registrado", "Distribución sintética por categoría de sexo registrado.", fig))

    # 3. Niños/as por tramo educativo
    orden_tramos = ["Sala Cuna (0-23 m)", "Nivel Medio (24-47 m)", "Transición (48-71 m)", "Fuera de rango (>=72 m)"]
    cont = feats["tramo"].value_counts().reindex(orden_tramos).fillna(0).reset_index()
    cont.columns = ["tramo", "ninos"]
    fig = px.bar(
        cont,
        x="tramo",
        y="ninos",
        text="ninos",
        title="Niños y niñas por tramo educativo",
        color="tramo",
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="niños/as")
    graficos.append(("tramo", "Tramos educativos", "Feature derivada del tramo según la edad (Sala Cuna / Nivel Medio / Transición).", fig))

    # 4. Nivel vigente por niño/a
    dist = (
        feats["nivel_vigente"].dropna().astype(int).value_counts().sort_index().reset_index()
    )
    dist.columns = ["nivel", "ninos"]
    fig = px.bar(
        dist,
        x="nivel",
        y="ninos",
        text="ninos",
        title="Nivel vigente por niño/a",
        color="ninos",
        color_continuous_scale="Blues",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        coloraxis_showscale=False,
        xaxis_title="nivel (1-9)",
        yaxis_title="niños/as",
        xaxis=dict(dtick=1),
    )
    graficos.append(("nivel", "Nivel vigente", "Última estimación de nivel por niño/a (la más reciente).", fig))

    # 5. Formato de captura
    fmt = obs["formato_captura"].value_counts().reset_index()
    fmt.columns = ["formato", "total"]
    fig = px.pie(
        fmt,
        names="formato",
        values="total",
        title="Observaciones por formato de captura",
        hole=0.45,
        color_discrete_sequence=px.colors.qualitative.Pastel,
    )
    fig.update_traces(textinfo="percent+label")
    graficos.append(("formato", "Formato de captura", "Cómo se registró cada observación (texto, audio, foto o video).", fig))

    # 6. Observaciones en el tiempo
    serie = obs.set_index("fecha_observacion").resample("MS").size().reset_index(name="total")
    fig = px.area(
        serie,
        x="fecha_observacion",
        y="total",
        title="Observaciones en el tiempo",
        markers=True,
    )
    fig.update_layout(xaxis_title="mes", yaxis_title="observaciones")
    fig.update_traces(line_color=COLOR_NIVEL)
    graficos.append(("tiempo", "Evolución temporal", "Cantidad de observaciones registradas por mes.", fig))

    # 7. Observaciones por niño/a (histograma de la feature n_observaciones)
    fig = px.histogram(
        feats,
        x="n_observaciones",
        nbins=10,
        title="¿Cuántas observaciones tiene cada niño/a?",
        color_discrete_sequence=[COLOR_NIVEL],
    )
    fig.update_layout(xaxis=dict(dtick=1), xaxis_title="observaciones por niño/a", yaxis_title="niños/as", showlegend=False)
    graficos.append(("obs_nino", "Cobertura por niño/a", "Distribución de la feature «número de observaciones por niño/a».", fig))

    # 8. Edad vs nivel vigente (scatter con features)
    sub = feats.dropna(subset=["edad_meses", "nivel_vigente"])
    if len(sub):
        fig = px.scatter(
            sub,
            x="edad_meses",
            y="nivel_vigente",
            color="tramo",
            size="n_observaciones",
            hover_data=["id_nino", "brecha", "brecha_sala", "alerta_sala"],
            title="Edad vs. nivel vigente",
            color_discrete_sequence=px.colors.qualitative.Set1,
        )
        fig.update_layout(
            xaxis_title="edad (meses)",
            yaxis_title="nivel vigente (1-9)",
            yaxis=dict(dtick=1),
            legend_title="tramo",
        )
        graficos.append(("edad_nivel", "Edad vs. nivel", "Relación entre la edad (feature) y el nivel observado; el punto crece con las observaciones.", fig))
    else:
        graficos.append(("edad_nivel", "Edad vs. nivel", "", _vacio(px.scatter(), "Sin datos")))

    # 9. Brecha observado vs esperado por edad
    brecha = feats.dropna(subset=["brecha"])
    fig = px.histogram(
        brecha,
        x="brecha",
        nbins=int(brecha["brecha"].max() - brecha["brecha"].min() + 1) if len(brecha) else 5,
        title="Brecha por edad: nivel vigente menos nivel esperado",
        color_discrete_sequence=[COLOR_NIVEL],
    )
    fig.update_layout(xaxis_title="brecha (niveles)", yaxis_title="niños/as", showlegend=False, xaxis=dict(dtick=1))
    if len(brecha):
        fig.add_vline(x=UMBRAL_ALERTA, line_dash="dash", line_color=COLOR_ALERTA,
                      annotation_text=f"umbral alerta ({UMBRAL_ALERTA})", annotation_position="top")
        n_edad = int((brecha["brecha"] <= UMBRAL_ALERTA).sum())
        fig.add_annotation(
            text=f"Con la referencia por edad, este dataset sintético no genera alertas (máximo rezago observado: "
                 f"{brecha['brecha'].min():.0f}). Útil para validar la lógica, no para verla actuar.",
            showarrow=False, xref="paper", yref="paper", x=0.5, y=1.18, font=dict(size=11, color=COLOR_ALERTA),
        )
    graficos.append(("brecha", "Brecha vs. lo esperado (edad)", "Feature brecha = nivel vigente − nivel esperado según la edad. Con esta referencia el dataset casi no tiene rezago.", fig))

    # 10. Brecha relativa a la sala (rezago del FAQ)
    bs = feats.dropna(subset=["brecha_sala"])
    fig = px.histogram(
        bs,
        x="brecha_sala",
        nbins=int((bs["brecha_sala"].max() - bs["brecha_sala"].min()) * 2 + 1) if len(bs) else 5,
        title="Rezago relativo a la sala (nivel vigente menos mediana de su sala)",
        color_discrete_sequence=["#7c3aed"],
    )
    fig.update_layout(xaxis_title="brecha vs. mediana de la sala (niveles)", yaxis_title="niños/as", showlegend=False)
    if len(bs):
        fig.add_vline(x=UMBRAL_ALERTA, line_dash="dash", line_color=COLOR_ALERTA,
                      annotation_text=f"umbral alerta ({UMBRAL_ALERTA})", annotation_position="top right")
        n_sala = int((bs["brecha_sala"] <= UMBRAL_ALERTA).sum())
        fig.add_annotation(
            text=f"Alertas por comparación con pares: {n_sala} niños/as ({100*n_sala/len(bs):.0f}%). "
                 "Es la definición de rezago que pide Integra.",
            showarrow=False, xref="paper", yref="paper", x=0.5, y=1.18, font=dict(size=11, color=COLOR_ALERTA),
        )
    graficos.append(("brecha_sala", "Rezago relativo a la sala", "Feature brecha_sala: compara a cada niño/a con la mediana de niños/as de su propia sala (rezago de pares).", fig))

    # 11. Salas con más alertas (rezago de pares)
    por_sala = (
        feats.groupby(["id_jardin", "sala_grupo"])
        .agg(n_ninos=("id_nino", "size"), n_alertas=("alerta_sala", "sum"), nivel=("nivel_vigente", "mean"))
        .reset_index()
        .query("n_alertas > 0")
        .sort_values("n_alertas", ascending=False)
        .head(15)
    )
    if len(por_sala):
        por_sala["etiqueta"] = por_sala["id_jardin"] + " · " + por_sala["sala_grupo"]
        fig = px.bar(
            por_sala.sort_values("n_alertas"),
            x="n_alertas",
            y="etiqueta",
            orientation="h",
            text="n_alertas",
            title="Salas con más alertas de rezago (top 15)",
            color="n_alertas",
            color_continuous_scale="OrRd",
            hover_data=["n_ninos", "nivel"],
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(yaxis=dict(title=""), xaxis_title="niños/as en alerta", coloraxis_showscale=False)
    else:
        fig = _vacio(px.scatter(), "Sin alertas relativas a la sala")
    graficos.append(("alertas_sala", "Alertas por sala", "Salas donde más niños/as quedan por debajo de la mediana de su grupo (el aviso va a la educadora).", fig))


    # 10. Alertas por jardín
    por_jardin = features_jardin(feats, jardines).sort_values("n_alertas", ascending=False)
    fig = px.bar(
        por_jardin,
        x="n_alertas",
        y="nombre_fantasia",
        orientation="h",
        title="Alertas de rezago por jardín",
        color="pct_alertas",
        color_continuous_scale="OrRd",
        hover_data=["n_ninos", "nivel_promedio", "pct_alertas"],
    )
    fig.update_layout(
        yaxis=dict(autorange="reversed", title=""),
        xaxis_title="niños/as con alerta",
        coloraxis_colorbar_title="% alertas",
    )
    graficos.append(("alertas_jardin", "Alertas por jardín", "Jardines con más niños/as por debajo de la mediana de su sala (el aviso va a la directora).", fig))

    # 11. Nivel promedio por jardín
    pj = por_jardin.sort_values("nivel_promedio")
    fig = px.bar(
        pj,
        x="nivel_promedio",
        y="nombre_fantasia",
        orientation="h",
        title="Nivel promedio por jardín",
        color="nivel_promedio",
        color_continuous_scale="Blues",
        hover_data=["n_ninos", "n_alertas"],
    )
    fig.update_layout(yaxis=dict(title=""), xaxis_title="nivel promedio", coloraxis_showscale=False)
    graficos.append(("nivel_jardin", "Nivel promedio por jardín", "Promedio del nivel vigente en cada jardín; útil para comparar entre jardines.", fig))

    # 12. Cobertura de dominios por niño/a (feature)
    fig = px.histogram(
        feats,
        x="dominios_cubiertos",
        title="Dominios cubiertos por niño/a",
        color_discrete_sequence=["#2f855a"],
    )
    fig.update_layout(xaxis=dict(dtick=1), xaxis_title="dominios distintos observados (0-5)", yaxis_title="niños/as", showlegend=False)
    graficos.append(("dominios", "Cobertura de dominios", "Feature: cuántos de los 5 dominios tiene evidencia cada niño/a.", fig))

    # 13. Mapa de calor: manifestaciones observadas por nivel x dominio
    om_man = om.merge(man[["id_manifestacion", "nivel", "dominio"]], on="id_manifestacion", how="left")
    pivote = (
        om_man.groupby(["nivel", "dominio"]).size().unstack(fill_value=0).reindex(range(1, 10), fill_value=0)
    )
    fig = go.Figure(
        go.Heatmap(
            z=pivote.values,
            x=pivote.columns.tolist(),
            y=pivote.index.tolist(),
            colorscale="Blues",
            text=pivote.values,
            texttemplate="%{text}",
            hovertemplate="Nivel %{y}<br>%{x}<br>%{z} evidencias<extra></extra>",
        )
    )
    fig.update_layout(title="Evidencias observadas por nivel y dominio", xaxis_title="", yaxis_title="nivel")
    graficos.append(("heatmap", "Nivel × dominio", "Cuántas manifestaciones se registraron en cada combinación nivel-dominio.", fig))

    # 14. Niños/as por región
    reg = features_jardin(feats, jardines).groupby("region")["n_ninos"].sum().reset_index().sort_values("n_ninos")
    fig = px.bar(
        reg,
        x="n_ninos",
        y="region",
        orientation="h",
        title="Niños y niñas por región",
        color="n_ninos",
        color_continuous_scale="Teal",
    )
    fig.update_layout(yaxis=dict(title=""), xaxis_title="niños/as", coloraxis_showscale=False)
    graficos.append(("region", "Cobertura territorial", "Distribución de niños/as por región (contexto geográfico real, datos sintéticos).", fig))

    # 15. Experiencia de las educadoras
    fig = px.box(
        educadoras,
        x="rol",
        y="anios_experiencia",
        color="rol",
        points="all",
        title="Experiencia de las educadoras por rol",
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.update_layout(xaxis_title="", yaxis_title="años de experiencia", showlegend=False)
    graficos.append(("educadoras", "Equipo educativo", "Distribución de años de experiencia según rol (educadora vs. técnica).", fig))

    # 16. Matriz de correlación de features
    numericas = [
        "edad_meses", "nivel_vigente", "nivel_esperado", "brecha",
        "n_observaciones", "formatos_distintos", "dominios_cubiertos",
    ]
    corr = feats[numericas].corr(numeric_only=True)
    fig = px.imshow(
        corr,
        text_auto=".2f",
        color_continuous_scale="RdBu_r",
        zmin=-1,
        zmax=1,
        title="Correlación entre features",
    )
    fig.update_layout(xaxis_title="", yaxis_title="")
    graficos.append(("corr", "Correlaciones", "Matriz de correlación de las features numéricas derivadas.", fig))

    return graficos


# ---------------------------------------------------------------------------
# Render HTML
# ---------------------------------------------------------------------------

CSS = """
:root{--fondo:#f7f8fa;--sup:#fff;--borde:#e2e5ea;--texto:#1f2733;--tenue:#5b6676;--acento:#2563eb;--alerta:#b45309;--radio:12px}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;color:var(--texto);background:var(--fondo);line-height:1.5}
header{background:linear-gradient(135deg,#1e3a8a,#2563eb);color:#fff;padding:2rem 1rem}
.wrap{max-width:1200px;margin:0 auto;padding:0 1rem}
header h1{margin:0 0 .3rem;font-size:1.6rem}
header p{margin:.15rem 0;opacity:.92;font-size:.95rem}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1rem;margin:1.5rem 0}
.kpi{background:var(--sup);border:1px solid var(--borde);border-radius:var(--radio);padding:1rem;box-shadow:0 1px 3px rgba(16,24,40,.08)}
.kpi .n{font-size:1.8rem;font-weight:700;color:var(--acento)}
.kpi .l{font-size:.8rem;color:var(--tenue)}
section{background:var(--sup);border:1px solid var(--borde);border-radius:var(--radio);padding:1rem 1.25rem;margin:0 0 1.25rem;box-shadow:0 1px 3px rgba(16,24,40,.08)}
section h3{margin:.25rem 0 .35rem;font-size:1rem}
section p.desc{margin:0 0 .75rem;color:var(--tenue);font-size:.88rem}
table{border-collapse:collapse;width:100%;font-size:.9rem}
th,td{text-align:left;padding:.5rem .6rem;border-bottom:1px solid var(--borde)}
th{background:var(--fondo);color:var(--tenue);font-size:.82rem}
td.num,th.num{text-align:right}
.alerta{color:var(--alerta);font-weight:600}
footer{color:var(--tenue);font-size:.85rem;text-align:center;padding:2rem 1rem}
.badge{display:inline-block;background:#e8f0fe;color:var(--acento);border-radius:999px;padding:.1rem .6rem;font-size:.78rem;font-weight:600}
"""


def _tabla_html(df: pd.DataFrame, numericas: set[str] | None = None) -> str:
    numericas = numericas or set()
    encab = "".join(f"<th>{c}</th>" for c in df.columns)
    filas = []
    for _, fila in df.iterrows():
        celdas = []
        for c in df.columns:
            clase = ' class="num"' if c in numericas else ""
            celdas.append(f"<td{clase}>{fila[c]}</td>")
        filas.append("<tr>" + "".join(celdas) + "</tr>")
    return f"<table><thead><tr>{encab}</tr></thead><tbody>{''.join(filas)}</tbody></table>"


def render(datos, feats, jardines_feats, calidad, checks, graficos, salida: Path) -> Path:
    total_ninos = len(feats)
    alertas_sala = int(feats["alerta_sala"].sum())
    pct_sala = 100 * alertas_sala / total_ninos if total_ninos else 0
    alertas_edad = int(feats["alerta"].sum())
    kpis = [
        ("Jardines", datos["jardines"]["id_jardin"].nunique()),
        ("Salas", feats[["id_jardin", "sala_grupo"]].drop_duplicates().shape[0]),
        ("Niños/as", total_ninos),
        ("Educadoras", len(datos["educadoras"])),
        ("Observaciones", len(datos["observaciones"])),
        ("Manifestaciones", len(datos["manifestaciones"])),
        ("Alertas (vs. sala)", f"{alertas_sala} ({pct_sala:.0f}%)"),
        ("Nivel promedio", f"{feats['nivel_vigente'].mean():.1f}"),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="n">{v}</div><div class="l">{l}</div></div>' for l, v in kpis
    )

    calidad_html = _tabla_html(calidad, numericas={"filas", "columnas", "nulos", "duplicados_PK"})
    checks_html = "".join(
        f"<tr><td>{nombre}</td><td class='num'>{valor}</td></tr>" for nombre, valor in checks
    )

    tarjetas = []
    for _id, titulo, desc, fig in graficos:
        fig.update_layout(
            font=dict(family="system-ui, Segoe UI, Roboto, Arial", size=12),
            margin=dict(t=56, r=16, b=48, l=56),
            paper_bgcolor="white",
            plot_bgcolor="white",
        )
        div = pio.to_html(fig, full_html=False, include_plotlyjs=False, config={"displaylogo": False, "responsive": True})
        tarjetas.append(
            f'<section id="{_id}"><h3>{titulo}</h3>'
            + (f'<p class="desc">{desc}</p>' if desc else "")
            + div
            + "</section>"
        )

    html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Datos sintéticos IntegrAI — revisión</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>{CSS}</style></head>
<body>
<header><div class="wrap">
<h1>Datos sintéticos E-1 · IntegrAI</h1>
<p>Reporte interactivo para revisión del equipo y visto bueno.</p>
<p>Generado el {date.today():%d-%m-%Y} · fuente: <code>data/*.csv</code> <span class="badge">datos 100% sintéticos</span></p>
</div></header>
<main class="wrap">
<div class="kpis">{kpi_html}</div>

<section id="calidad">
<h3>Calidad de datos</h3>
<p class="desc">Conteos, valores nulos y duplicados por tabla.</p>
{calidad_html}
</section>

<section id="checks">
<h3>Chequeos de integridad</h3>
<p class="desc">Verificaciones de consistencia referencial y de rangos.</p>
<table><thead><tr><th>chequeo</th><th class="num">resultado</th></tr></thead><tbody>{checks_html}</tbody></table>
</section>

<h2 style="margin:1.5rem 0 .5rem">Visualizaciones</h2>
{''.join(tarjetas)}
</main>
<footer>Reporte de apoyo · no es un instrumento clínico · datos sintéticos con fines pedagógicos.</footer>
</body></html>"""

    salida.write_text(html, encoding="utf-8")
    return salida


def imprimir_resumen(feats: pd.DataFrame, calidad: pd.DataFrame, checks, salida: Path) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    print("=" * 60)
    print("REPORTE DE DATOS SINTETICOS - IntegrAI")
    print("=" * 60)
    print(f"Ninos/as: {len(feats)} | Nivel promedio: {feats['nivel_vigente'].mean():.2f}")
    print(f"Alertas vs. sala (rezago de pares): {int(feats['alerta_sala'].sum())} "
          f"({100*feats['alerta_sala'].mean():.0f}%) | "
          f"Alertas vs. edad (umbral {UMBRAL_ALERTA}): {int(feats['alerta'].sum())}")
    print("\nTablas:")
    print(calidad.to_string(index=False))
    print("\nChequeos:")
    for nombre, valor in checks:
        print(f"  - {nombre}: {valor}")
    print(f"\nHTML generado: {salida}")


def cargar_dominios(datos_dir: Path | None = None) -> list[dict]:
    return json.loads(((datos_dir or DATA) / "dominios.json").read_text(encoding="utf-8"))


def construir_payload(
    datos: dict[str, pd.DataFrame], feats: pd.DataFrame, dominios: list[dict]
) -> dict:
    """Estructura compacta para el dashboard (datos por niño/a y por observación)."""
    jmap = datos["jardines"].set_index("id_jardin")
    ninos = []
    for _, r in feats.iterrows():
        j = jmap.loc[r["id_jardin"]]
        ninos.append(
            {
                "id": r["id_nino"],
                "jardin": r["id_jardin"],
                "region": j["region"],
                "comuna": j["comuna"],
                "sala": r["sala_grupo"],
                "tramo": r["tramo"],
                "sexo": r["sexo_registrado"],
                "edad": None if pd.isna(r["edad_meses"]) else round(float(r["edad_meses"]), 1),
                "nivelVigente": None if pd.isna(r["nivel_vigente"]) else int(r["nivel_vigente"]),
                "nivelEsperado": None if pd.isna(r["nivel_esperado"]) else int(r["nivel_esperado"]),
                "brecha": None if pd.isna(r["brecha"]) else float(r["brecha"]),
                "brechaSala": None if pd.isna(r["brecha_sala"]) else float(r["brecha_sala"]),
                "alerta": bool(r["alerta_sala"]),
                "nObs": int(r["n_observaciones"]),
                "formatos": int(r["formatos_distintos"]),
                "dominios": int(r["dominios_cubiertos"]),
                "tieneVideo": bool(r["tiene_video"]),
            }
        )

    didx = {d["id"]: i for i, d in enumerate(dominios)}
    om = datos["observacion_manifestaciones"].merge(
        datos["manifestaciones"][["id_manifestacion", "dominio"]], on="id_manifestacion", how="left"
    )
    dom_por_obs = (
        om.groupby("id_observacion")["dominio"]
        .apply(lambda s: sorted({didx[d] for d in s if d in didx}))
        .to_dict()
    )
    obs = [
        {
            "idNino": r["id_nino"],
            "mes": f"{r['fecha_observacion']:%Y-%m}",
            "formato": r["formato_captura"],
            "nivel": int(r["nivel_estimado"]),
            "dominios": dom_por_obs.get(r["id_observacion"], []),
        }
        for _, r in datos["observaciones"].iterrows()
    ]
    jardines = [
        {"id": r["id_jardin"], "nombre": r["nombre_fantasia"], "region": r["region"], "comuna": r["comuna"]}
        for _, r in datos["jardines"].iterrows()
    ]
    return {
        "ninos": ninos,
        "obs": obs,
        "jardines": jardines,
        "dominios": [d["nombre"] for d in dominios],
        "tramos": [
            "Sala Cuna (0-23 m)",
            "Nivel Medio (24-47 m)",
            "Transición (48-71 m)",
            "Fuera de rango (>=72 m)",
        ],
        "niveles": list(range(1, 10)),
        "umbral": UMBRAL_ALERTA,
        "edadMin": int(feats["edad_meses"].min()),
        "edadMax": int(feats["edad_meses"].max()),
        "generado": f"{date.today():%d-%m-%Y}",
    }


CSS_DASH = """
:root{--fondo:#f5f7fa;--sup:#fff;--borde:#e4e8ee;--texto:#1e293b;--tenue:#64748b;
--acento:#2563eb;--acento2:#0f766e;--alerta:#dc2626;--radio:14px}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;color:var(--texto);background:var(--fondo)}
.app{display:flex;min-height:100vh}
aside{position:sticky;top:0;align-self:flex-start;width:290px;height:100vh;overflow-y:auto;
background:var(--sup);border-right:1px solid var(--borde);padding:1.1rem}
aside h2{font-size:1rem;margin:.2rem 0 1rem}
aside .grupo{margin-bottom:.9rem}
aside label{display:block;font-size:.78rem;color:var(--tenue);margin-bottom:.25rem;font-weight:600}
select[multiple]{width:100%;border:1px solid var(--borde);border-radius:9px;padding:.25rem;font-size:.82rem;background:#fbfcfe}
select[multiple]:focus,input:focus{outline:2px solid #bfdbfe;border-color:var(--acento)}
input,select{font-family:inherit}
.fila{display:flex;gap:.5rem}
.fila>div{flex:1}
input[type=number]{width:100%;border:1px solid var(--borde);border-radius:9px;padding:.35rem;font-size:.82rem}
.chk{display:flex;align-items:center;gap:.45rem;font-size:.85rem;color:var(--texto)}
button{border:0;border-radius:9px;padding:.5rem .8rem;font-size:.85rem;font-weight:600;cursor:pointer}
#btn-limpiar{width:100%;background:#eef2f7;color:var(--texto)}
#btn-limpiar:hover{background:#e2e8f0}
.ayuda{font-size:.75rem;color:var(--tenue);margin-top:.6rem;line-height:1.4}
main{flex:1;padding:1.3rem 1.5rem 3rem;max-width:1500px}
header h1{font-size:1.35rem;margin:0 0 .2rem}
header p{margin:.1rem 0;color:var(--tenue);font-size:.9rem}
.badge{display:inline-block;background:#e8f0fe;color:var(--acento);border-radius:999px;
padding:.1rem .6rem;font-size:.75rem;font-weight:700;margin-left:.4rem}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:.9rem;margin:1rem 0}
.kpi{background:var(--sup);border:1px solid var(--borde);border-radius:var(--radio);padding:.85rem 1rem;
box-shadow:0 1px 2px rgba(16,24,40,.05)}
.kpi .n{font-size:1.5rem;font-weight:800;color:var(--acento)}
.kpi .l{font-size:.75rem;color:var(--tenue);margin-top:.15rem}
.kpi.alerta .n{color:var(--alerta)}
#reco{background:linear-gradient(135deg,#eff6ff,#f0fdfa);border:1px solid #dbeafe;border-radius:var(--radio);
padding:1rem 1.2rem;margin-bottom:1.2rem}
#reco h3{margin:0 0 .5rem;font-size:1rem}
#reco ul{margin:.2rem 0;padding-left:1.1rem}
#reco li{margin:.35rem 0;font-size:.88rem}
#reco .mini{font-size:.8rem;color:var(--tenue);margin:.5rem 0 0}
h2.seccion{font-size:1.05rem;margin:1.6rem 0 .7rem;padding-bottom:.3rem;border-bottom:2px solid var(--borde)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:1rem}
.card{background:var(--sup);border:1px solid var(--borde);border-radius:var(--radio);padding:1rem 1.1rem;
box-shadow:0 1px 3px rgba(16,24,40,.06)}
.card.wide{grid-column:1/-1}
.card h3{margin:0 0 .2rem;font-size:.95rem}
.card .purpose{margin:0 0 .6rem;color:var(--tenue);font-size:.82rem}
.plot{width:100%}
details{margin-top:.6rem;border-top:1px dashed var(--borde);padding-top:.5rem}
details summary{cursor:pointer;font-size:.82rem;font-weight:600;color:var(--acento2)}
details p{font-size:.83rem;color:#475569;margin:.45rem 0 0;line-height:1.5}
.inline{display:flex;align-items:center;gap:.5rem;font-size:.83rem;color:var(--tenue);margin-bottom:.4rem}
.inline select{border:1px solid var(--borde);border-radius:9px;padding:.3rem .5rem;font-size:.83rem}
footer{color:var(--tenue);font-size:.8rem;text-align:center;padding:2rem 1rem}
.rol{display:flex;gap:.3rem;margin:.7rem 0 .2rem;background:#eef2f7;border-radius:10px;padding:.25rem;max-width:440px}
.rol button{flex:1;background:transparent;color:var(--tenue);padding:.42rem .3rem;font-size:.8rem;border:0;cursor:pointer;font-weight:600}
.rol button.activo{background:#fff;color:var(--acento);box-shadow:0 1px 3px rgba(16,24,40,.12)}
nav.tabs{display:flex;gap:.25rem;flex-wrap:wrap;border-bottom:2px solid var(--borde);margin:1.1rem 0 0;
position:sticky;top:0;background:var(--fondo);z-index:6;padding-top:.35rem}
nav.tabs button{background:transparent;color:var(--tenue);padding:.55rem .95rem;font-size:.88rem;border:0;
border-bottom:3px solid transparent;cursor:pointer;border-radius:9px 9px 0 0;font-weight:600}
nav.tabs button.activo{color:var(--acento);border-bottom-color:var(--acento)}
h2.seccion{display:none}
.panel-etica{display:none;padding-top:1rem;max-width:920px}
.panel-etica.activo{display:block}
.etica h1{font-size:1.15rem;margin:.2rem 0 .6rem}
.etica h2{font-size:1.02rem;margin:1.3rem 0 .4rem}
.etica h3{font-size:.95rem;margin:1.1rem 0 .3rem;color:var(--acento2)}
.etica p,.etica li{font-size:.88rem;color:#475569;line-height:1.6}
.etica ul{padding-left:1.1rem}
.etica .caja{background:#fff;border:1px solid var(--borde);border-left:4px solid var(--acento2);
border-radius:10px;padding:.8rem 1rem;margin:.7rem 0}
.etica .regla{font-family:ui-monospace,Consolas,monospace;background:#f1f5f9;border-radius:6px;
padding:.1rem .4rem;font-size:.82rem;color:#0f172a}
.etica .aviso{border-left-color:var(--alerta);background:#fef2f2}
.historia{background:linear-gradient(135deg,#0f172a,#1e3a8a);color:#e2e8f0;border-radius:var(--radio);padding:1.2rem 1.3rem;margin:1rem 0}
.historia h2{margin:0 0 .2rem;font-size:1.05rem;color:#fff}
.historia .sub{margin:0 0 .9rem;font-size:.85rem;color:#c7d2fe}
.pasos{list-style:none;display:flex;gap:.5rem;margin:0;padding:0;flex-wrap:wrap}
.paso{flex:1 1 150px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.15);border-radius:12px;padding:.7rem .75rem;cursor:pointer;transition:.15s}
.paso:hover{background:rgba(255,255,255,.16);transform:translateY(-2px)}
.paso .num{display:inline-flex;width:1.5rem;height:1.5rem;align-items:center;justify-content:center;border-radius:50%;background:var(--acento);color:#fff;font-weight:800;font-size:.8rem}
.paso h4{margin:.4rem 0 .2rem;font-size:.88rem;color:#fff}
.paso p{margin:0;font-size:.78rem;color:#cbd5e1;line-height:1.4}
.paso.activo{background:rgba(37,99,235,.35);border-color:#93c5fd}
.narr{display:grid;grid-template-columns:repeat(2,1fr);gap:.5rem;margin:.7rem 0 .1rem}
.beat{border-radius:10px;padding:.5rem .65rem;font-size:.8rem;line-height:1.45}
.beat .bk{display:block;font-weight:700;font-size:.72rem;letter-spacing:.02em;text-transform:uppercase;margin-bottom:.15rem;opacity:.85}
.beat p{margin:0;color:#334155}
.beat.ve{background:#eff6ff;border-left:3px solid var(--acento)}
.beat.ve .bk{color:var(--acento)}
.beat.sig{background:#f0fdfa;border-left:3px solid var(--acento2)}
.beat.sig .bk{color:var(--acento2)}
.beat.imp{background:#fffbeb;border-left:3px solid #d97706}
.beat.imp .bk{color:#b45309}
.beat.acc{background:#ecfdf5;border-left:3px solid #059669;grid-column:1/-1}
.beat.acc .bk{color:#047857}
.card.destacada{box-shadow:0 0 0 3px #93c5fd,0 1px 3px rgba(16,24,40,.1);transition:box-shadow .3s}
@media(max-width:820px){aside{position:static;width:100%;height:auto}.app{flex-direction:column}.narr{grid-template-columns:1fr}.beat.acc{grid-column:auto}}
"""

PLANTILLA_DASH = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Panel de decisiones · IntegrAI</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>__CSS__</style></head>
<body>
<div class="app">
<aside>
  <h2>Filtros</h2>
  <div class="grupo"><label>Jardín</label><select id="f-jardin" multiple size="4"></select></div>
  <div class="grupo"><label>Región</label><select id="f-region" multiple size="3"></select></div>
  <div class="grupo"><label>Tramo</label><select id="f-tramo" multiple size="4"></select></div>
  <div class="grupo"><label>Sala</label><select id="f-sala" multiple size="3"></select></div>
  <div class="grupo"><label>Sexo registrado</label><select id="f-sexo" multiple size="4"></select></div>
  <div class="grupo"><label>Nivel vigente</label><select id="f-nivel" multiple size="3"></select></div>
  <div class="grupo"><label>Edad (meses)</label>
    <div class="fila"><div><input type="number" id="f-emin" placeholder="mín"></div>
    <div><input type="number" id="f-emax" placeholder="máx"></div></div></div>
  <div class="grupo"><label>Formato de captura</label>
    <select id="f-formato"><option value="todos">Todos</option><option>texto</option>
    <option>audio</option><option>foto</option><option>video</option></select></div>
  <div class="grupo"><label class="chk"><input type="checkbox" id="f-alerta"> Mostrar solo alertas de rezago</label></div>
  <button id="btn-limpiar">Limpiar filtros</button>
  <p class="ayuda">Sin selección en una lista = incluir todo. Las listas se combinan entre sí.
  Los filtros se aplican al instante.</p>
</aside>
<main>
<header>
  <h1>Panel de decisiones · IntegrAI<span class="badge">datos sintéticos</span></h1>
  <p id="resumen-filtros">—</p>
  <p>Del dato a la acción: revisa, decide y fundamenta el <strong>plan pedagógico, comunitario y social</strong> de tu salón y jardín. Generado el __GENERADO__.</p>
  <div class="rol" id="rol" title="La vista se adapta a tu rol">
    <button data-rol="parvularia" class="activo">Parvularia</button>
    <button data-rol="directora">Directora</button>
    <button data-rol="equipo">Equipo Integra</button>
  </div>
</header>
<nav class="tabs" id="tabs">
  <button data-tab="acompanar" class="activo">Acompañar (pedagógico)</button>
  <button data-tab="comunidad">Registro y comunidad</button>
  <button data-tab="bienestar">Bienestar integral</button>
  <button data-tab="etica">Ética y derechos</button>
</nav>

<section class="historia" id="historia">
  <h2>La historia de un dato que cambia una semana</h2>
  <p class="sub">En cinco pasos, una observación de 30 segundos se convierte en una decisión con fundamento. Toca un paso para ver el gráfico que lo respalda.</p>
  <ol class="pasos">
    <li class="paso" data-tab="comunidad" data-card="card-formato"><span class="num">1</span><h4>Observas</h4><p>Grabas una nota de voz o una foto de 30 segundos mientras acompañas.</p></li>
    <li class="paso" data-tab="acompanar" data-card="card-nivel"><span class="num">2</span><h4>El sistema propone</h4><p>Un nivel con la evidencia del catálogo, siempre como sugerencia para tu criterio.</p></li>
    <li class="paso" data-tab="acompanar" data-card="card-bsala"><span class="num">3</span><h4>Comparas</h4><p>Ves ese nivel frente al de su sala y al esperable por edad.</p></li>
    <li class="paso activo" data-tab="acompanar" data-card="card-alertas"><span class="num">4</span><h4>Detectas la señal</h4><p>Aparece una diferencia entre pares que merece tu mirada.</p></li>
    <li class="paso" data-tab="acompanar" data-card="card-tray"><span class="num">5</span><h4>Actúas y documentas</h4><p>Ajustas el plan, vuelves a observar y la evidencia queda registrada.</p></li>
  </ol>
</section>

<div class="kpis">
  <div class="kpi"><div class="n" id="k-ninos">—</div><div class="l">Niños/as en vista</div></div>
  <div class="kpi"><div class="n" id="k-obs">—</div><div class="l">Observaciones</div></div>
  <div class="kpi"><div class="n" id="k-nivel">—</div><div class="l">Nivel promedio</div></div>
  <div class="kpi alerta"><div class="n" id="k-alertas">—</div><div class="l">Alertas de rezago (vs. sala)</div></div>
  <div class="kpi"><div class="n" id="k-salas">—</div><div class="l">Grupos en vista</div></div>
</div>

<div id="reco"><h3>Prioridades sugeridas para el plan</h3><p class="mini">Cargando…</p></div>

<h2 class="seccion">Plan pedagógico (escolar) · dónde y a quién acompañar</h2>
<div class="grid">
  <section class="card wide" id="card-tray">
    <h3>Trayectoria de un niño/a en el tiempo</h3>
    <p class="purpose">Sigue el avance real de un niño/a y compáralo con el promedio de su grupo.</p>
    <div class="inline">Niño/a: <select id="f-nino"></select></div>
    <div class="plot" id="fig-tray" style="height:320px"></div>
    <div class="narr">
      <div class="beat ve"><span class="bk">Qué veo</span><p>La línea sólida es un niño/a; la punteada, el promedio de su sala. Vertical: nivel (1–9). Horizontal: el tiempo.</p></div>
      <div class="beat sig"><span class="bk">Qué significa</span><p>Si la línea sube, hay avance. Si se aplana, se quedó en el mismo nivel aunque sigan las observaciones.</p></div>
      <div class="beat imp"><span class="bk">Por qué importa</span><p>Una línea plana es la señal más honesta de que necesita <strong>otro tipo de experiencia</strong>, no más de lo mismo.</p></div>
      <div class="beat acc"><span class="bk">Qué hago</span><p>Elige un niño/a con la línea plana, prueba una actividad distinta y vuelve a observar en dos semanas.</p></div>
    </div>
  </section>
  <section class="card" id="card-nivel">
    <h3>Nivel vigente del grupo</h3>
    <p class="purpose">En qué nivel está hoy cada niño/a.</p>
    <div class="plot" id="fig-nivel" style="height:280px"></div>
    <div class="narr">
      <div class="beat ve"><span class="bk">Qué veo</span><p>Una barra por nivel: cuántos niños y niñas están hoy en cada uno.</p></div>
      <div class="beat sig"><span class="bk">Qué significa</span><p>Dónde se concentra el grupo y cuánta dispersión hay entre un extremo y otro.</p></div>
      <div class="beat imp"><span class="bk">Por qué importa</span><p>Un grupo muy disperso necesita experiencias por subgrupos; uno concentrado, una actividad común.</p></div>
      <div class="beat acc"><span class="bk">Qué hago</span><p>Planifica una experiencia para el nivel más frecuente y una variante para los extremos.</p></div>
    </div>
  </section>
  <section class="card" id="card-edad">
    <h3>Edad vs. nivel alcanzado</h3>
    <p class="purpose">Relaciona la edad con el nivel observado.</p>
    <div class="plot" id="fig-edad" style="height:280px"></div>
    <div class="narr">
      <div class="beat ve"><span class="bk">Qué veo</span><p>Cada punto es un niño/a: edad (eje X) y nivel alcanzado (eje Y).</p></div>
      <div class="beat sig"><span class="bk">Qué significa</span><p>Los puntos bajo la tendencia se apartan de lo esperable para su edad.</p></div>
      <div class="beat imp"><span class="bk">Por qué importa</span><p>Ahí la edad no explica el nivel: es justo donde el acompañamiento marca la diferencia.</p></div>
      <div class="beat acc"><span class="bk">Qué hago</span><p>Mira los tres puntos más bajos y revisa su trayectoria antes de decidir.</p></div>
    </div>
  </section>
  <section class="card" id="card-bsala">
    <h3>Rezago relativo a la sala</h3>
    <p class="purpose">Cuánto queda cada niño/a por debajo de la mediana de su sala.</p>
    <div class="plot" id="fig-bsala" style="height:280px"></div>
    <div class="narr">
      <div class="beat ve"><span class="bk">Qué veo</span><p>Cuánto queda cada niño/a por debajo de la mediana de su propia sala.</p></div>
      <div class="beat sig"><span class="bk">Qué significa</span><p>A la izquierda del umbral están quienes más se distancian de sus pares.</p></div>
      <div class="beat imp"><span class="bk">Por qué importa</span><p>Es el rezago que ves todos los días, medido contra el grupo real y no contra un ideal.</p></div>
      <div class="beat acc"><span class="bk">Qué hago</span><p>Prioriza a los del extremo y conversa con la familia con esta evidencia concreta.</p></div>
    </div>
  </section>
  <section class="card" id="card-alertas">
    <h3>Grupos con más alertas</h3>
    <p class="purpose">Salas y jardines donde se concentra el rezago.</p>
    <div class="plot" id="fig-alertas" style="height:300px"></div>
    <div class="narr">
      <div class="beat ve"><span class="bk">Qué veo</span><p>Salas y jardines ordenados por número de alertas de rezago.</p></div>
      <div class="beat sig"><span class="bk">Qué significa</span><p>Dónde se concentra el rezago dentro del jardín.</p></div>
      <div class="beat imp"><span class="bk">Por qué importa</span><p>Un grupo con muchas señales puede necesitar apoyo al <strong>equipo</strong>, no solo a un niño/a.</p></div>
      <div class="beat acc"><span class="bk">Qué hago</span><p>Si una sala destaca, coordina refuerzo de material y apoyo a la educadora.</p></div>
    </div>
  </section>
  <section class="card" id="card-brecha">
    <h3>Brecha vs. lo esperado por edad</h3>
    <p class="purpose">Distancia entre el nivel del niño/a y el esperado para su edad.</p>
    <div class="plot" id="fig-brecha" style="height:280px"></div>
    <details><summary>Cómo leerlo y usarlo con criterio</summary>
    <p>Complementa la mirada de grupo con la <strong>referencia etaria</strong> (curva de niveles).
    Sirve para justificar decisiones ante la familia y la dirección.</p></details>
  </section>
  <section class="card" id="card-dominios">
    <h3>Cobertura de dominios por niño/a</h3>
    <p class="purpose">Cuántos de los 5 dominios tienen evidencia.</p>
    <div class="plot" id="fig-dominios" style="height:280px"></div>
    <div class="narr">
      <div class="beat ve"><span class="bk">Qué veo</span><p>Cuántos de los 5 dominios tienen al menos una evidencia por niño/a.</p></div>
      <div class="beat sig"><span class="bk">Qué significa</span><p>Aparecen niños y niñas con pocos dominios observados.</p></div>
      <div class="beat imp"><span class="bk">Por qué importa</span><p>No es que estén mal: es que <strong>no hay respaldo</strong> para decidir sobre ellos.</p></div>
      <div class="beat acc"><span class="bk">Qué hago</span><p>La próxima semana observa el dominio que falta en dos niños/as.</p></div>
    </div>
  </section>
</div>

<h2 class="seccion">Plan comunitario · familias, territorio y registro</h2>
<div class="grid">
  <section class="card" id="card-formato">
    <h3>Formatos de captura</h3>
    <p class="purpose">Cómo se registra la evidencia.</p>
    <div class="plot" id="fig-formato" style="height:280px"></div>
    <div class="narr">
      <div class="beat ve"><span class="bk">Qué veo</span><p>Cómo se registra: texto, audio, foto o video.</p></div>
      <div class="beat sig"><span class="bk">Qué significa</span><p>Qué canales usa hoy el equipo para capturar la observación.</p></div>
      <div class="beat imp"><span class="bk">Por qué importa</span><p>Una <strong>nota de voz de 30 segundos</strong> documenta igual que media hora escribiendo.</p></div>
      <div class="beat acc"><span class="bk">Qué hago</span><p>Prueba grabar una nota de voz en la próxima observación.</p></div>
    </div>
  </section>
  <section class="card" id="card-obsnino">
    <h3>Observaciones por niño/a</h3>
    <p class="purpose">Cuántas veces se observó a cada niño/a.</p>
    <div class="plot" id="fig-obsnino" style="height:280px"></div>
    <details><summary>Cómo leerlo y usarlo con criterio</summary>
    <p>Detecta niños/as con <strong>poca cobertura</strong> para equilibrar la observación y
    asegurar que todas las familias reciban retroalimentación.</p></details>
  </section>
  <section class="card" id="card-tiempo">
    <h3>Observaciones en el tiempo</h3>
    <p class="purpose">Ritmo de registro mes a mes.</p>
    <div class="plot" id="fig-tiempo" style="height:280px"></div>
    <div class="narr">
      <div class="beat ve"><span class="bk">Qué veo</span><p>Cuántas observaciones se registraron cada mes.</p></div>
      <div class="beat sig"><span class="bk">Qué significa</span><p>Los meses con caídas de registro (vacaciones, sobrecarga).</p></div>
      <div class="beat imp"><span class="bk">Por qué importa</span><p>Sin registro continuo la trayectoria se corta y las decisiones quedan <strong>a ciegas</strong>.</p></div>
      <div class="beat acc"><span class="bk">Qué hago</span><p>Detecta el mes flojo y acuerda una meta mínima de observaciones.</p></div>
    </div>
  </section>
  <section class="card" id="card-region">
    <h3>Cobertura territorial</h3>
    <p class="purpose">Distribución por región.</p>
    <div class="plot" id="fig-region" style="height:300px"></div>
    <details><summary>Cómo leerlo y usarlo con criterio</summary>
    <p>Sitúa la decisión en el contexto del jardín y permite comparar con otros territorios
    para articular apoyos del <strong>plan comunitario</strong>.</p></details>
  </section>
</div>

<h2 class="seccion">Plan social y convivencia · desarrollo integral</h2>
<div class="grid">
  <section class="card wide" id="card-heat">
    <h3>Evidencias por nivel y dominio</h3>
    <p class="purpose">Qué dominios tienen más o menos registro en cada nivel.</p>
    <div class="plot" id="fig-heat" style="height:340px"></div>
    <div class="narr">
      <div class="beat ve"><span class="bk">Qué veo</span><p>Mapa de calor: nivel (filas) × dominio (columnas); el color es el nº de evidencias.</p></div>
      <div class="beat sig"><span class="bk">Qué significa</span><p>Los cuadros claros son dominios poco observados en ese nivel.</p></div>
      <div class="beat imp"><span class="bk">Por qué importa</span><p>Los vacíos de evidencia son <strong>puntos ciegos del plan</strong>, sobre todo en lo socioemocional.</p></div>
      <div class="beat acc"><span class="bk">Qué hago</span><p>Elige un cuadro claro y observa ese dominio esta semana.</p></div>
    </div>
  </section>
  <section class="card" id="card-tramo">
    <h3>Composición por tramo</h3>
    <p class="purpose">Niños/as por tramo educativo.</p>
    <div class="plot" id="fig-tramo" style="height:280px"></div>
    <div class="narr">
      <div class="beat ve"><span class="bk">Qué veo</span><p>Cuántos niños y niñas hay en cada tramo (Sala Cuna, Nivel Medio, Transición).</p></div>
      <div class="beat sig"><span class="bk">Qué significa</span><p>La composición del grupo por edad.</p></div>
      <div class="beat imp"><span class="bk">Por qué importa</span><p>Define cómo agrupar y qué experiencias ofrecer a cada subgrupo.</p></div>
      <div class="beat acc"><span class="bk">Qué hago</span><p>Ajusta los agrupamientos según dónde está la mayoría.</p></div>
    </div>
  </section>
</div>

<section class="panel-etica" id="card-etica">
<div class="etica">
<h1>Ética, derechos y reglas del panel</h1>
<p>Este panel apoya la <strong>decisión pedagógica</strong> de las personas a cargo. No reemplaza su criterio ni emite juicios sobre los niños y niñas.</p>

<h2>Qué significa lo que ves</h2>
<ul>
<li><strong>Nivel vigente:</strong> la última estimación registrada para cada niño/a, a partir de sus observaciones.</li>
<li><strong>Nivel esperado:</strong> la banda orientativa de la ruta para su edad. Es una referencia, no una norma rígida.</li>
<li><strong>Rezago relativo a la sala:</strong> cuánto queda un niño/a por debajo de la mediana de su propio grupo.</li>
<li><strong>Alerta de rezago:</strong> aviso cuando el nivel queda por debajo de su grupo o de su banda etaria. Es una sugerencia para mirar con atención.</li>
</ul>

<h2>Reglas de las alertas (y sus límites)</h2>
<div class="caja">
<p>Base comparativa: <span class="regla">nivel vigente &minus; mediana de la sala</span>.</p>
<p>Umbral de alerta: <span class="regla">&le; &minus;2 niveles</span>. Se activa solo ante una diferencia notoria, para reducir falsas alarmas.</p>
<p>Señales de apoyo: <strong>estancamiento</strong> (varias observaciones en el mismo nivel) y <strong>evidencia insuficiente</strong> (menos de 2 observaciones).</p>
</div>
<p>Las alertas son <strong>hipótesis</strong>: un ritmo distinto no es un déficit. Deben leerse con el contexto del niño/a, su familia y el equipo.</p>

<h2>Derechos y principios</h2>
<ul>
<li><strong>Interés superior del niño/a</strong> por sobre cualquier indicador.</li>
<li><strong>No estigmatización:</strong> los datos se usan para apoyar, nunca para etiquetar o rankear públicamente a un niño/a.</li>
<li><strong>Participación:</strong> se considera la voz del niño/a y su familia en las decisiones.</li>
<li><strong>No discriminación</strong> por sexo, origen, condición o ritmo de desarrollo.</li>
<li><strong>Privacidad y minimización:</strong> solo datos necesarios; sin RUT ni nombres reales; los medios se usan y se eliminan.</li>
</ul>

<h2>Marco de referencia</h2>
<p>Convención sobre los Derechos del Niño · Ley 21.719 de protección de datos personales (Chile) · Bases Curriculares de Educación Parvularia (MINEDUC).</p>

<div class="caja aviso"><strong>Recuerda:</strong> las sugerencias las propone el sistema; la decisión final y su fundamento son de la educadora, la directora o el equipo a cargo. Ante la duda, revisar en conjunto y con la familia.</div>
</div>
</section>

<footer>Panel de apoyo a la decisión pedagógica · no es un instrumento clínico · datos 100% sintéticos.
La educadora mantiene siempre la decisión final.</footer>
</main>
</div>
<script>
__DATA__
__APP__
</script>
</body></html>
"""

APP_JS = r"""
const DATA = window.__PAYLOAD__;
const NINOS = DATA.ninos, OBS = DATA.obs, JARD = DATA.jardines, DOMS = DATA.dominios,
      TRAMOS = DATA.tramos, NIVELES = DATA.niveles, UMBRAL = DATA.umbral;
const JNOM = Object.fromEntries(JARD.map(j => [j.id, j.nombre]));
const COLORS = ["#2563eb","#0891b2","#7c3aed","#d97706","#059669","#db2777"];
const $ = id => document.getElementById(id);
const uniq = a => [...new Set(a)];
const mean = a => a.length ? a.reduce((s,x)=>s+x,0)/a.length : null;
const CFG = {responsive:true, displaylogo:false, modeBarButtonsToRemove:["lasso2d","select2d","autoScale2d"]};

const TAB_DE = {
  "card-tray":"acompanar","card-nivel":"acompanar","card-edad":"acompanar",
  "card-bsala":"acompanar","card-alertas":"acompanar",
  "card-dominios":"comunidad","card-formato":"comunidad","card-tiempo":"comunidad",
  "card-heat":"bienestar","card-tramo":"bienestar"
};
const OCULTAS = ["card-brecha","card-obsnino","card-region"];
const FIGS_TAB = {
  acompanar:["fig-tray","fig-nivel","fig-edad","fig-bsala","fig-alertas"],
  comunidad:["fig-dominios","fig-formato","fig-tiempo"],
  bienestar:["fig-heat","fig-tramo"]
};
let TAB = "acompanar", ROL = "parvularia";

function applyTabs(){
  Object.keys(TAB_DE).forEach(id => { const el = $(id); if(el) el.style.display = (TAB_DE[id]===TAB) ? "" : "none"; });
  OCULTAS.forEach(id => { const el = $(id); if(el) el.style.display = "none"; });
  const et = $("card-etica"); if(et) et.className = "panel-etica" + (TAB==="etica" ? " activo" : "");
  requestAnimationFrame(() => {
    (FIGS_TAB[TAB] || []).forEach(fid => { const el = $(fid); if(el && window.Plotly) Plotly.Plots.resize(el); });
  });
}

function setRol(r){
  ROL = r;
  document.querySelectorAll("#rol button").forEach(b => b.classList.toggle("activo", b.dataset.rol===r));
  const et = document.querySelector(".etica"); if(et) et.dataset.rol = r;
  if(r === "directora") TAB = "comunidad";
  updateRecomendaciones(filtered());
  applyTabs();
}
document.querySelectorAll("#rol button").forEach(b => b.addEventListener("click", () => setRol(b.dataset.rol)));
document.querySelectorAll("#tabs button").forEach(b => b.addEventListener("click", () => {
  document.querySelectorAll("#tabs button").forEach(x => x.classList.remove("activo"));
  b.classList.add("activo"); TAB = b.dataset.tab; applyTabs();
}));

document.querySelectorAll(".paso").forEach(p => p.addEventListener("click", () => {
  document.querySelectorAll(".paso").forEach(x => x.classList.remove("activo"));
  p.classList.add("activo");
  const tab = p.dataset.tab;
  document.querySelectorAll("#tabs button").forEach(b => b.classList.toggle("activo", b.dataset.tab === tab));
  TAB = tab; applyTabs();
  const card = $(p.dataset.card);
  if(card){
    card.classList.add("destacada");
    card.scrollIntoView({behavior:"smooth", block:"center"});
    setTimeout(() => card.classList.remove("destacada"), 2200);
  }
}));

function baseLayout(extra){
  return Object.assign({
    margin:{t:28,r:14,b:46,l:54},
    font:{family:"system-ui, Segoe UI, Roboto, Arial", size:12, color:"#334155"},
    paper_bgcolor:"#fff", plot_bgcolor:"#fff",
    xaxis:{gridcolor:"#eef2f7", zerolinecolor:"#e2e8f0", automargin:true},
    yaxis:{gridcolor:"#eef2f7", zerolinecolor:"#e2e8f0", automargin:true},
    showlegend:false, colorway:COLORS
  }, extra || {});
}
function valueCounts(a){ const m={}; a.forEach(v=>{m[v]=(m[v]||0)+1;}); return m; }
function fillMulti(id, values, labelFn){
  $(id).innerHTML = values.map(v => `<option value="${v}">${labelFn ? labelFn(v) : v}</option>`).join("");
}
function selected(id){ return [...$(id).selectedOptions].map(o => o.value); }

function initFilters(){
  fillMulti("f-jardin", uniq(NINOS.map(n=>n.jardin)).sort(), j => `${j} · ${JNOM[j]||""}`);
  fillMulti("f-region", uniq(NINOS.map(n=>n.region)).sort());
  fillMulti("f-tramo", TRAMOS);
  fillMulti("f-sala", uniq(NINOS.map(n=>n.sala)).sort());
  fillMulti("f-sexo", uniq(NINOS.map(n=>n.sexo)).sort());
  fillMulti("f-nivel", NIVELES, v => "Nivel "+v);
  $("f-emin").value = DATA.edadMin; $("f-emax").value = DATA.edadMax;
  $("f-emin").min = DATA.edadMin - 12; $("f-emax").max = DATA.edadMax + 12;
}

function filtered(){
  const jard = selected("f-jardin"), reg = selected("f-region"), tramo = selected("f-tramo"),
        sala = selected("f-sala"), sexo = selected("f-sexo"), niv = selected("f-nivel").map(Number),
        solo = $("f-alerta").checked, fmt = $("f-formato").value,
        emin = Number($("f-emin").value), emax = Number($("f-emax").value);
  const ninos = NINOS.filter(n =>
    (!jard.length || jard.includes(n.jardin)) &&
    (!reg.length || reg.includes(n.region)) &&
    (!tramo.length || tramo.includes(n.tramo)) &&
    (!sala.length || sala.includes(n.sala)) &&
    (!sexo.length || sexo.includes(n.sexo)) &&
    (!niv.length || niv.includes(n.nivelVigente)) &&
    (!solo || n.alerta) &&
    (n.edad>=emin && n.edad<=emax));
  const ids = new Set(ninos.map(n=>n.id));
  const obs = OBS.filter(o => ids.has(o.idNino) && (fmt==="todos" || o.formato===fmt));
  return {ninos, obs};
}

function dominiosPorNino(sel){
  const dc = {};
  sel.obs.forEach(o => { (dc[o.idNino] = dc[o.idNino] || new Set()); o.dominios.forEach(d => dc[o.idNino].add(d)); });
  return dc;
}

function drawTramo(sel){
  const y = TRAMOS.map(k => sel.ninos.filter(n=>n.tramo===k).length);
  Plotly.react("fig-tramo", [{type:"bar", x:TRAMOS, y:y, text:y.map(String), textposition:"outside",
    marker:{color:["#2563eb","#0891b2","#7c3aed","#d97706"]}}],
    baseLayout({yaxis:{title:"niños/as", gridcolor:"#eef2f7"}}), CFG);
}

function drawNivel(sel){
  const y = NIVELES.map(k => sel.ninos.filter(n=>n.nivelVigente===k).length);
  Plotly.react("fig-nivel", [{type:"bar", x:NIVELES, y:y, text:y.map(String), textposition:"outside",
    marker:{color:y, colorscale:"Blues", showscale:false}}],
    baseLayout({xaxis:{title:"nivel (1-9)", dtick:1, gridcolor:"#eef2f7"}, yaxis:{title:"niños/as", gridcolor:"#eef2f7"}}), CFG);
}

function drawEdad(sel){
  const by = {};
  sel.ninos.forEach(n => { (by[n.tramo] = by[n.tramo] || []).push(n); });
  const traces = TRAMOS.filter(t => by[t]).map((t,i) => ({
    type:"scatter", mode:"markers", name:t,
    x: by[t].map(n=>n.edad), y: by[t].map(n=>n.nivelVigente),
    text: by[t].map(n=>n.id),
    marker:{size:9, color:COLORS[i], opacity:.82, line:{width:1, color:"#fff"}},
    hovertemplate:"%{text}<br>Edad: %{x} meses<br>Nivel: %{y}<extra></extra>"
  }));
  Plotly.react("fig-edad", traces,
    baseLayout({showlegend:true, legend:{orientation:"h", y:-0.2, font:{size:10}},
      xaxis:{title:"edad (meses)", gridcolor:"#eef2f7"}, yaxis:{title:"nivel vigente", dtick:1, gridcolor:"#eef2f7"}}), CFG);
}

function drawBrecha(sel){
  const m = valueCounts(sel.ninos.map(n=>n.brecha).filter(v=>v!==null));
  const keys = Object.keys(m).map(Number).sort((a,b)=>a-b);
  Plotly.react("fig-brecha", [{type:"bar", x:keys, y:keys.map(k=>m[k]), marker:{color:"#2563eb"}}],
    baseLayout({xaxis:{title:"brecha (niveles)", dtick:1, gridcolor:"#eef2f7"}, yaxis:{title:"niños/as", gridcolor:"#eef2f7"},
      shapes:[{type:"line", x0:UMBRAL, x1:UMBRAL, y0:0, y1:1, yref:"paper", line:{color:"#dc2626", dash:"dash", width:2}}],
      annotations:[{x:UMBRAL, y:1, yref:"paper", text:"umbral "+UMBRAL, showarrow:false, yshift:8, font:{color:"#dc2626", size:10}}]}), CFG);
}

function drawBrechaSala(sel){
  const m = valueCounts(sel.ninos.map(n=>n.brechaSala).filter(v=>v!==null));
  const keys = Object.keys(m).map(Number).sort((a,b)=>a-b);
  Plotly.react("fig-bsala", [{type:"bar", x:keys, y:keys.map(k=>m[k]), marker:{color:"#7c3aed"}}],
    baseLayout({xaxis:{title:"brecha vs. mediana de la sala", gridcolor:"#eef2f7"}, yaxis:{title:"niños/as", gridcolor:"#eef2f7"},
      shapes:[{type:"line", x0:UMBRAL, x1:UMBRAL, y0:0, y1:1, yref:"paper", line:{color:"#dc2626", dash:"dash", width:2}}],
      annotations:[{x:UMBRAL, y:1, yref:"paper", text:"umbral "+UMBRAL, showarrow:false, yshift:8, font:{color:"#dc2626", size:10}}]}), CFG);
}

function drawAlertas(sel){
  const by = {};
  sel.ninos.forEach(n => { (by[n.jardin+" \u00b7 "+n.sala] = by[n.jardin+" \u00b7 "+n.sala] || []).push(n); });
  const rows = Object.entries(by).map(([g,ns]) => ({g:g, n:ns.length, a:ns.filter(x=>x.alerta).length}))
    .filter(r => r.a>0).sort((x,y)=>x.a-y.a).slice(-14);
  Plotly.react("fig-alertas", [{type:"bar", orientation:"h", x:rows.map(r=>r.a), y:rows.map(r=>r.g),
    text:rows.map(r=>r.a), textposition:"outside", marker:{color:rows.map(r=>r.a), colorscale:"OrRd", showscale:false},
    customdata:rows.map(r=>r.n), hovertemplate:"%{y}<br>%{x} de %{customdata} en alerta<extra></extra>"}],
    baseLayout({xaxis:{title:"niños/as en alerta", gridcolor:"#eef2f7"}, yaxis:{automargin:true, gridcolor:"#eef2f7"},
      margin:{t:20,r:30,b:46,l:150}}), CFG);
}

function drawDominios(sel){
  const dc = dominiosPorNino(sel);
  const y = [0,1,2,3,4,5].map(k => sel.ninos.filter(n => ((dc[n.id]&&dc[n.id].size)||0)===k).length);
  Plotly.react("fig-dominios", [{type:"bar", x:[0,1,2,3,4,5], y:y, text:y.map(String), textposition:"outside",
    marker:{color:"#059669"}}],
    baseLayout({xaxis:{title:"dominios con evidencia (0-5)", dtick:1, gridcolor:"#eef2f7"}, yaxis:{title:"niños/as", gridcolor:"#eef2f7"}}), CFG);
}

function drawFormato(sel){
  const m = valueCounts(sel.obs.map(o=>o.formato));
  const names = Object.keys(m);
  Plotly.react("fig-formato", [{type:"pie", labels:names, values:names.map(k=>m[k]), hole:.45,
    textinfo:"percent+label", marker:{colors:["#2563eb","#0891b2","#d97706","#7c3aed"]}}],
    baseLayout({margin:{t:10,r:10,b:10,l:10}, showlegend:false}), CFG);
}

function drawObsNino(sel){
  const m = valueCounts(sel.ninos.map(n=>n.nObs));
  const keys = Object.keys(m).map(Number).sort((a,b)=>a-b);
  Plotly.react("fig-obsnino", [{type:"bar", x:keys, y:keys.map(k=>m[k]), text:keys.map(k=>m[k]),
    textposition:"outside", marker:{color:"#2563eb"}}],
    baseLayout({xaxis:{title:"observaciones por niño/a", dtick:1, gridcolor:"#eef2f7"}, yaxis:{title:"niños/as", gridcolor:"#eef2f7"}}), CFG);
}

function drawTiempo(sel){
  const by = {};
  sel.obs.forEach(o => { by[o.mes] = (by[o.mes]||0)+1; });
  const months = Object.keys(by).sort();
  Plotly.react("fig-tiempo", [{type:"scatter", mode:"lines+markers", x:months, y:months.map(m=>by[m]),
    line:{color:"#0f766e", width:3}, marker:{size:7}}],
    baseLayout({xaxis:{title:"mes", gridcolor:"#eef2f7"}, yaxis:{title:"observaciones", gridcolor:"#eef2f7"}}), CFG);
}

function drawRegion(sel){
  const m = valueCounts(sel.ninos.map(n=>n.region));
  const ks = Object.keys(m).sort((a,b)=>m[a]-m[b]);
  Plotly.react("fig-region", [{type:"bar", orientation:"h", x:ks.map(k=>m[k]), y:ks,
    text:ks.map(k=>m[k]), textposition:"outside", marker:{color:"#0f766e"}}],
    baseLayout({xaxis:{title:"niños/as", gridcolor:"#eef2f7"}, yaxis:{automargin:true, gridcolor:"#eef2f7"}, margin:{t:16,r:30,b:46,l:140}}), CFG);
}

function drawHeat(sel){
  const z = NIVELES.map(lv => DOMS.map((d,di) => sel.obs.filter(o=>o.nivel===lv && o.dominios.includes(di)).length));
  Plotly.react("fig-heat", [{type:"heatmap", z:z, x:DOMS, y:NIVELES.map(String), colorscale:"Blues",
    text:z, texttemplate:"%{text}", showscale:false,
    hovertemplate:"Nivel %{y}<br>%{x}<br>%{z} evidencias<extra></extra>"}],
    baseLayout({margin:{t:10,r:10,b:120,l:46}, xaxis:{automargin:true, tickangle:-20}, yaxis:{title:"nivel", dtick:1, automargin:true}}), CFG);
}

function updateNinoOptions(sel){
  const el = $("f-nino"), prev = el.value;
  const ids = sel.ninos.map(n=>n.id).sort();
  el.innerHTML = ids.map(id => `<option value="${id}">${id}</option>`).join("");
  if(ids.includes(prev)) el.value = prev;
}

function drawTrayectoria(sel){
  const nid = $("f-nino").value;
  if(!nid){ Plotly.purge("fig-tray"); return; }
  const child = sel.obs.filter(o => o.idNino===nid);
  const cm = {};
  child.forEach(o => { (cm[o.mes] = cm[o.mes]||[]).push(o.nivel); });
  const cmon = Object.keys(cm).sort();
  const byMonth = {};
  sel.obs.forEach(o => { (byMonth[o.mes] = byMonth[o.mes]||[]).push(o.nivel); });
  const months = Object.keys(byMonth).sort();
  const traces = [
    {type:"scatter", mode:"lines+markers", name:"Promedio del grupo",
     x:months, y:months.map(m=>mean(byMonth[m])), line:{color:"#94a3b8", dash:"dash", width:2}, marker:{size:6}},
    {type:"scatter", mode:"lines+markers", name:nid,
     x:cmon, y:cmon.map(m=>mean(cm[m])), line:{color:"#2563eb", width:3}, marker:{size:10, line:{width:1,color:"#fff"}}}
  ];
  Plotly.react("fig-tray", traces,
    baseLayout({showlegend:true, legend:{orientation:"h", y:-0.25}, xaxis:{title:"mes", gridcolor:"#eef2f7"},
      yaxis:{title:"nivel", dtick:1, range:[0.5,9.5], gridcolor:"#eef2f7"}}), CFG);
}

function updateKpis(sel){
  const n = sel.ninos.length;
  $("k-ninos").textContent = n;
  $("k-obs").textContent = sel.obs.length;
  const nv = sel.ninos.map(x=>x.nivelVigente).filter(v=>v!==null);
  $("k-nivel").textContent = nv.length ? mean(nv).toFixed(1) : "\u2014";
  const al = sel.ninos.filter(x=>x.alerta).length;
  $("k-alertas").textContent = al + (n ? ` (${Math.round(100*al/n)}%)` : "");
  $("k-salas").textContent = uniq(sel.ninos.map(x=>x.jardin+"\u00b7"+x.sala)).length;
}

function updateRecomendaciones(sel){
  const box = $("reco");
  const n = sel.ninos.length;
  if(!n){ box.innerHTML = "<h3>Prioridades sugeridas para el plan</h3><p class='mini'>Sin niños/as con los filtros actuales. Ajusta los filtros.</p>"; return; }
  const alertas = sel.ninos.filter(x=>x.alerta);
  const by = {};
  alertas.forEach(x => { const k = x.jardin+" \u00b7 "+x.sala; by[k] = (by[k]||0)+1; });
  const top = Object.entries(by).sort((a,b)=>b[1]-a[1]).slice(0,5);
  const dc = dominiosPorNino(sel);
  const cov = DOMS.map((d,di) => ({d:d, pct: 100*sel.ninos.filter(x=>dc[x.id]&&dc[x.id].has(di)).length/n})).sort((a,b)=>a.pct-b.pct);
  const socio = DOMS.findIndex(d => /socio/i.test(d));
  const socioPct = socio>=0 ? Math.round(100*sel.ninos.filter(x=>dc[x.id]&&dc[x.id].has(socio)).length/n) : null;
  const pct = Math.round(100*alertas.length/n);
  const bPed = `<li><strong>Plan pedagógico:</strong> ${alertas.length} niños/as (${pct}%) están bajo el nivel de su grupo. ` +
    `Reforzar primero los dominios con menos evidencia: <em>${cov.slice(0,2).map(c=>c.d).join(" y ")}</em>.</li>`;
  const bCom = `<li><strong>Plan comunitario:</strong> ` +
    (top.length ? `coordinar con las familias de las salas ${top.map(t=>t[0]).join(", ")} y acordar evidencias a compartir.` : "sin salas críticas con los filtros actuales.") +
    `</li>`;
  const bSoc = `<li><strong>Plan social y convivencia:</strong> ` +
    (socioPct===null ? "sin datos de dominio socioemocional." :
      `cobertura socioemocional del ${socioPct}%${socioPct<60 ? " \u2192 priorizar observaciones de este dominio." : "."}`) +
    `</li>`;
  const orden = ROL==="directora" ? [bCom,bPed,bSoc] : ROL==="equipo" ? [bPed,bSoc,bCom] : [bPed,bCom,bSoc];
  const foco = {parvularia:"Mirada de sala: qué hacer esta semana con tu grupo.",
                directora:"Mirada de jardín: dónde reforzar el apoyo a los equipos.",
                equipo:"Mirada de red: comparar, priorizar y escalar recursos."}[ROL] || "";
  let h = `<h3>Prioridades sugeridas para el plan</h3><p class="mini">${foco}</p><ul>`;
  h += orden.join("");
  h += `</ul>`;
  if(top.length) h += `<p class="mini">Salas a priorizar: ${top.map(t=>`${t[0]} (${t[1]})`).join(" \u00b7 ")}</p>`;
  h += `<p class="mini">Sugerencias automáticas: la educadora tiene siempre la decisión final.</p>`;
  box.innerHTML = h;
}

function render(){
  const sel = filtered();
  $("resumen-filtros").textContent = `${sel.ninos.length} niños/as y ${sel.obs.length} observaciones en la vista.`;
  updateKpis(sel);
  updateNinoOptions(sel);
  drawTramo(sel); drawNivel(sel); drawEdad(sel); drawBrechaSala(sel);
  drawAlertas(sel); drawDominios(sel); drawFormato(sel);
  drawTiempo(sel); drawHeat(sel); drawTrayectoria(sel);
  updateRecomendaciones(sel);
  applyTabs();
}

function limpiar(){
  ["f-jardin","f-region","f-tramo","f-sala","f-sexo","f-nivel"].forEach(id => { $(id).selectedIndex = -1; });
  $("f-formato").value = "todos"; $("f-alerta").checked = false;
  $("f-emin").value = DATA.edadMin; $("f-emax").value = DATA.edadMax;
  render();
}

let _t = null;
function schedule(){ clearTimeout(_t); _t = setTimeout(render, 120); }
["f-jardin","f-region","f-tramo","f-sala","f-sexo","f-nivel","f-formato","f-alerta","f-emin","f-emax"]
  .forEach(id => { const el = $(id); el.addEventListener("input", schedule); el.addEventListener("change", schedule); });
$("f-nino").addEventListener("change", () => drawTrayectoria(filtered()));
$("btn-limpiar").addEventListener("click", limpiar);

initFilters();
render();
"""


def render_interactivo(payload: dict, salida: Path) -> Path:
    html = (
        PLANTILLA_DASH.replace("__CSS__", CSS_DASH)
        .replace("__GENERADO__", payload["generado"])
        .replace("__DATA__", "window.__PAYLOAD__ = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";")
        .replace("__APP__", APP_JS)
    )
    salida.write_text(html, encoding="utf-8")
    return salida


def generar_dashboard(salida=None, datos_dir=None, abrir: bool = False,
                     usar_backend: bool = True, estatico: bool = False) -> Path:
    """Genera el panel. API reutilizable por las etapas del proyecto (app, cron)."""
    destino = Path(salida) if salida else RAIZ / "dashboard" / "visualizacion_datos.html"
    datos = cargar(usar_backend=usar_backend, datos_dir=datos_dir)
    feats = construir_features(datos)
    calidad, checks = resumen_calidad(datos)
    if estatico:
        jardines_feats = features_jardin(feats, datos["jardines"])
        graficos = construir_graficos(datos, feats)
        destino = render(datos, feats, jardines_feats, calidad, checks, graficos, destino)
    else:
        payload = construir_payload(datos, feats, cargar_dominios(datos_dir))
        destino = render_interactivo(payload, destino)
    imprimir_resumen(feats, calidad, checks, destino)
    if abrir:
        webbrowser.open(destino.resolve().as_uri())
    return destino


def main() -> int:
    parser = argparse.ArgumentParser(description="Dashboard / reporte de los datos sintéticos.")
    parser.add_argument("--salida", default=str(RAIZ / "dashboard" / "visualizacion_datos.html"))
    parser.add_argument("--abrir", action="store_true", help="Abrir el HTML en el navegador")
    parser.add_argument("--estatico", action="store_true", help="Generar el reporte estático con plotly.express")
    parser.add_argument("--datos", default=None, help="Carpeta de datos (por defecto: backend/dataset)")
    parser.add_argument("--csv", action="store_true", help="Forzar lectura desde CSV (ignorar el backend SQLite)")
    args = parser.parse_args()

    generar_dashboard(salida=args.salida, datos_dir=args.datos, abrir=args.abrir,
                      usar_backend=not args.csv, estatico=args.estatico)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
