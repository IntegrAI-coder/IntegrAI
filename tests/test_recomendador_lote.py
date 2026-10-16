import json
from pathlib import Path
from src.recomendador.lote import generar


def test_reproducible_salvo_fecha_y_cubre_hallazgos():
    a=generar(generado_en="A").model_dump(mode="json")
    b=generar(generado_en="B").model_dump(mode="json")
    a.pop("generado_en"); b.pop("generado_en")
    assert a == b
    tipos={h["tipo"] for i in a["items"] for h in i["hallazgos_deterministicos"]}
    assert {"hito_no_logrado","hito_sin_registro","nivel","posible_manipulacion"} <= tipos


def test_solo_ids_existentes_y_contrato_publico():
    ninos={line.split(',')[0] for line in Path('data/ninos.csv').read_text(encoding='utf-8').splitlines()[1:]}
    # + el curso demo del equipo (JAR-EQUIPO), que vive en la BD y no en el CSV sintético
    ninos |= {c['id_nino'] for c in json.loads(Path('datos_sinteticos/recomendador/casos_equipo.json').read_text(encoding='utf-8'))['casos']}
    lote=generar(generado_en="A")
    assert all(i.id_nino in ninos for i in lote.items)
    assert all(len(c.fragmento)<=300 for i in lote.items for s in i.sugerencias for c in s.citas)


def test_curso_equipo_por_nivel_sin_derivacion_y_con_cita_mineduc():
    import pytest
    from src.recomendador.rag import cargar_indice, cargar_manifiesto
    if cargar_indice(manifiesto=cargar_manifiesto()) is None:
        pytest.skip("sin índice RAG local (privado/rag/indice.json)")
    lote=generar(generado_en="A")
    eq=[i for i in lote.items if i.id_jardin=="JAR-EQUIPO"]
    assert eq and all(i.hito is None and not i.derivacion_salud for i in eq)
    assert all(c.fuente_id=="MINEDUC-BASES" and c.pagina_pdf in (52, 53, 54) for i in eq for s in i.sugerencias for c in s.citas)
