"""Tests del marco por tramos (no requieren el docx: usan una rúbrica mínima en memoria)."""
import pytest

from src import marcos
from src.marcos import MarcoRubrica, edad_al_corte, tramo_por_edad, tramo_por_meses

NOMBRES = ["Comenzando", "Explorando", "Desarrollando", "Afianzando", "Integrando", "Ampliando", "Consolidando", "Profundizando"]


def rubrica_minima() -> MarcoRubrica:
    from tools.importar_rubrica import TRAMOS
    tramos = [{**t, "niveles": [{"nivel": i + 1, "nombre": n, "descripcion": f"desc {t['id']} {i + 1}",
                                 "conductas": [f"conducta clave{i + 1}x"], "ejemplos": [f"ejemplo clave{i + 1}x uno", f"ejemplo clave{i + 1}x dos"]}
                                for i, n in enumerate(NOMBRES)]} for t in TRAMOS]
    return MarcoRubrica({"marco": "integra_iya", "nucleo": {"id": "identidad_autonomia"}, "tramos": tramos})


@pytest.fixture
def m():
    return rubrica_minima()


@pytest.mark.parametrize("meses,esperado", [
    (0, ("sala_cuna", "sala_cuna_menor")), (11, ("sala_cuna", "sala_cuna_menor")),
    (12, ("sala_cuna", "sala_cuna_mayor")), (23, ("sala_cuna", "sala_cuna_mayor")),
    (24, ("nivel_medio", "medio_menor")), (36, ("nivel_medio", "medio_mayor")), (47, ("nivel_medio", "medio_mayor")),
    (48, ("transicion", "nt1")), (60, ("transicion", "nt2")), (71, ("transicion", "nt2")),
    (72, None), (None, None), (-3, None)])
def test_tramos_por_meses(m, meses, esperado):
    assert tramo_por_meses(meses, m) == esperado


def test_regla_31_de_marzo(m):
    # nacido 2023-04-15: al 31-mar-2026 tiene 35 meses -> medio menor todo el año escolar 2026
    assert edad_al_corte("2023-04-15", "2026-10-15") == 35
    assert tramo_por_edad("2023-04-15", "2026-10-15", m) == ("nivel_medio", "medio_menor")
    # en febrero 2027 sigue en el año escolar 2026
    assert tramo_por_edad("2023-04-15", "2027-02-10", m) == ("nivel_medio", "medio_menor")
    # en marzo 2027 pasa al año escolar 2027: 47 meses -> medio mayor
    assert tramo_por_edad("2023-04-15", "2027-03-15", m) == ("nivel_medio", "medio_mayor")
    # nacido después del corte: sala cuna menor, no "sin tramo"
    assert tramo_por_edad("2026-06-01", "2026-10-15", m) == ("sala_cuna", "sala_cuna_menor")


def test_estructura_y_anclas(m):
    assert [t["id"] for t in m.tramos()] == ["sala_cuna", "nivel_medio", "transicion"]
    assert m.niveles("transicion") == list(range(1, 9))
    assert m.nombre_nivel("nivel_medio", 4) == "Afianzando"
    a = m.anclas("sala_cuna")
    assert len(a) == 8 * 4 and all(x["tramo"] == "sala_cuna" for x in a)
    assert {x["id"] for x in a if x["nivel"] == 3} == {"IYA-SC-N03-D", "IYA-SC-N03-C1", "IYA-SC-N03-E1", "IYA-SC-N03-E2"}
    assert "Conducta observable" in m.descripcion_nivel("sala_cuna", 1)


def test_matcher_filtra_por_tramo_y_excluye(m):
    from src.matcher import Matcher
    mt = Matcher(usar_semantico=False, anclas=m.anclas())
    r = mt.matchear("clave3x", top_k=50, umbral=0.0, ratio=0.0, tramo="nivel_medio")
    assert r and all(x.manifestacion["tramo"] == "nivel_medio" for x in r)
    r2 = mt.matchear("clave3x", top_k=50, umbral=0.0, ratio=0.0, tramo="nivel_medio", excluir={"IYA-NM-N03-C1"})
    assert "IYA-NM-N03-C1" not in {x.manifestacion["id"] for x in r2}


def test_clasificador_sin_tramo(m, monkeypatch):
    from src.clasificador_rubrica import ClasificadorRubrica
    from src.matcher import Matcher
    c = ClasificadorRubrica(marco=m, matcher=Matcher(usar_semantico=False, anclas=m.anclas()))
    assert c.clasificar("algo", edad_meses=80)["estado"] == "sin_tramo"
    r = c.clasificar("hoy mostro clave5x en la sala", edad_meses=30)
    assert r["tramo"] == "nivel_medio" and r["nivel"] == 5 and r["nombre_nivel"] == "Integrando"


def test_mm_v2_agrega_reglas_de_la_rubrica(m):
    from src.multimodal.conductas import SYSTEM, system_para
    assert system_para(None) == SYSTEM
    v2 = system_para(m)
    assert "comillas" in v2 and "grado de apoyo" in v2 and "Identidad" not in SYSTEM
    assert "lo que el niño o niña DICE" in v2
