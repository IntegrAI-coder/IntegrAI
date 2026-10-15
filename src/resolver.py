"""Resolver determinista de nombre → `id_nino` (IntegrAI · Desafío E-1).

POR QUÉ EXISTE
--------------
El LLM/OCR **no** asigna el `id_nino`: extrae la mención literal del nombre.
Este módulo la mapea contra el **roster de la sala** imitando la lógica de la tía:

  · nombre de pila ÚNICO en la sala   -> resuelve solo.
  · nombre de pila REPETIDO           -> exige apellido ("sebastian wagner").
  · diminutivos ("mati") / typos OCR  -> intenta resolver con confianza.
  · sin coincidencia o ambiguo        -> NO resuelve (va a "por verificar").

La resolución es **reproducible y auditable** (se guarda el método y la evidencia).
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

UMBRAL_FUZZY = 0.86  # similitud mínima para aceptar un match "fuzzy"

# Diminutivos/apodos frecuentes en Chile -> nombre(s) canónico(s).
DIMINUTIVOS: dict[str, set[str]] = {
    "mati": {"matias", "matilde", "matilda"},
    "cote": {"maria jose", "constanza"},
    "pancho": {"francisco"},
    "nacho": {"ignacio"},
    "vale": {"valentina", "valeria"},
    "fede": {"federico", "federica"},
    "nico": {"nicolas", "nicole"},
    "joaco": {"joaquin"},
    "tomi": {"tomas"},
    "flor": {"florencia"},
    "cami": {"camila"},
    "cris": {"cristobal", "cristina"},
    "ale": {"alejandra", "alejandro", "alejandrina"},
    "seba": {"sebastian", "sebastiana"},
}


def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos, sin puntuación, espacios colapsados."""
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join("".join(c if c.isalnum() or c.isspace() else " " for c in t.lower()).split())


@dataclass
class Resultado:
    id_nino: str | None
    metodo: str                       # exacto | exacto+apellido | diminutivo | fuzzy | -
    estado: str                       # resuelto | ambiguo | desconocido
    confianza: float = 1.0
    candidatos: list[str] = field(default_factory=list)
    evidencia: str = ""

    @property
    def requiere_verificacion(self) -> bool:
        return self.estado != "resuelto"


class Resolver:
    """Índice nombre→id por sala. Se construye desde las filas de `ninos` de una sala."""

    def __init__(self, filas: list[dict]) -> None:
        # índice: pila_normalizado -> { id_nino: set(apellidos_normalizados) }
        self.index: dict[str, dict[str, set[str]]] = {}
        for f in filas:
            pila = normalizar(f.get("nombre_pila") or "")
            if not pila:
                continue
            apells = set(normalizar(f.get("apellidos") or "").split())
            self.index.setdefault(pila, {}).setdefault(f["id_nino"], set()).update(apells)

    # ------------------------------------------------------------------
    def resolver(self, mencion: str) -> Resultado:
        toks = normalizar(mencion).split()
        if not toks:
            return Resultado(None, "-", "desconocido", evidencia="mención vacía")
        pila, apells = toks[0], toks[1:]

        # 1) match exacto de nombre de pila
        cands = self.index.get(pila)
        if cands:
            if len(cands) == 1:
                idn = next(iter(cands))
                return Resultado(idn, "exacto", "resuelto",
                                 evidencia=f"'{pila}' único en la sala")
            if apells:  # homónimos: la tía dio apellido
                for idn, aps in cands.items():
                    if any(a in aps for a in apells):
                        return Resultado(idn, "exacto+apellido", "resuelto",
                                         evidencia=f"'{pila}' + apellido {apells}")
                return Resultado(None, "-", "ambiguo", 0.0, sorted(cands),
                                 f"apellido {apells} no matchea a los homónimos '{pila}'")
            return Resultado(None, "-", "ambiguo", 0.0, sorted(cands),
                             f"'{pila}' repetido y sin apellido")

        # 2) diminutivos
        for canon in DIMINUTIVOS.get(pila, set()):
            sub = self.index.get(canon) or self.index.get(canon.split()[0] if canon.split() else "")
            if sub and len(sub) == 1:
                return Resultado(next(iter(sub)), "diminutivo", "resuelto", 0.9,
                                 evidencia=f"'{pila}' -> '{canon}'")

        # 3) fuzzy (typos de OCR) sobre nombres de pila
        best_id, best_score = None, 0.0
        for clave, ids in self.index.items():
            s = SequenceMatcher(None, pila, clave).ratio()
            if s > best_score and len(ids) == 1:
                best_id, best_score = next(iter(ids)), s
        if best_id and best_score >= UMBRAL_FUZZY:
            return Resultado(best_id, "fuzzy", "resuelto", best_score,
                             evidencia=f"'{pila}' ~ similitud {best_score:.2f}")

        return Resultado(None, "-", "desconocido", 0.0, [],
                         f"'{pila}' no está en el roster de la sala")


