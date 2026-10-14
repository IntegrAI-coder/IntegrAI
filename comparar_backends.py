"""Compara los backends de decisión (Híbrido vs Laya typesafe) sobre casos reales.

    python3 comparar_backends.py
Muestra, por cada observación: el nivel que decide cada motor, su confianza y
(si disponible) la distribución calibrada. Sirve como evidencia del diferencial
"decision model typesafe" para el pitch.
"""
from __future__ import annotations

from src import marco
from src.clasificador import Clasificador
from src.matcher import Matcher

CASOS = [
    ("se sacó y guardó sus zapatos solo, armó una torre de cuatro bloques y contó hasta cinco. Compartió los materiales por turnos.", 24),
    ("balbucea y responde a la voz con sonidos, sigue un objeto lento con la mirada", 3),
    ("camina sola por la sala, usa la cuchara para comer y dice dos palabras juntas", 15),
    ("sostiene la cabeza brevemente boca abajo y mueve brazos y piernas", 1),
    ("conversa con frases completas, espera su turno en el juego y resuelve un rompecabezas", 30),
]


def main() -> None:
    matcher = Matcher()  # compartido: la evidencia (matches) es igual para ambos
    motores = {}
    import os
    motor_names = ["hibrido", "laya"]
    if os.getenv("LAYA_MODEL_PATH"):
        motor_names.append("laya-integra")
    for nombre in motor_names:
        try:
            motores[nombre] = Clasificador(matcher=matcher, backend=nombre)
            print(f"✔ motor '{nombre}' cargado")
        except Exception as e:  # noqa: BLE001
            print(f"✖ motor '{nombre}' no disponible: {e!r}")

    print("\n" + "=" * 96)
    for texto, edad in CASOS:
        print(f"\n📝 {texto[:88]}  ({edad} meses)")
        for nombre, cl in motores.items():
            r = cl.clasificar(texto, edad)
            dist = " ".join(f"{l}:{r.probabilidades.get(l,0):.2f}" for l in sorted(r.probabilidades))
            print(f"   [{nombre:7}] nivel={r.nivel} ({marco.nombre_nivel(r.nivel) if r.nivel else '—':<28}) "
                  f"conf={r.confianza:.2f} suf={r.evidencia_suficiente} doms={r.dominios}")
            print(f"             dist: {dist}")
    print("\n" + "=" * 96)


if __name__ == "__main__":
    main()
