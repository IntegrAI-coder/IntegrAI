"""Orquestación pública del recomendador referenciado."""
from __future__ import annotations

from typing import Any

from . import normas
from .analisis import edad_meses_decimal
from .contrato import AVISO, Hallazgo, HitoAnalizado, Procedencia, Recomendacion, Sugerencia, Validacion
from .privacidad import prefiltro
from .rag import Indice, Pasaje
from .redactor import cita_desde_pasaje, plantilla
from .validadores import validar_recomendacion


def recomendar(caso: dict[str, Any], indice: Indice | None = None, numero: int = 1) -> Recomendacion | None:
    filtro = prefiltro(caso.get("nota", ""), caso.get("nombres", []))
    base = {"id_recomendacion": f"REC-{numero:05d}", "id_nino": caso["id_nino"],
            "id_jardin": caso["id_jardin"], "sala_grupo": caso["sala_grupo"],
            "estado_revision": "por_verificar", "generado_por": Procedencia(tipo="plantilla_deterministica"),
            "validacion": Validacion(citas_literales=True, numeros_verificados=True, sin_pii=True, requiere_revision_humana=True),
            "aviso": AVISO}
    if filtro.posible_manipulacion:
        return Recomendacion(**base, hito=None,
            hallazgos_deterministicos=[Hallazgo(id="H-1", tipo="posible_manipulacion", regla="PREFILTRO_INYECCION_V1", resultado="La nota contiene instrucciones ajenas a una observación.", observacion_ids=[caso["id_observacion"]])],
            resumen="La nota se separó para revisión manual porque contiene instrucciones que podrían manipular el procesamiento.", sugerencias=[], derivacion_salud=False)
    if not caso.get("hito_id"):
        return _por_nivel(caso, base, indice)
    item = normas.hito(caso["hito_id"])
    edad = edad_meses_decimal(caso["fecha_nacimiento"], caso["fecha_referencia"])
    zona = normas.zona(item, edad)
    estado = caso.get("estado", "sin_registro")
    tipo = "hito_sin_registro" if estado == "sin_registro" else "hito_no_logrado"
    if estado not in {"no_logrado", "sin_registro"}:
        return None
    if estado == "sin_registro" and zona not in {"atencion", "fuera_de_ventana"}:
        return None
    consulta_es, consulta_en = normas.consultas_hito(item.id)
    pasajes = indice.buscar(consulta_es, consulta_en, k=2, max_por_fuente=1) if indice else []
    resumen, sugerencias = plantilla(item.nombre, estado, zona, pasajes, consulta_es + " " + consulta_en)
    hito = HitoAnalizado(id=item.id, estado=estado, zona=zona, edad_meses=round(edad, 2),
                         id_observacion=caso.get("id_observacion") if estado == "no_logrado" else None,
                         cita_observacion=caso.get("cita") if estado == "no_logrado" else None,
                         fecha_observacion=caso.get("fecha_observacion") if estado == "no_logrado" else None)
    hallazgos = [Hallazgo(id="H-1", tipo=tipo, regla="DISPARO_HITO_V1",
                           resultado=f"{item.id}: {estado}; zona {zona}; umbrales por validar.",
                           observacion_ids=[caso["id_observacion"]] if caso.get("id_observacion") else [])]
    nivel = caso.get("nivel")
    if nivel and (nivel.get("alerta_absoluta") or nivel.get("rezago_relativo")):
        hallazgos.append(Hallazgo(id=f"H-{len(hallazgos) + 1}", tipo="nivel", regla="PARIDAD_E1_V1",
                                  resultado=(f"Escala E-1: nivel vigente {nivel['vigente']}, esperado {nivel['esperado']}; "
                                             f"brecha {nivel['vigente'] - nivel['esperado']}; fecha {nivel['fecha']}."),
                                  observacion_ids=nivel.get("observacion_ids", [])))
    curso = caso.get("curso")
    if curso and curso.get("unico_sin_logro"):
        hallazgos.append(Hallazgo(id=f"H-{len(hallazgos) + 1}", tipo="curso", regla="K_MIN_CURSO_5",
                                  resultado=f"Comparación anónima con {curso['k_registrados']} registros: único sin logro registrado.",
                                  observacion_ids=[]))
    rec = Recomendacion(**base, hito=hito, hallazgos_deterministicos=hallazgos,
        resumen=resumen, sugerencias=sugerencias, derivacion_salud=zona == "fuera_de_ventana")
    errores = validar_recomendacion(rec)
    if errores:
        raise ValueError("; ".join(errores))
    return rec