def resolver_menciones(menciones: list[str], filas_sala: list[dict]) -> list[Resultado]:
    """Resuelve varias menciones (un mensaje puede nombrar a más de un niño/a)."""
    r = Resolver(filas_sala)
    return [r.resolver(m) for m in menciones]


def es_apellido_del_roster(cand: str, aps: list[str]) -> bool:
    """¿`cand` coincide con (o es prefijo de) algún apellido del roster?"""
    return any(a == cand or a.startswith(cand + " ") or cand.startswith(a) for a in aps if a)


def extraer_menciones(texto: str, filas: list[dict]) -> list[str]:
    """TODAS las menciones de la frase (nombre de pila del roster o diminutivo + apellidos
    del roster), en orden y sin repetir. Un mensaje puede nombrar a **más de un niño/a**
    ("Sofía jugó bien con Camila")."""
    toks = normalizar(texto).split()
    pila = {normalizar(f["nombre_pila"]) for f in filas if f.get("nombre_pila")}
    aps = [normalizar(f.get("apellidos") or "") for f in filas if f.get("apellidos")]
    aliases = set(DIMINUTIVOS.keys())
    out: list[str] = []
    vistos: set[str] = set()
    i = 0
    while i < len(toks):
        t = toks[i]
        if t in pila or t in aliases:
            nombre = [t]
            j = i + 1
            while j < len(toks) and len(nombre) < 3 and es_apellido_del_roster(toks[j], aps):
                nombre.append(toks[j]); j += 1
            men = " ".join(nombre)
            if men not in vistos:
                vistos.add(men); out.append(men)
            i = j
        else:
            i += 1
    return out


def extraer_mencion(texto: str, filas: list[dict]) -> str:
    """Primera mención (compatibilidad con el flujo de un solo niño/a)."""
    menciones = extraer_menciones(texto, filas)
    if menciones:
        return menciones[0]
    toks = normalizar(texto).split()
    return toks[0] if toks else ""


if __name__ == "__main__":  # self-test con el caso del enunciado
    roster = [
        {"id_nino": "N-001", "nombre_pila": "Sebastián", "apellidos": "Wagner"},
        {"id_nino": "N-002", "nombre_pila": "Sebastián", "apellidos": "Pérez"},
        {"id_nino": "N-003", "nombre_pila": "Martina",   "apellidos": "Soto"},
        {"id_nino": "N-004", "nombre_pila": "Matías",    "apellidos": "Rojas"},
    ]
    casos = [
        "sebastian wagner",          # -> N-001 (homónimo + apellido)
        "sebastian perez",           # -> N-002
        "sebastian",                 # -> AMBIGUO (2 homónimos)
        "martina",                   # -> N-003 (único)
        "mati",                      # -> N-004 (diminutivo)
        "marthina",                  # -> fuzzy -> N-003
        "josefa",                    # -> DESCONOCIDO
    ]
    for c in casos:
        r = Resolver(roster).resolver(c)
        print(f"{c:20s} -> {r.estado:11s} {r.id_nino or '—':6s} [{r.metodo}] {r.evidencia}")
