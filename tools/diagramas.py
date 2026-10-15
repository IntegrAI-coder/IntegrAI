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

TINTA = "#1F2A44"; GRIS = "#4A5568"; FONDO = "#FAF7F2"; BORDE = "#C9CFD8"
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
                                fc=relleno, ec="#B5541A" if alerta else borde, lw=2.2 if alerta else 1.2))
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
                     "Responsable: Fundación Integra (DPD) · Encargados con DPA: Meta, AWS, equipo IntegrAI · Ley 21.719, 21.430")
    W, H = 25, 20
    fila1 = [(3, "Tía · WhatsApp", ["texto, post-it, voz, video", "código o apodo del niño/a", "nunca RUT"], "S", "Integra"),
             (32, "Meta Cloud API", ["encargado (DPA)", "medio disponible por", "tiempo limitado"], "S", "Meta"),
             (61, "Webhook", ["firma X-Hub-Signature-256", "whitelist de teléfonos", "desconocido = descartado"], None, "Sebastián"),
             (90, "Medios temporales", ["S3 cifrado (KMS)", "borrado ≤ 24 h", "nunca en el repo"], "S", "Ivan"),
             (119, "U2 · Ingesta", ["lectura fiel + conductas", "nombre → ID, no sale", "magic bytes, ≤ 16 MB"], "S", "Mauricio"),
             (148, "Bedrock (us-east-1)", ["encargado, sin entrenar", "transferencia: cláusulas", "tipo (arts. 27-28)"], "S", "AWS")]
    y1 = 60
    for x, t, l, c, d in fila1:
        caja(ax, x, y1, W, H, t, l, c, d)
    for i in range(len(fila1) - 1):
        flecha(ax, (fila1[i][0] + W + 0.6, y1 + H / 2), (fila1[i + 1][0] - 0.6, y1 + H / 2))
    fila2 = [(148, "Ensemble", ["matcher + Laya", "propone nivel + evidencia", "registra versión de modelo"], "C", "Sebastián"),
             (119, "Revisión de la tía", ["humano en el loop", "art. 8 bis: explica y", "permite corregir"], "C", "Integra"),
             (90, "BD observaciones", ["seudónimo NINO-xxxxx", "matrícula + 1 año", "cifrada, con backup"], "C", "Ivan"),
             (61, "Dashboard (RBAC)", ["educadora: su sala", "directora: su jardín", "login + TLS"], "C", "Santiago"),
             (32, "Agregados anónimos", ["por jardín / región", "sin datos individuales", "k-anonimato ≥ 5"], "I", "Integra"),
             (3, "Datos sintéticos", ["dataset E-1, benchmarks", "únicos en el repo", "público"], "P", "Mauricio")]
    y2 = 28
    for x, t, l, c, d in fila2:
        caja(ax, x, y2, W, H, t, l, c, d)
    flecha(ax, (148 + W / 2, y1 - 0.6), (148 + W / 2, y2 + H + 0.6), "texto sin nombres")
    for i in range(len(fila2) - 2):
        flecha(ax, (fila2[i][0] - 0.6, y2 + H / 2), (fila2[i + 1][0] + W + 0.6, y2 + H / 2))
    caja(ax, 61, 6, 54, 14, "Auditoría y derechos", ["log de cada acceso y decisión (2 años, sin PII) · canal ARCO+ (30 días)",
                                                     "brecha: Agencia sin dilación + apoderados · CSIRT 3 h / 72 h (buena práctica)"], None, "Mauricio")
    flecha(ax, (90 + W / 2, y2 - 0.6), (95, 20.6), dash=True)
    leyenda_clases(ax, 3, 2.5)
    fig.savefig(OUT / "infra_datos.png", bbox_inches="tight", facecolor=FONDO); plt.close(fig)


