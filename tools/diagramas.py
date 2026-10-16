"""Genera los diagramas de gobierno de datos e infraestructura TI (docs/img/*.png).

    python tools/diagramas.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent.parent / "docs" / "img"
OUT.mkdir(parents=True, exist_ok=True)

TINTA = "#1F2A44"; GRIS = "#4A5568"; FONDO = "#FAF7F2"; BORDE = "#C9CFD8"; VERDE = "#3D7D5A"
CLASE = {"S": ("#B5541A", "S · Sensible (menores)"), "C": ("#2F6DB5", "C · Confidencial"),
         "I": ("#3D7D5A", "I · Interno"), "P": ("#7A7F87", "P · Público")}
DUENO = {"Ivan": "#6B4FA0", "Sebastián": "#2F6DB5", "Santiago": "#3D7D5A", "Mauricio": "#B5541A",
         "Integra": "#1F2A44", "Meta": "#7A7F87", "AWS": "#7A7F87"}
plt.rcParams["font.family"] = "DejaVu Sans"


def lienzo(titulo: str, sub: str):
    fig, ax = plt.subplots(figsize=(18, 10), dpi=150)
    fig.patch.set_facecolor(FONDO); ax.set_facecolor(FONDO)
    ax.set_xlim(0, 180); ax.set_ylim(0, 100); ax.axis("off")
    ax.text(3, 96, titulo, fontsize=22, fontweight="bold", color=TINTA, va="top")
    ax.text(3, 91.5, sub, fontsize=12, color=GRIS, va="top")
    return fig, ax


def caja(ax, x, y, w, h, titulo, lineas=(), clase=None, dueno=None, borde=BORDE, relleno="#FFFFFF", alerta=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.5",
                                fc=relleno, ec="#B5541A" if alerta else borde, lw=2.2 if alerta or borde != BORDE else 1.2))
    ax.text(x + 1.2, y + h - 1.4, titulo, fontsize=11, fontweight="bold", color=TINTA, va="top")
    for i, l in enumerate(lineas):
        ax.text(x + 1.2, y + h - 5.0 - i * 3.1, l, fontsize=8.8, color=GRIS, va="top")
    if clase:
        c, _ = CLASE[clase]
        ax.add_patch(FancyBboxPatch((x + 1.0, y + 0.6), 3.4, 2.8, boxstyle="round,pad=0.1,rounding_size=0.6", fc=c, ec=c))
        ax.text(x + 2.7, y + 2.0, clase, fontsize=9.5, fontweight="bold", color="white", ha="center", va="center")
    if dueno:
        ax.text(x + w - 0.6, y + 0.6, dueno, fontsize=8, color="white", ha="right", va="bottom", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.25", fc=DUENO.get(dueno, GRIS), ec="none"))


def flecha(ax, a, b, texto="", color=GRIS, estilo="-|>", rad=0.0, dash=False):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=estilo, mutation_scale=14, color=color, lw=1.6,
                                 connectionstyle=f"arc3,rad={rad}", linestyle="--" if dash else "-"))
    if texto:
        ax.text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 1.4, texto, fontsize=8, color=color, ha="center",
                bbox=dict(boxstyle="round,pad=0.15", fc=FONDO, ec="none"))


def leyenda_clases(ax, x, y):
    ax.text(x, y + 3.2, "Clasificación del dato", fontsize=10, fontweight="bold", color=TINTA)
    for i, (k, (c, nombre)) in enumerate(CLASE.items()):
        ax.add_patch(FancyBboxPatch((x + i * 30, y - 1), 2.8, 2.6, boxstyle="round,pad=0.1,rounding_size=0.5", fc=c, ec=c))
        ax.text(x + i * 30 + 4, y + 0.3, nombre, fontsize=9.5, color=TINTA, va="center")


def infra_datos():
    fig, ax = lienzo("Gobierno de datos · flujo de una observación",
                     "Arquitectura final (16-oct-2026) · Responsable: Fundación Integra (DPD) · "
                     "Encargados con DPA: Meta, AWS, operador del webhook · Ley 21.719, 21.430")
    W, H = 30, 21
    xs = [3, 39, 75, 111, 147]
    # Fila 1 (izq. → der.): de la observación a las conductas
    y1 = 63
    fila1 = [("1 · Observación", ["la tía escribe por WhatsApp", "nombre o apodo del niño/a",
                                  "botones si el nombre se repite"], "S", "Integra"),
             ("2 · Medio recibido", ["texto · imagen (post-it)", "audio (nota de voz) · video",
                                     "magic bytes, ≤ 16 MB"], "S", "Sebastián"),
             ("3 · Transcripción", ["post-it: Claude Sonnet 5", "audio: faster-whisper (CPU)",
                                    "video: Pegasus (TwelveLabs)"], "S", "Mauricio"),
             ("4 · Controles de ingesta", ["PII redactada", "detector de inyección → cola",
                                           "escáner de secretos (salidas)"], "S", "Mauricio"),
             ("5 · Conductas con cita", ["conductas observables", "cada una con cita literal",
                                         "sin nombres → se guarda en BD"], "C", "Mauricio")]
    for x, (t, l, c, d) in zip(xs, fila1):
        caja(ax, x, y1, W, H, t, l, c, d)
    for i in range(4):
        flecha(ax, (xs[i] + W + 0.6, y1 + H / 2), (xs[i + 1] - 0.6, y1 + H / 2))
    # Fila 2 (der. → izq.): del tramo por edad a la decisión de la educadora
    y2 = 36
    rx = list(reversed(xs))
    fila2 = [("6 · Tramo por edad", ["edad al 31 de marzo:", "Sala Cuna · Nivel Medio", "· Transición"], "C", "Sebastián"),
             ("7 · Juez de la rúbrica", ["rúbrica Integra: Identidad y", "Autonomía, 3 tramos × 8 niveles",
                                         "Claude Sonnet 5 + evidencia"], "C", "Sebastián"),
             ("8 · Compuerta", ["confianza del juez", "alertas: rezago, inyección,", "medio dudoso"], "C", "Sebastián"),
             ("9 · Auto o \"Por verificar\"", ["alta confianza → automático", "duda o alerta → cola en vivo",
                                               "de la profesora (SSE)"], "C", "Sebastián"),
             ("10 · Educadora decide", ["\"Confirma a Nombre I.\"", "confirma o corrige el nivel",
                                        "revisión humana (art. 8 bis)"], "S", "Integra")]
    for x, (t, l, c, d) in zip(rx, fila2):
        caja(ax, x, y2, W, H, t, l, c, d)
    for i in range(4):
        flecha(ax, (rx[i] - 0.6, y2 + H / 2), (rx[i + 1] + W + 0.6, y2 + H / 2))
    flecha(ax, (147 + W / 2, y1 - 0.6), (147 + W / 2, y2 + H + 0.6))
    ax.text(147 + W / 2 + 1.2, (y1 + y2 + H) / 2, "texto sin nombres", fontsize=8.5, color=GRIS, va="center")
    # Fila 3 (izq. → der.): del nivel oficial al dashboard
    y3 = 9
    fila3 = [("11 · Nivel oficial", ["nivel confirmado + evidencia", "trayectoria del niño/a",
                                     "seudónimo NINO-xxxxx"], "S", "Integra"),
             ("12 · Recomendador RAG", ["corpus OMS · CDC · MINEDUC", "hitos motores OMS (bebés) ·",
                                        "Identidad y Autonomía (2-6)"], "C", "Mauricio"),
             ("13 · Revisión profesora", ["recomendaciones con cita", "\"Por verificar\": aprobar,",
                                                "editar o descartar"], "C", "Integra"),
             ("14 · Dashboard", ["ficha: nivel, brecha, trayectoria", "y recomendaciones aprobadas",
                                 "coordinación: métricas por jardín"], "I", "Santiago")]
    for x, (t, l, c, d) in zip(xs, fila3):
        caja(ax, x, y3, W, H, t, l, c, d)
    flecha(ax, (3 + W / 2, y2 - 0.6), (3 + W / 2, y3 + H + 0.6))
    for i in range(3):
        flecha(ax, (xs[i] + W + 0.6, y3 + H / 2), (xs[i + 1] - 0.6, y3 + H / 2))
    caja(ax, 147, 3.5, W, 26.5, "Se guarda · se borra",
         ["✗ medio crudo (foto, audio, video):", "    se borra al procesar (≤ 24 h)", "✗ nombres: no llegan a la BD",
          "✓ solo conductas sin nombres", "✓ nivel, evidencia, quién confirmó", "✓ datos de la demo: sintéticos"],
         borde=VERDE, dueno="Integra")
    leyenda_clases(ax, 3, 2.5)
    fig.savefig(OUT / "infra_datos.png", bbox_inches="tight", facecolor=FONDO); plt.close(fig)


def infra_ti():
    fig, ax = lienzo("Infraestructura TI · arquitectura desplegada",
                     "Estado al 16-oct-2026 · cuenta AWS del evento, us-east-1 · etiqueta = responsable · "
                     "todos los datos de la demo son sintéticos")
    # --- Columna 1: usuarios y entrada por WhatsApp ---
    caja(ax, 3, 64, 32, 22, "Educadora (tía)", ["WhatsApp: texto, post-it, voz, video",
                                                 "vista de profesora: casos por",
                                                 "confirmar (\"Confirma a Nombre I.\")",
                                                 "y recomendaciones a revisar"], clase="S", dueno="Integra")
    caja(ax, 3, 43, 32, 17, "WhatsApp Cloud API", ["texto · foto de post-it", "nota de voz · video",
                                                   "botones: niños con igual nombre"], clase="S", dueno="Meta")
    caja(ax, 3, 25, 32, 14, "Webhook HTTPS", ["firma HMAC fail-closed + whitelist", "→ CloudFront /procesar*"],
         dueno="Sebastián")
    caja(ax, 3, 4, 32, 17, "Ficha y coordinación", ["ficha: nivel oficial, trayectoria", "y recomendaciones aprobadas",
                                                    "coordinación: métricas por jardín"], clase="I", dueno="Santiago")
    flecha(ax, (19, 63.4), (19, 60.6))
    flecha(ax, (19, 42.4), (19, 39.6))
    # --- Columna 2: CloudFront, S3 y GitHub Pages ---
    caja(ax, 40, 41, 30, 45, "CloudFront (HTTPS)", ["TLS + HSTS · sin caché", "",
                                                    "/  → React (S3 privado)", "/streamlit* → Streamlit :80",
                                                    "/api/* · /procesar*", "/clasificar · /health",
                                                    "     → API FastAPI :8000"], dueno="Ivan")
    caja(ax, 40, 22, 30, 15, "S3 frontend (privado)", ["React · acceso solo por OAC", "Block Public Access"],
         clase="P", dueno="Santiago")
    caja(ax, 40, 3, 30, 15, "GitHub Pages", ["demo pública secundaria", "datos sintéticos (CSV)"],
         clase="P", dueno="Mauricio")
    flecha(ax, (55, 40.4), (55, 37.6))
    flecha(ax, (35.6, 76), (39.4, 76), "web")
    flecha(ax, (35.6, 32), (39.4, 46))
    flecha(ax, (35.6, 14), (39.4, 43))
    # --- Columna 3: EC2 integra-server ---
    ax.add_patch(FancyBboxPatch((75, 29), 50, 57, boxstyle="round,pad=0.4,rounding_size=2", fc="#EEF1F6",
                                ec="#9AA8BF", lw=1.2, ls="--"))
    ax.text(76.5, 85.2, "EC2 integra-server · admin por SSM (sin SSH)", fontsize=10.5, fontweight="bold",
            color=TINTA, va="top")
    caja(ax, 77, 57, 46, 24, "webhook_ec2.py · FastAPI :8000", ["resolución del niño/a en la sala de la tía",
                                                                "U2 multimodal → conductas con cita",
                                                                "juez de la rúbrica · compuerta",
                                                                "cola \"Por verificar\" en vivo (SSE)",
                                                                "API con token X-Api-Key"], dueno="Sebastián")
    caja(ax, 77, 41, 22, 13, "Streamlit :80", ["dashboard operativo"], dueno="Santiago")
    caja(ax, 101, 41, 22, 13, "faster-whisper", ["audio en CPU · ffmpeg"], dueno="Mauricio")
    caja(ax, 77, 30.5, 46, 8, "BD de la plataforma (SQLite)", ["conductas sin nombres · niveles · cola"])
    flecha(ax, (70.6, 70), (76.4, 70), ":8000")
    flecha(ax, (70.6, 47), (76.4, 47), ":80")
    flecha(ax, (112, 56.4), (112, 54.6))
    # --- Recomendador RAG (lote) ---
    caja(ax, 75, 3, 50, 22, "Recomendador RAG (lote)", ["corpus OMS · CDC · MINEDUC (Bases Curriculares)",
                                                        "→ índice léxico → análisis determinístico:",
                                                        "   hitos OMS (bebés) · Identidad y Autonomía (2-6)",
                                                        "→ citas → recomendaciones.json → \"Por verificar\""],
         dueno="Mauricio")
    flecha(ax, (100, 25.6), (100, 28.4), dash=True)
    # --- Columna 4: Bedrock, seguridad y gobierno ---
    caja(ax, 130, 60, 47, 26, "Amazon Bedrock", ["Claude Sonnet 5: post-it, conductas y juez",
                                                 "Pegasus (TwelveLabs): video",
                                                 "Titan Embeddings: búsqueda del RAG",
                                                 "Claude Opus 5: juez DeepEval (offline)",
                                                 "sin logging de invocación"], dueno="AWS")
    caja(ax, 130, 26, 47, 30, "Seguridad", ["Secrets Manager: integrai/api-token",
                                            "IMDSv2 obligatorio · admin por SSM",
                                            "redacción de PII antes del modelo",
                                            "inyección (\"dame todas las keys\") → cola",
                                            "escáner de secretos en las salidas",
                                            "medios: magic bytes; se borran al procesar"], dueno="Mauricio")
    caja(ax, 130, 3, 47, 19, "Gobierno de datos", ["medios crudos ≤ 24 h · BD sin nombres",
                                                   "la educadora confirma (art. 8 bis)",
                                                   "repo público sin IDs ni secretos"], dueno="Integra")
    flecha(ax, (125.6, 72), (129.4, 72))
    fig.savefig(OUT / "infra_ti.png", bbox_inches="tight", facecolor=FONDO); plt.close(fig)


if __name__ == "__main__":
    infra_datos(); infra_ti()
    print("ok:", OUT)
