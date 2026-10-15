#!/usr/bin/env python3
"""Simula una HISTORIA de observaciones por niño/a (varios días) para probar la
**evaluación constante** (no una foto de una actividad).

Para cada niño/a de los 4 cursos (JAR-EQUIPO) genera observaciones a lo largo de D días,
con notas del día a día ("se vistió sola", "no durmió la siesta", "se peleó con un
compañero"...), siguiendo un **perfil**:
  · estable    → nivel ~ plano
  · avance     → el nivel sube en el período
  · retroceso  → el nivel baja (dispara alerta de retroceso)
  · oscilante  → vaivén
  · rezago     → por debajo de su banda etaria (dispara alerta de rezago)

Cada día pone **1-2 notas**; cuando las notas del día discrepan (1 nivel), la
consolidación queda con **margen bajo** → entra a la cola "por verificar" (la tía decide).

Después corre el CRON día a día (periodo=fecha) para acumular evaluaciones + tendencias.

Idempotente: borra lo sintético (OBS-9*) y re-inicia el watermark.

Uso (en la EC2, con el venv):
    /opt/integra/.venv/bin/python tools/simular_trayectorias.py [dias]
"""
from __future__ import annotations

import os
import random
import sys
from datetime import date, timedelta

sys.path.insert(0, os.getenv("INTEGRA_HOME", "/opt/integra"))
from src.plataforma import Plataforma  # noqa: E402
from src import marco  # noqa: E402
from src.evaluacion_periodica import ejecutar  # noqa: E402
from catalogo_manifestaciones import elegir, indice  # noqa: E402

MANIF = indice()   # catálogo de conductas observables → evidencia por (nivel, dominio)

JARDIN = "JAR-EQUIPO"
ORIGEN = "demo_hist"
DIAS = int(sys.argv[1]) if len(sys.argv) > 1 else 12
FECHA_FIN = date(2026, 10, 13)          # el demo mira hacia el 13-oct
PERFILES = ["estable", "avance", "retroceso", "oscilante", "rezago", "avance",
            "estable", "oscilante", "retroceso", "avance"]

CURSOS = [("Sala Girasol", "EDU-EQ-1"), ("Sala Mariposa", "EDU-EQ-2"),
          ("Sala Estrella", "EDU-EQ-3"), ("Sala Cometa", "EDU-EQ-4")]

LEXICO = {
    1: ["lloró mucho y le costó calmarse aun con ayuda", "no toleró la separación de su adulto",
        "necesitó apoyo constante para regularse"],
    2: ["se calmó con la voz de la tía después de un rato", "se frustró al esperar su turno"],
    3: ["hizo la rutina con apoyo del adulto", "mostró sus cosas pero le costó compartir"],
    4: ["siguió la rutina con un recordatorio", "se frustró al perder un juego y se calmó con ayuda"],
    5: ["guardó sus cosas cuando se lo pidieron", "esperó su turno con un recordatorio"],
    6: ["se vistió casi solo (ayuda en los botones)", "compartió cuando se lo pidieron"],
    7: ["se vistió solo y ordenó sin que se lo pidieran", "resolvió un conflicto conversando"],
    8: ["se vistió solo, guardó sus cosas y ayudó a un compañero",
        "por iniciativa propia esperó su turno y compartió"],
}
DIA_DIFICIL = ["no durmió la siesta y estuvo irritable", "no quiso comer su comida",
               "se peleó con un compañero", "lloró mucho, extrañó a su familia",
               "estuvo decaído/a y participó poco"]
FORMATOS = ["texto", "audio", "imagen", "texto", "texto", "video"]


def _nivel_edad(nin: dict, f: date) -> int:
    if not nin.get("fecha_nacimiento"):
        return 5
    edad = marco.edad_meses(nin["fecha_nacimiento"], f.isoformat())
    esperados = marco.niveles_esperados_por_edad(edad)
    return esperados[0] if esperados else 5


def main() -> None:
    rnd = random.Random(20261015)
    p = Plataforma()
    c = p.con

    # limpiar TODO lo sintético (OBS-9*) + pendientes de JAR-EQUIPO + reiniciar watermark.
    c.execute("DELETE FROM observaciones WHERE id_observacion LIKE 'OBS-9%'")
    c.execute("DELETE FROM evaluaciones_pendientes WHERE id_nino_propuesto IN "
              "(SELECT id_nino FROM ninos WHERE id_jardin=?)", (JARDIN,))
    c.commit()
    wm = c.execute("SELECT COALESCE(MAX(rowid),0) m FROM observaciones").fetchone()["m"]
    p.set_meta("cron_watermark_rowid", str(wm))
    print(f"limpio · watermark reiniciado a {wm}")

    plan = []
    for sala, edu in CURSOS:
        for i, nin in enumerate(p.ninos_de(JARDIN, sala)):
            plan.append({"nin": nin, "edu": edu, "perfil": PERFILES[i % len(PERFILES)],
                         "ajuste": rnd.choice([-4, -3, -2, -1, 0, 0, 0, 1])})

    total = 0
    for d in range(DIAS):
        f = FECHA_FIN - timedelta(days=(DIAS - 1 - d))
        for item in plan:
            nin, edu, perfil = item["nin"], item["edu"], item["perfil"]
            base = _nivel_edad(nin, f) + item["ajuste"]
            frac = d / max(1, DIAS - 1)
            if perfil == "rezago":
                base -= 2
            delta = {"avance": 2.0 * frac, "retroceso": -2.0 * frac,
                     "oscilante": rnd.choice([-1.5, 0.0, 1.5]) * (0.6 + frac)}.get(perfil, 0.0)
            nivel = max(1, min(8, round(base + delta + rnd.uniform(-0.4, 0.4))))

            # 1-2 notas del día. Si discrepan 1 nivel -> margen bajo -> "por verificar".
            niveles = [nivel]
            if rnd.random() < 0.5:
                niveles.append(max(1, min(8, nivel + (rnd.choice([-1, 1]) if rnd.random() < 0.6 else 0))))
            for l in niveles:
                if rnd.random() < 0.15:            # un "día difícil"
                    nota, dom = rnd.choice(DIA_DIFICIL), "socioemocional"
                    l = max(1, l - 2)
                else:
                    nota = rnd.choice(LEXICO.get(l) or LEXICO[8])
                    dom = rnd.choice(["motor_grueso", "motor_fino", "lenguaje_comunicacion",
                                      "socioemocional", "cognitivo"])
                p.registrar_observacion(nin["id_nino"], edu, f.isoformat(), rnd.choice(FORMATOS),
                                        l, f"{nin.get('nombre_pila','')}: {nota}",
                                        dominios=[dom], manifestaciones=elegir(MANIF, l, dom, rnd=rnd),
                                        confianza=rnd.uniform(0.55, 0.9),
                                        origen=ORIGEN, metodo_resolucion="demo_hist")
                total += 1
        c.commit()
        r = ejecutar(periodo=f.isoformat())
        print(f"  {f} → obs {r['observaciones_nuevas']:>3} · eval {r['evaluaciones']:>3} · "
              f"por_verificar {r['pendientes']:>3} · alertas {r['alertas']:>3}", flush=True)

    print(f"\n✅ {total} observaciones en {DIAS} días para {len(plan)} niños de {JARDIN}")
    from collections import Counter
    tend = Counter(p.trayectoria(x["nin"]["id_nino"], FECHA_FIN.isoformat()).get("tendencia") for x in plan)
    print("tendencias:", dict(tend))


if __name__ == "__main__":
    main()