def infra_ti():
    fig, ax = lienzo("Infraestructura TI · hoy vs. objetivo",
                     "Etiqueta = responsable · borde naranjo = riesgo actual · cuenta AWS del evento, us-east-1")
    # --- HOY ---
    ax.text(3, 85, "HOY", fontsize=15, fontweight="bold", color="#B5541A")
    caja(ax, 3, 66, 22, 14, "Internet", ["cualquiera", "sin autenticación"], alerta=True)
    caja(ax, 3, 46, 22, 14, "WhatsApp (Meta)", ["webhook sin validar", "firma ni teléfono"], alerta=True, dueno="Sebastián")
    caja(ax, 33, 46, 30, 34, "EC2 integra-server", ["IP pública, HTTP :80 y :8000", "API /procesar /clasificar", "sin token · Swagger público",
                                                    "/health expone el roster", "Streamlit sin login", "SQLite + Laya + Whisper",
                                                    "llaves STS del evento"], alerta=True, dueno="Sebastián")
    caja(ax, 33, 28, 30, 13, "Bedrock", ["Sonnet 5 · Nova · Titan", "sin logging de invocación"], dueno="AWS")
    caja(ax, 3, 25, 22, 16, "Repo público", ["datos sintéticos", "IP redactada (PR seguridad)"], clase="P", dueno="Mauricio")
    flecha(ax, (25.6, 73), (32.4, 70), "HTTP", color="#B5541A")
    flecha(ax, (25.6, 53), (32.4, 53), "HTTP", color="#B5541A")
    flecha(ax, (48, 45.4), (48, 41.6))
    ax.plot([72, 72], [5, 88], color=BORDE, lw=1.5, ls="--")
    # --- OBJETIVO ---
    ax.text(78, 85, "OBJETIVO", fontsize=15, fontweight="bold", color="#3D7D5A")
    caja(ax, 78, 66, 20, 15, "Tías / directoras", ["login Cognito (MFA)", "RBAC por sala/jardín"], dueno="Santiago")
    caja(ax, 78, 47, 20, 15, "WhatsApp", ["firma HMAC +", "whitelist teléfonos"], dueno="Sebastián")
    caja(ax, 104, 58, 22, 22, "CloudFront + WAF", ["TLS (ACM)", "reglas administradas", "rate limit", "sin /docs ni /openapi"], dueno="Ivan")
    ax.add_patch(FancyBboxPatch((131, 22), 46, 60, boxstyle="round,pad=0.4,rounding_size=2", fc="#EEF1F6", ec="#9AA8BF", lw=1.2, ls="--"))
    ax.text(132.5, 80.5, "VPC · subred privada", fontsize=10, fontweight="bold", color=GRIS, va="top")
    caja(ax, 134, 56, 40, 20, "EC2 (sin IP pública)", ["SG: solo desde CloudFront", "IMDSv2 · SSM (sin SSH)", "EBS cifrado (KMS)",
                                                       "API con token · U2 · ensemble"], dueno="Ivan")
    caja(ax, 134, 38, 19, 14, "S3 medios", ["KMS · lifecycle 24 h", "Block Public Access"], clase="S", dueno="Ivan")
    caja(ax, 155, 38, 19, 14, "BD y backups", ["cifrada (KMS)", "seudónimos"], clase="C", dueno="Ivan")
    caja(ax, 134, 24, 40, 11, "VPC endpoint → Bedrock", ["tráfico privado · logging cifrado o desactivado"], dueno="Mauricio")
    caja(ax, 78, 21, 48, 23, "Seguridad y operación", ["Secrets Manager: token Meta, app secret", "CloudTrail + GuardDuty + Security Hub",
                                                       "CloudWatch: logs sin PII, alarmas", "AWS Budgets: tope de gasto Bedrock",
                                                       "IAM mínimo privilegio · Access Analyzer"], dueno="Ivan")
    caja(ax, 78, 3, 99, 15, "Gobierno (Integra)", ["DPD · EIPD (art. 15 ter) · DPA con AWS y Meta · consentimiento de apoderados (art. 16 quáter)", "canal ARCO+ (30 días) · respuesta a incidentes · revisión anual de riesgos"],
         dueno="Mauricio")
    flecha(ax, (98.6, 74), (103.4, 72), "")
    flecha(ax, (98.6, 55), (103.4, 62), "")
    ax.text(101, 76.5, "HTTPS", fontsize=8, color=GRIS, ha="center")
    flecha(ax, (126.6, 69), (133.4, 66), "")
    ax.text(129.5, 61.5, "origen\nprivado", fontsize=8, color=GRIS, ha="center")
    flecha(ax, (154, 55.4), (154, 52.6))
    flecha(ax, (150, 37.4), (150, 35.6))
    fig.savefig(OUT / "infra_ti.png", bbox_inches="tight", facecolor=FONDO); plt.close(fig)


if __name__ == "__main__":
    infra_datos(); infra_ti()
    print("ok:", OUT)