# Páginas PDF de las Bases Curriculares (MINEDUC 2018) con los OA del núcleo Identidad y Autonomía por nivel.
_PAGINAS_IYA = {"sala_cuna": 52, "medio": 53, "transicion": 54}
_NOMBRE_TRAMO = {"sala_cuna": "Sala Cuna", "medio": "Nivel Medio", "transicion": "Transición"}
_CONSULTA_IYA = "preferencias independencia confianza emociones autovalía identidad"


def _tramo(edad_meses: float) -> str | None:
    if edad_meses < 0 or edad_meses >= 72:
        return None
    return "sala_cuna" if edad_meses < 24 else "medio" if edad_meses < 48 else "transicion"


def _pasaje_iya(indice: Indice | None, tramo: str) -> Pasaje | None:
    if indice is None:
        return None
    pagina = _PAGINAS_IYA[tramo]
    candidatos = [f for f in indice.fragmentos if f["fuente_id"] == "MINEDUC-BASES" and int(f["pagina"]) == pagina]
    if not candidatos:
        return None
    frag = max(candidatos, key=lambda f: sum(t in f["texto"].lower() for t in _CONSULTA_IYA.split()))
    fuente = indice.fuentes.get(frag["fuente_id"], {})
    return Pasaje(id="P1", fragmento_id=frag["id"], fuente_id=frag["fuente_id"], titulo=fuente.get("titulo", ""),
                  organizacion=fuente.get("organizacion", ""), anio=fuente.get("anio"), pagina=pagina,
                  url=fuente.get("url", ""), idioma=fuente.get("idioma", ""), texto=frag["texto"], score=1.0)


def _por_nivel(caso: dict[str, Any], base: dict[str, Any], indice: Indice | None) -> Recomendacion | None:
    """Niños/as de 2 a 6 años: los hitos motores OMS no aplican; se propone desde el nivel E-1 de
    Identidad y Autonomía (rezago o estancamiento) con los OA de las Bases Curriculares del tramo."""
    nivel = caso.get("nivel") or {}
    if not (nivel.get("rezago_relativo") or nivel.get("estancamiento")):
        return None
    tramo = _tramo(edad_meses_decimal(caso["fecha_nacimiento"], caso["fecha_referencia"]))
    pasaje = _pasaje_iya(indice, tramo) if tramo else None
    if pasaje is None:
        return None
    if nivel.get("rezago_relativo"):
        resultado = (f"Escala E-1: nivel vigente {nivel['vigente']}, esperado {nivel['esperado']}; "
                     f"brecha {nivel['vigente'] - nivel['esperado']}; fecha {nivel['fecha']}.")
        resumen = ("El nivel registrado en Identidad y Autonomía está bajo lo esperado para su edad; "
                   "se proponen experiencias para fortalecerlo y seguir observando.")
    else:
        resultado = f"Escala E-1: nivel {nivel['vigente']} sin cambios en las últimas observaciones; fecha {nivel['fecha']}."
        resumen = ("El nivel en Identidad y Autonomía se mantiene sin cambios en las últimas observaciones; "
                   "se proponen nuevas experiencias para movilizarlo.")
    texto = ("Ofrecer en la rutina oportunidades para elegir entre opciones, expresar preferencias y emociones, "
             "y hacer por sí mismo/a tareas de autocuidado (vestirse, ordenar, servirse), reconociendo sus logros, "
             f"según los objetivos de Identidad y Autonomía de {_NOMBRE_TRAMO[tramo]}. Registrar los cambios observables.")
    cita = cita_desde_pasaje(pasaje, _CONSULTA_IYA)
    rec = Recomendacion(**base, hito=None,
        hallazgos_deterministicos=[Hallazgo(id="H-1", tipo="nivel", regla="NIVEL_IYA_V1", resultado=resultado,
                                            observacion_ids=nivel.get("observacion_ids", []))],
        resumen=resumen, sugerencias=[Sugerencia(texto=texto, citas=[cita])], derivacion_salud=False)
    errores = validar_recomendacion(rec)
    if errores:
        raise ValueError("; ".join(errores))
    return rec
