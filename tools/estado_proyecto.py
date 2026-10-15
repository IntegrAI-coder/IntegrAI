"""Dashboard de equipo del estado del proyecto (cumplimiento del objetivo).

Genera `estado_proyecto.html`: un tablero para el equipo que resume el objetivo
del desafío, el avance por área/persona (según lo entregado en el repo), las
métricas resultantes del modelo y de la compuerta, el estado de seguridad y el
estado del repositorio.

Uso:
    python tools/estado_proyecto.py              # genera el HTML
    python tools/estado_proyecto.py --abrir      # y lo abre en el navegador
    python tools/estado_proyecto.py --sin-tests  # no ejecuta pytest (más rápido)

Lee del propio repositorio (archivos, git) y de las métricas ya publicadas en
`docs/EVAL_ENSEMBLE.md` y `docs/METRICAS_GATE.md` (fijadas aquí como snapshot).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import webbrowser
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "estado_proyecto.html"
REMOTO = "https://github.com/IntegrAI-coder/IntegrAI"


# --------------------------------------------------------------------------- #
# Datos del proyecto (objetivo, áreas y entregables)
# --------------------------------------------------------------------------- #

OBJETIVO = {
    "titulo": "Convertir una observación de WhatsApp en un nivel con evidencia",
    "detalle": (
        "La educadora envía texto, foto de post-it, nota de voz o video; el sistema "
        "propone un nivel con evidencia del catálogo y ella Confirma / Ajusta / Cancela. "
        "Solo su confirmación cambia el nivel del niño/a."
    ),
    "kpi": "Bajar el tiempo de documentación de 4 h/semana a casi 0",
    "estado": "Prototipo funcional desplegado en integra-server · falta congelar código, activar seguridad F0 y demostrar el E2E en teléfonos reales",
}

# (etiqueta, ruta_o_None, estado_manual_o_None, nota)
AREAS = [
    {
        "area": "Infraestructura AWS",
        "owner": "Ivan",
        "rama": "Ivan",
        "items": [
            ("Plan de infraestructura (doc)", "docs/INFRA.md", None, ""),
            ("Plantilla CloudFormation", "infra/integra-server.yaml", None, ""),
            ("README de infra", "infra/README.md", None, ""),
            ("Secretos en Secrets Manager", "tools/secrets_aws.py", None, ""),
            ("IAM mínimo (rol EC2)", "tools/iam_aws.py", None, ""),
            ("Cifrado EBS (plan + migración)", "tools/ebs_aws.py", None, ""),
            ("CloudFront TLS + WAF como código", "tools/cloudfront_aws.py", None, ""),
            ("Observabilidad (CloudTrail/GuardDuty/Config)", "tools/observabilidad_aws.py", None, ""),
            ("KMS + S3 (BPA, lifecycle 24 h)", "tools/kms_s3_aws.py", None, ""),
            ("Bedrock por VPC endpoint", "tools/bedrock_aws.py", None, ""),
            ("Budgets (alerta de gasto)", "tools/budgets_aws.py", None, ""),
            ("Auditoría de región", "tools/region_audit.py", None, ""),
            ("CloudWatch logs y alarmas", "tools/cloudwatch_aws.py", None, ""),
            ("Respaldos", "tools/backup_aws.py", None, ""),
            ("Endurecer servicios EC2", "tools/endurecer_servicios_ec2.sh", None, ""),
            ("Desplegar seguridad en EC2", "tools/desplegar_seguridad_ec2.sh", None, ""),
            ("Cerrar 80/8000 (solo CloudFront)", "tools/seguridad_aws.py", None, ""),
            ("CI de seguridad (deps + escaneo)", ".github/workflows/seguridad.yml", None, ""),
            ("Dashboard de datos", "dashboard/visualizar_datos.py", None, "Movido a dashboard/"),
            ("CloudFront TLS aplicado en AWS", None, "hecho", "Verificado en la cuenta"),
            ("IMDSv2 obligatorio aplicado", None, "hecho", "Verificado en la instancia"),
            ("Cifrado EBS por defecto aplicado", None, "hecho", "Verificado en la cuenta"),
            ("Activar token API + cerrar SG", None, "pendiente", "Corte coordinado con Sebastián"),
            ("Observabilidad/KMS/S3/Budgets aplicados", None, "pendiente", "Entregado en repo, sin ejecutar"),
        ],
    },
    {
        "area": "WhatsApp + clasificador",
        "owner": "Sebastián",
        "rama": "whatsapp-clasificador",
        "items": [
            ("Webhook (firma, whitelist)", "webhook/server.py", None, ""),
            ("API EC2 (/procesar, /clasificar)", "webhook_ec2.py", None, ""),
            ("Resolver niño/a por nombre", "src/resolver.py", None, ""),
            ("Clasificador", "src/clasificador.py", None, ""),
            ("Compuerta por margen", "src/compuerta.py", None, ""),
            ("Ensemble (híbrido + Laya)", "src/modelo_decision.py", None, ""),
            ("U2 multimodal delante del ensemble", "src/multimodal/__init__.py", None, ""),
            ("Arquitectura de decisión (doc)", "docs/ARQUITECTURA_DECISION.md", None, ""),
            ("Resolver + cron (doc)", "docs/ARQUITECTURA_RESOLVER_Y_CRON.md", None, ""),
            ("Bench contra la edad", "bench/casos_contra_edad.jsonl", None, ""),
            ("Código del servidor en el repo", "webhook/server.py", None, "Presente en el repo"),
        ],
    },
    {
        "area": "Frontend",
        "owner": "Santiago",
        "rama": "frontend",
        "items": [
            ("App React + Vite", "frontend/src/App.tsx", None, ""),
            ("Página de cursos", "frontend/src/pages/Cursos.tsx", None, ""),
            ("Ficha del niño/a", "frontend/src/pages/Nino.tsx", None, ""),
            ("Gráficos de consulta", "frontend/src/components/GraficoDistribucion.tsx", None, ""),
            ("Tests de dominio", "frontend/src/domain/consultas.test.ts", None, ""),
            ("Transcripción/conductas/advertencias en ficha", None, "en curso", "Pendiente según PLAN"),
            ("Marcar 'pendiente de revisión' de la compuerta", None, "pendiente", "Pendiente"),
            ("PR del frontend a main", None, "pendiente", "Falta PR a main"),
        ],
    },
    {
        "area": "Modelo multimodal U2 + seguridad",
        "owner": "Mauricio",
        "rama": "u2-eval-despliegue",
        "items": [
            ("U2 multimodal (audio/imagen/video)", "src/multimodal/video.py", None, ""),
            ("Nota → conductas", "src/multimodal/conductas.py", None, ""),
            ("Evaluación del ensemble (doc)", "docs/EVAL_ENSEMBLE.md", None, ""),
            ("Métricas de la compuerta (doc)", "docs/METRICAS_GATE.md", None, ""),
            ("Gobierno de datos y marco legal", "docs/GOBIERNO_DATOS.md", None, ""),
            ("Checklist de seguridad (doc)", "docs/SEGURIDAD.md", None, ""),
            ("Tests de seguridad", "tests/test_seguridad.py", None, ""),
            ("Cerrar puertos 22/8000/8501", None, "pendiente", "Requiere corte coordinado"),
            ("Autenticación de la API y del dashboard", None, "en curso", "F0/F1"),
        ],
    },
    {
        "area": "Entrega, datos y tableros",
        "owner": "Equipo",
        "rama": "main",
        "items": [
            ("Dataset sintético (7 CSV)", "data/ninos.csv", None, ""),
            ("Diccionario de datos", "docs/diccionario_datos.md", None, ""),
            ("Plan de equipo", "docs/PLAN.md", None, ""),
            ("Resumen del deck", "docs/resumen_deck.md", None, ""),
            ("Dashboard de datos", "dashboard/visualizar_datos.py", None, ""),
            ("Dashboard de estado del proyecto", "tools/estado_proyecto.py", "hecho", "Este tablero"),
        ],
    },
]

# Métricas publicadas (snapshot de docs/EVAL_ENSEMBLE.md y docs/METRICAS_GATE.md).
MOTORES = [
    {"m": "Solo edad", "exacto": 1.00, "pm1": 1.00},
    {"m": "Laya afinado v1", "exacto": 0.137, "pm1": 0.480},
    {"m": "Laya base", "exacto": 0.507, "pm1": 0.857},
    {"m": "Matcher híbrido", "exacto": 0.663, "pm1": 0.690},
    {"m": "Ensemble", "exacto": 0.940, "pm1": 0.973},
]
CONTRA_EDAD = [
    {"m": "Solo edad", "exacto": 0.17, "pm1": 0.62, "recall": 0.00},
    {"m": "Ensemble (desplegado)", "exacto": 0.47, "pm1": 0.73, "recall": 0.50},
    {"m": "Ensemble + conductas U2", "exacto": 0.72, "pm1": 0.88, "recall": 0.80},
]
GATE = [
    {"u": 0.00, "auto": 100, "exacto": 94.0, "rev": 0, "final": 94.0},
    {"u": 0.08, "auto": 91, "exacto": 96.4, "rev": 9, "final": 96.7},
    {"u": 0.12, "auto": 86, "exacto": 97.3, "rev": 14, "final": 97.7},
    {"u": 0.15, "auto": 83, "exacto": 98.0, "rev": 17, "final": 98.3},
    {"u": 0.20, "auto": 75, "exacto": 98.2, "rev": 25, "final": 98.7},
    {"u": 0.25, "auto": 69, "exacto": 98.6, "rev": 31, "final": 99.0},
    {"u": 0.30, "auto": 62, "exacto": 98.4, "rev": 38, "final": 99.0},
]
SEGURIDAD = {
    "f0_hecho": [
        "Firma HMAC fail-closed, whitelist y token de API en el código",
        "IP/ID de instancia/fuera del repo",
        "IMDSv2 obligatorio",
        "Puerto 443 cerrado (no escuchaba)",
        "Cifrado EBS por defecto de la cuenta",
        "Token de la API en Secrets Manager",
        "CloudFront con TLS delante de la EC2",
    ],
    "f0_pendiente": [
        "Activar el token en la API (corte coordinado)",
        "Webhook → CloudFront https + secreto + whitelist",
        "Cerrar 80/8000 a internet (solo CloudFront)",
        "Servicios sin root y cifrar el EBS actual",
    ],
}

# --- Plan y README (lo que dicen los documentos vigentes) --------------------

ARQUITECTURA_README = (
    "WhatsApp → API Gateway + Lambda (firma + whitelist) → SQS → Worker → "
    "Normalizar (Transcribe · visión post-it · video Nova) → Clasificador "
    "(Bedrock + Pydantic) → Sesión (Confirmar / Ajustar / Cancelar) → Commit en "
    "DynamoDB (nivel + auditoría)."
)
STACK_README = [
    "Python 3.12", "AWS SAM", "Lambda", "SQS", "S3", "DynamoDB",
    "Amazon Transcribe", "Amazon Bedrock (claude-sonnet-5 · nova-pro-v1)",
    "Meta WhatsApp Cloud API",
]
# Brecha entre lo que declaran README/PLAN y la implementación verificada en el repo.
BRECHAS = [
    ("Cómputo", "README/PLAN: serverless (Lambda + SAM + SQS + DynamoDB)",
     "Implementación: FastAPI en EC2 `integra-server`; el clasificador corre como ensemble ahí."),
    ("Runtime", "README/PLAN: Python 3.12", "Implementación: Python 3.13 (entorno local y EC2)."),
    ("Clasificador", "1 nivel por la rúbrica (Claude + Pydantic)",
     "Además del LLM: ensemble (matcher híbrido + Laya) con compuerta por margen."),
    ("Dashboard", "PLAN lo deja como stretch del 16-oct (P4)",
     "Entregado: dashboard de datos (dashboard/) + este tablero de estado."),
    ("Contratos", "/contracts congelados al final de la Inception", "No hay carpeta contracts/ en el repo."),
]
# Tareas hasta el cierre (docs/PLAN.md §2), por persona.
PLAN_CIERRE = [
    {"persona": "Ivan", "rama": "Ivan", "tareas": [
        "Decidir la infraestructura de demo y de producción (EC2 para la demo; documentar camino serverless).",
        "Infraestructura como código del servidor (instance profile, security group, systemd).",
        "Secretos de Meta en Secrets Manager, no en disco.",
        "Logs y alarmas básicas (CloudWatch).",
    ], "listo": "docs/INFRA.md + plantilla en infra/, desplegable por otra persona"},
    {"persona": "Sebastián", "rama": "whatsapp-clasificador", "tareas": [
        "Subir al repo el código que corre en integra-server (API + webhook).",
        "Llamar a U2 (normalizar_entradas) antes del ensemble (47 % → 72 %).",
        "Evaluar el ensemble con bench/casos_contra_edad.jsonl.",
    ], "listo": "PR con el código del servidor y la mejora medida"},
    {"persona": "Santiago", "rama": "frontend", "tareas": [
        "Abrir el PR de frontend/ a main.",
        "Mostrar en la ficha del niño/a transcripción, conductas y advertencias de U2.",
        "Marcar los casos 'pendiente de revisión' de la compuerta.",
    ], "listo": "Dashboard en main y desplegado"},
    {"persona": "Mauricio", "rama": "u2-eval-despliegue", "tareas": [
        "Fusionar PR #3 (U2 + evaluación).",
        "Medir audio (Whisper small vs. large-v3-turbo) y video con medios del equipo.",
        "Seguridad: cerrar 22/8000/8501, auth de API, firma del webhook, whitelist, borrar medios, PII fuera de logs.",
    ], "listo": "Checklist de seguridad cumplido en el servidor"},
]


# --------------------------------------------------------------------------- #
# Recolección del estado del repo
# --------------------------------------------------------------------------- #

def _git(*args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=str(RAIZ), capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def estado_repo() -> dict:
    ahead_behind = _git("rev-list", "--left-right", "--count", "origin/Ivan...HEAD")
    ab = ahead_behind.split() if ahead_behind else []
    status = [l for l in _git("status", "--porcelain").splitlines() if l.strip()]
    return {
        "rama": _git("branch", "--show-current") or "—",
        "head": _git("log", "-1", "--pretty=%h · %s"),
        "commits": _git("rev-list", "--count", "HEAD") or "—",
        "fecha_head": _git("log", "-1", "--pretty=%cd", "--date=short") or "—",
        "detras": ab[0] if len(ab) == 2 else "?",
        "delante": ab[1] if len(ab) == 2 else "?",
        "ramas": len([l for l in _git("branch", "-a").splitlines() if l.strip()]),
        "ramas_activas": _git("for-each-ref", "--sort=-committerdate",
                              "--format=%(refname:short)", "refs/remotes/origin") or "",
        "cambios": status,
        "remoto": REMOTO,
    }


def contar_tests(sin_tests: bool) -> dict:
    archivos = sorted((RAIZ / "tests").glob("test_*.py"))
    total = 0
    for f in archivos:
        total += f.read_text(encoding="utf-8", errors="replace").count("def test_")
    info = {"archivos": len(archivos), "declaradas": total, "corridas": None, "ok": None}
    if sin_tests:
        return info
    import re
    try:
        r = subprocess.run(["python", "-m", "pytest", "-q", "-o", "addopts=", "--no-header"],
                           cwd=str(RAIZ), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=600)
        texto = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
        m = re.search(r"(\d+) passed", texto)
        if m:
            info["corridas"] = int(m.group(1))
            info["ok"] = "failed" not in texto and "error" not in texto.lower()
        else:
            m = re.search(r"(\d+) (?:failed|error)", texto)
            if m:
                info["corridas"] = m.group(0)
                info["ok"] = False
    except Exception:
        pass
    return info


def evaluar_areas() -> list[dict]:
    areas = []
    for a in AREAS:
        items = []
        hechos = 0
        for label, ruta, manual, nota in a["items"]:
            if ruta is not None and (RAIZ / ruta).exists():
                estado = "hecho"
            elif manual:
                estado = manual
            else:
                estado = "pendiente"
            if estado == "hecho":
                hechos += 1
            items.append({"label": label, "ruta": ruta, "estado": estado, "nota": nota})
        pct = round(100 * hechos / len(items)) if items else 0
        areas.append({"area": a["area"], "owner": a["owner"], "rama": a["rama"],
                      "pct": pct, "items": items, "hechos": hechos, "total": len(items)})
    return areas


def construir_payload(sin_tests: bool) -> dict:
    areas = evaluar_areas()
    avance = round(sum(a["pct"] for a in areas) / len(areas)) if areas else 0
    tests = contar_tests(sin_tests)
    kpis = {
        "avance": avance,
        "ensemble": "94,0 %",
        "final": "98,3 %",
        "recall_rezago": "80 %",
        "tests": f'{tests["corridas"] or tests["declaradas"]}',
        "tests_ok": bool(tests["ok"]),
        "seguridad": f'{len(SEGURIDAD["f0_hecho"])}/{len(SEGURIDAD["f0_hecho"]) + len(SEGURIDAD["f0_pendiente"])}',
    }
    return {
        "objetivo": OBJETIVO,
        "kpis": kpis,
        "areas": areas,
        "motores": MOTORES,
        "contraEdad": CONTRA_EDAD,
        "gate": GATE,
        "seguridad": SEGURIDAD,
        "plan": {
            "arquitectura": ARQUITECTURA_README,
            "stack": STACK_README,
            "brechas": BRECHAS,
            "cierre": PLAN_CIERRE,
        },
        "tests": tests,
        "repo": estado_repo(),
        "generado": f"{date.today():%d-%m-%Y}",
    }


# --------------------------------------------------------------------------- #
# Presentación
# --------------------------------------------------------------------------- #

CSS = """
:root{--fondo:#f5f7fa;--sup:#fff;--borde:#e4e8ee;--texto:#1e293b;--tenue:#64748b;
--acento:#2563eb;--acento2:#0f766e;--alerta:#dc2626;--ok:#059669;--warn:#d97706;--radio:14px}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;color:var(--texto);background:var(--fondo)}
main{max-width:1360px;margin:0 auto;padding:1.4rem 1.5rem 3rem}
header h1{font-size:1.4rem;margin:0 0 .2rem}
header p{margin:.15rem 0;color:var(--tenue);font-size:.9rem;line-height:1.5}
.badge{display:inline-block;background:#e8f0fe;color:var(--acento);border-radius:999px;padding:.1rem .6rem;font-size:.74rem;font-weight:700;margin-left:.4rem}
.obj{background:linear-gradient(135deg,#eff6ff,#f0fdfa);border:1px solid #dbeafe;border-radius:var(--radio);padding:1rem 1.2rem;margin:1rem 0}
.obj h3{margin:0 0 .35rem;font-size:1rem}
.obj .kpi{color:var(--acento2);font-weight:700}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.9rem;margin:1rem 0}
.kpi{background:var(--sup);border:1px solid var(--borde);border-radius:var(--radio);padding:.85rem 1rem;box-shadow:0 1px 2px rgba(16,24,40,.05)}
.kpi .n{font-size:1.5rem;font-weight:800;color:var(--acento)}
.kpi .l{font-size:.75rem;color:var(--tenue);margin-top:.15rem}
.kpi.ok .n{color:var(--ok)}
nav.tabs{display:flex;gap:.25rem;flex-wrap:wrap;border-bottom:2px solid var(--borde);margin:1.1rem 0 0;position:sticky;top:0;background:var(--fondo);z-index:6;padding-top:.35rem}
nav.tabs button{background:transparent;color:var(--tenue);padding:.55rem .95rem;font-size:.88rem;border:0;border-bottom:3px solid transparent;cursor:pointer;border-radius:9px 9px 0 0;font-weight:600}
nav.tabs button.activo{color:var(--acento);border-bottom-color:var(--acento)}
.panel{display:none;padding-top:1rem}
.panel.activo{display:block}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:1rem;margin-top:1rem}
.card{background:var(--sup);border:1px solid var(--borde);border-radius:var(--radio);padding:1rem 1.1rem;box-shadow:0 1px 3px rgba(16,24,40,.06)}
.card.wide{grid-column:1/-1}
.card h3{margin:0 0 .2rem;font-size:.95rem}
.card .purpose{margin:0 0 .6rem;color:var(--tenue);font-size:.82rem}
.area{border:1px solid var(--borde);border-radius:var(--radio);background:var(--sup);padding:1rem 1.1rem;margin-top:1rem}
.area h3{margin:0;font-size:1rem;display:flex;justify-content:space-between;align-items:center;gap:.5rem;flex-wrap:wrap}
.area .meta{color:var(--tenue);font-size:.8rem;font-weight:400}
.barra{height:9px;background:#eef2f7;border-radius:999px;overflow:hidden;margin:.55rem 0 .8rem}
.barra span{display:block;height:100%;background:linear-gradient(90deg,var(--acento),var(--acento2))}
.items{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:.3rem .9rem}
.it{display:flex;align-items:flex-start;gap:.45rem;font-size:.84rem;padding:.15rem 0}
.dot{width:.65rem;height:.65rem;border-radius:50%;flex:0 0 auto;margin-top:.28rem}
.dot.hecho{background:var(--ok)}.dot.en-curso{background:var(--warn)}.dot.pendiente{background:#cbd5e1}
.it .nota{color:var(--tenue);font-size:.76rem}
.table{width:100%;border-collapse:collapse;font-size:.85rem;margin-top:.4rem}
.table th,.table td{text-align:left;padding:.45rem .5rem;border-bottom:1px solid var(--borde)}
.table th{color:var(--tenue);font-weight:600;font-size:.78rem}
.table td.n{text-align:right;font-variant-numeric:tabular-nums}
.chip{display:inline-block;border-radius:999px;padding:.08rem .55rem;font-size:.74rem;font-weight:700}
.chip.hecho{background:#dcfce7;color:#166534}.chip.en-curso{background:#fef3c7;color:#92400e}.chip.pendiente{background:#e2e8f0;color:#475569}
code{font-family:ui-monospace,Consolas,monospace;background:#f1f5f9;border-radius:6px;padding:.08rem .35rem;font-size:.8rem}
footer{color:var(--tenue);font-size:.8rem;text-align:center;padding:2rem 1rem}
@media(max-width:760px){.grid{grid-template-columns:1fr}}
"""

PLANTILLA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Estado del proyecto · IntegrAI</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>__CSS__</style></head>
<body><main>
<header>
  <h1>Estado del proyecto · IntegrAI<span class="badge">datos sintéticos</span></h1>
  <p>Tablero de equipo · Breaking Barriers 2026 · actualizado el __GENERADO__.</p>
</header>
<div class="obj">
  <h3>__OBJ_TITULO__</h3>
  <p>__OBJ_DETALLE__</p>
  <p><span class="kpi">KPI: __OBJ_KPI__</span></p>
  <p class="meta" style="color:#64748b;font-size:.85rem">__OBJ_ESTADO__</p>
</div>
<div class="kpis" id="kpis"></div>
<nav class="tabs" id="tabs">
  <button data-tab="resumen" class="activo">Resumen</button>
  <button data-tab="areas">Áreas y equipo</button>
  <button data-tab="plan">Plan y README</button>
  <button data-tab="modelo">Métricas del modelo</button>
  <button data-tab="seguridad">Seguridad</button>
  <button data-tab="repo">Repositorio</button>
</nav>

<section class="panel activo" data-panel="resumen">
  <div class="grid">
    <div class="card"><h3>Avance por área</h3><p class="purpose">% de entregables presentes en el repo.</p><div id="fig-areas" style="height:340px"></div></div>
    <div class="card"><h3>Exactitud por motor (300 notas)</h3><p class="purpose">Exacto vs. ±1 nivel. Fuente: docs/EVAL_ENSEMBLE.md.</p><div id="fig-motores" style="height:340px"></div></div>
  </div>
</section>

<section class="panel" data-panel="areas"><div id="areas"></div></section>

<section class="panel" data-panel="plan"><div id="plan"></div></section>

<section class="panel" data-panel="modelo">
  <div class="grid">
    <div class="card wide"><h3>Casos "contra la edad" (60 casos)</h3><p class="purpose">Cuando el niño se aparta de su edad: exactitud, ±1 y recall de alerta de rezago.</p><div id="fig-contra" style="height:340px"></div></div>
    <div class="card wide"><h3>Compuerta por margen</h3><p class="purpose">Auto-registradas, exactitud de las aceptadas y exactitud final con revisión humana.</p><div id="fig-gate" style="height:340px"></div></div>
  </div>
  <div class="card wide" style="margin-top:1rem">
    <h3>Lectura</h3>
    <p class="purpose">Punto operativo <code>margen &lt; 0,15</code></p>
    <ul style="font-size:.88rem;color:#475569;line-height:1.6">
      <li>83 % se auto-registra con <strong>98,0 %</strong> de acierto; 17 % va a revisión de la educadora.</li>
      <li>La compuerta atrapa el <strong>72 %</strong> de los errores; <strong>5 errores escapan</strong> (riesgo residual).</li>
      <li>Con revisión humana de la cola, la <strong>exactitud final es 98,3 %</strong>.</li>
      <li>La edad explica casi todo el acierto: en casos "contra la edad" el ensemble desplegado baja a 47 %. Poner U2 (nota → conductas) delante sube el exacto a 72 % y el recall de rezago a 80 %.</li>
    </ul>
  </div>
</section>

<section class="panel" data-panel="seguridad">
  <div class="grid">
    <div class="card"><h3>Controles F0 (antes de la demo)</h3><p class="purpose">Aplicados vs. pendientes.</p><div id="fig-seg" style="height:300px"></div></div>
    <div class="card"><h3>Pendientes para el corte</h3><p class="purpose">Requieren coordinación con Sebastián.</p><ul id="seg-pend" style="font-size:.86rem;color:#475569;line-height:1.6"></ul></div>
  </div>
  <div class="card wide" style="margin-top:1rem"><h3>Hallazgos corregidos en el código</h3>
    <p class="purpose">Firma fail-closed, whitelist, token, path traversal, magic bytes, PII en logs, prompt injection y más (docs/SEGURIDAD.md, H1–H20).</p>
  </div>
</section>

<section class="panel" data-panel="repo"><div class="grid" id="repo-grid"></div></section>

<footer>Tablero interno de equipo · datos 100 % sintéticos · no es un instrumento clínico.
Las métricas son un snapshot de los documentos del repo.</footer>
</main>
<script>
const DATA = __DATA__;
__APP__
</script>
</body></html>
"""

APP = r"""
const $ = id => document.getElementById(id);
const COLOR = {ok:"#059669", warn:"#d97706", gris:"#cbd5e1", azul:"#2563eb", teal:"#0f766e"};

function pct(x){ return Math.round(x); }

function renderKpis(){
  const k = DATA.kpis;
  const items = [
    {n:k.avance+"%", l:"Avance de entregables", cls:"ok"},
    {n:k.ensemble, l:"Exactitud ensemble", cls:""},
    {n:k.final, l:"Exactitud final (compuerta)", cls:"ok"},
    {n:k.recall_rezago, l:"Recall alerta de rezago", cls:""},
    {n:k.tests, l:"Tests en verde", cls:k.tests_ok?"ok":""},
    {n:k.seguridad, l:"Controles F0 aplicados", cls:""},
  ];
  $("kpis").innerHTML = items.map(i =>
    `<div class="kpi ${i.cls}"><div class="n">${i.n}</div><div class="l">${i.l}</div></div>`).join("");
}

function renderAreas(){
  const cont = $("areas");
  cont.innerHTML = DATA.areas.map(a => {
    const its = a.items.map(it => {
      const cls = it.estado.replace(" ", "-").replace("ó","o");
      const estado = it.estado.charAt(0).toUpperCase() + it.estado.slice(1);
      const nota = it.nota ? ` <span class="nota">· ${it.nota}</span>` : "";
      return `<div class="it"><span class="dot ${cls}" title="${estado}"></span><span>${it.label}${nota}</span></div>`;
    }).join("");
    return `<div class="area">
      <h3>${a.area} <span class="meta">${a.owner} · rama <code>${a.rama}</code> · ${a.hechos}/${a.total} · ${a.pct}%</span></h3>
      <div class="barra"><span style="width:${a.pct}%"></span></div>
      <div class="items">${its}</div>
    </div>`;
  }).join("");
}

function renderSeg(){
  $("seg-pend").innerHTML = DATA.seguridad.f0_pendiente.map(x => `<li>${x}</li>`).join("");
}

function renderPlan(){
  const p = DATA.plan;
  const brechas = p.brechas.map(b => `<tr><th>${b[0]}</th><td>${b[1]}<br><em style="color:#0f766e">${b[2]}</em></td></tr>`).join("");
  const cierre = p.cierre.map(c => `
    <div class="area">
      <h3>${c.persona} <span class="meta">rama <code>${c.rama}</code></span></h3>
      <ul style="font-size:.86rem;color:#475569;line-height:1.55;margin:.2rem 0 .5rem">${c.tareas.map(t=>`<li>${t}</li>`).join("")}</ul>
      <p class="purpose">Listo cuando: ${c.listo}</p>
    </div>`).join("");
  $("plan").innerHTML = `
    <div class="card wide" style="margin-top:1rem">
      <h3>Arquitectura declarada (README actual)</h3>
      <p class="purpose">${p.arquitectura}</p>
      <p class="purpose">Stack declarado: ${p.stack.map(s=>`<code>${s}</code>`).join(" ")}</p>
    </div>
    <div class="card wide" style="margin-top:1rem">
      <h3>Plan vs. implementación (brechas)</h3>
      <p class="purpose">Lo que dicen los documentos frente a lo verificado en el repositorio.</p>
      <table class="table">${brechas}</table>
    </div>
    <h3 class="seccion" style="margin:1.4rem 0 .2rem;font-size:1rem">Tareas hasta el cierre (docs/PLAN.md §2)</h3>
    ${cierre}`;
}

const CFG = {responsive:true, displaylogo:false, modeBarButtonsToRemove:["lasso2d","select2d"]};
function lay(extra){ return Object.assign({
  margin:{t:20,r:16,b:60,l:60}, font:{family:"system-ui,Segoe UI,Roboto,Arial", size:12, color:"#334155"},
  paper_bgcolor:"#fff", plot_bgcolor:"#fff",
  xaxis:{gridcolor:"#eef2f7"}, yaxis:{gridcolor:"#eef2f7"}, showlegend:true,
  legend:{orientation:"h", y:-0.2}
}, extra||{}); }

function drawAreas(){
  const a = DATA.areas;
  Plotly.react("fig-areas", [{type:"bar", orientation:"h", x:a.map(x=>x.pct), y:a.map(x=>x.area),
    text:a.map(x=>x.pct+"%"), textposition:"outside",
    marker:{color:a.map(x=>x.pct>=90?COLOR.ok:x.pct>=60?COLOR.azul:COLOR.warn)}}],
    lay({showlegend:false, xaxis:{range:[0,108], title:"% completado", gridcolor:"#eef2f7"},
      yaxis:{automargin:true}, margin:{t:10,r:30,b:50,l:170}}), CFG);
}

function drawMotores(){
  const m = DATA.motores;
  Plotly.react("fig-motores", [
    {type:"bar", name:"Exacto", x:m.map(x=>x.m), y:m.map(x=>x.exacto), marker:{color:COLOR.azul}},
    {type:"bar", name:"±1", x:m.map(x=>x.m), y:m.map(x=>x.pm1), marker:{color:"#93c5fd"}}
  ], lay({barmode:"group", yaxis:{tickformat:".0%", range:[0,1.08], gridcolor:"#eef2f7"},
    xaxis:{automargin:true, tickangle:-15}}), CFG);
}

function drawContra(){
  const c = DATA.contraEdad;
  Plotly.react("fig-contra", [
    {type:"bar", name:"Exacto", x:c.map(x=>x.m), y:c.map(x=>x.exacto), marker:{color:COLOR.azul}},
    {type:"bar", name:"±1", x:c.map(x=>x.m), y:c.map(x=>x.pm1), marker:{color:"#93c5fd"}},
    {type:"bar", name:"Recall rezago", x:c.map(x=>x.m), y:c.map(x=>x.recall), marker:{color:COLOR.warn}}
  ], lay({barmode:"group", yaxis:{tickformat:".0%", range:[0,1.08], gridcolor:"#eef2f7"}}), CFG);
}

function drawGate(){
  const g = DATA.gate;
  Plotly.react("fig-gate", [
    {type:"bar", name:"Auto-registradas (%)", x:g.map(x=>x.u), y:g.map(x=>x.auto), marker:{color:"#93c5fd"}},
    {type:"bar", name:"A revisión (%)", x:g.map(x=>x.u), y:g.map(x=>x.rev), marker:{color:"#fca5a5"}},
    {type:"scatter", mode:"lines+markers", name:"Exactitud final (%)", x:g.map(x=>x.u), y:g.map(x=>x.final),
     line:{color:COLOR.ok, width:3}, marker:{size:8}, yaxis:"y"}
  ], lay({barmode:"group", xaxis:{title:"umbral de margen", dtick:0.05},
    yaxis:{title:"%", range:[0,105], gridcolor:"#eef2f7"}}), CFG);
}

function drawSeg(){
  const hecho = DATA.seguridad.f0_hecho.length, pend = DATA.seguridad.f0_pendiente.length;
  Plotly.react("fig-seg", [{type:"pie", hole:.55, labels:["Aplicados","Pendientes"],
    values:[hecho,pend], marker:{colors:[COLOR.ok, COLOR.gris]}, textinfo:"label+value"}],
    lay({showlegend:false, margin:{t:10,r:10,b:10,l:10}}), CFG);
}

function renderRepo(){
  const r = DATA.repo;
  const cambios = r.cambios.length ? r.cambios.map(c=>`<li><code>${c}</code></li>`).join("") : "<li>Sin cambios pendientes</li>";
  const ramas = (r.ramas_activas||"").split("\n").filter(Boolean).slice(0,12).map(x=>`<li><code>${x}</code></li>`).join("");
  $("repo-grid").innerHTML = `
    <div class="card"><h3>Rama de trabajo</h3><p class="purpose">Sincronía con el remoto.</p>
      <table class="table">
        <tr><th>Rama</th><td><code>${r.rama}</code></td></tr>
        <tr><th>Último commit</th><td>${r.head}</td></tr>
        <tr><th>Commits (HEAD)</th><td class="n">${r.commits}</td></tr>
        <tr><th>Fecha</th><td>${r.fecha_head}</td></tr>
        <tr><th>vs. origin/Ivan</th><td>detrás ${r.detras} · delante ${r.delante}</td></tr>
        <tr><th>Ramas remotas</th><td class="n">${r.ramas}</td></tr>
      </table></div>
    <div class="card"><h3>Cambios en el árbol</h3><p class="purpose">Sin commitear en esta máquina.</p>
      <ul style="font-size:.84rem;color:#475569">${cambios}</ul></div>
    <div class="card wide"><h3>Ramas remotas recientes</h3><p class="purpose">Trabajo en curso del equipo.</p>
      <ul style="columns:2;font-size:.84rem;color:#475569">${ramas}</ul></div>`;
}

document.querySelectorAll("nav.tabs button").forEach(b => b.addEventListener("click", () => {
  document.querySelectorAll("nav.tabs button").forEach(x=>x.classList.remove("activo"));
  b.classList.add("activo");
  document.querySelectorAll(".panel").forEach(p => p.classList.toggle("activo", p.dataset.panel===b.dataset.tab));
  requestAnimationFrame(()=>{ ["fig-areas","fig-motores","fig-contra","fig-gate","fig-seg"].forEach(f=>{
    const el=$(f); if(el && window.Plotly) Plotly.Plots.resize(el); }); });
}));

renderKpis(); renderAreas(); renderSeg(); renderRepo(); renderPlan();
drawAreas(); drawMotores(); drawContra(); drawGate(); drawSeg();
"""


def render(payload: dict, salida: Path) -> Path:
    html = (PLANTILLA
            .replace("__CSS__", CSS)
            .replace("__GENERADO__", payload["generado"])
            .replace("__OBJ_TITULO__", payload["objetivo"]["titulo"])
            .replace("__OBJ_DETALLE__", payload["objetivo"]["detalle"])
            .replace("__OBJ_KPI__", payload["objetivo"]["kpi"])
            .replace("__OBJ_ESTADO__", payload["objetivo"]["estado"])
            .replace("__DATA__", json.dumps(payload, ensure_ascii=False))
            .replace("__APP__", APP))
    salida.write_text(html, encoding="utf-8")
    return salida


def main() -> int:
    parser = argparse.ArgumentParser(description="Dashboard de estado del proyecto.")
    parser.add_argument("--salida", default=str(SALIDA))
    parser.add_argument("--abrir", action="store_true")
    parser.add_argument("--sin-tests", action="store_true", help="No ejecutar pytest")
    args = parser.parse_args()

    payload = construir_payload(sin_tests=args.sin_tests)
    destino = render(payload, Path(args.salida))
    areas = payload["areas"]
    print(f"Generado: {destino}  ({destino.stat().st_size // 1024} KB)")
    print(f"Avance global: {payload['kpis']['avance']}%")
    for a in areas:
        print(f"  - {a['area']:<38} {a['pct']:>3}%  ({a['hechos']}/{a['total']})")
    print(f"Tests: {payload['kpis']['tests']}")
    if args.abrir:
        webbrowser.open(destino.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
