"""Tests de extracción de menciones y resolución multi-niño (IntegrAI · E-1).

Cubre el caso "Sofía jugó bien con Camila": un mensaje que nombra a DOS niños/as.
"""
from src.resolver import extraer_mencion, extraer_menciones, resolver_menciones

# Sala con un HOMÓNIMO (dos Sofía) + Camila + Emilia.
ROSTER = [
    {"id_nino": "N-1", "nombre_pila": "Sofía", "apellidos": "Sepúlveda"},
    {"id_nino": "N-2", "nombre_pila": "Sofía", "apellidos": "Navarro"},
    {"id_nino": "N-3", "nombre_pila": "Camila", "apellidos": "Rojas"},
    {"id_nino": "N-4", "nombre_pila": "Emilia", "apellidos": "Contreras"},
]


def test_extrae_dos_menciones():
    assert extraer_menciones("hoy Sofía jugó bien con Camila", ROSTER) == ["sofia", "camila"]


def test_extrae_mencion_con_apellido_del_roster():
    assert extraer_menciones("Emilia Contreras se vistió sola", ROSTER) == ["emilia contreras"]


def test_ignora_verbo_como_apellido():
    # "compartió" NO es apellido del roster -> no se pega al nombre
    assert extraer_menciones("Sofía compartió un juguete", ROSTER) == ["sofia"]


def test_extraer_mencion_singular_es_la_primera():
    assert extraer_mencion("Camila y Emilia jugaron", ROSTER) == "camila"


def test_homonimo_sin_apellido_es_ambiguo():
    (r,) = resolver_menciones(["sofia"], ROSTER)
    assert r.estado == "ambiguo" and r.id_nino is None


def test_multi_resuelve_ambos():
    menciones = extraer_menciones("Sofía Sepúlveda y Camila compartieron los bloques", ROSTER)
    res = resolver_menciones(menciones, ROSTER)
    assert [x.id_nino for x in res] == ["N-1", "N-3"]


def test_sin_menciones_devuelve_lista_vacia():
    assert extraer_menciones("hoy fue un día tranquilo", ROSTER) == []
