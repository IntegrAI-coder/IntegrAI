"""Orquestador end-to-end del agente IntegraAI (desafío E-1).

    WhatsApp (nota · foto · audio · video)
      -> Procesador        (transcribe / describe -> texto)
      -> Clasificador      (matcher -> manifestaciones -> nivel 1-9, decisión tipada)
      -> Plataforma        (guarda observación + vínculos de evidencia)
      -> Redacción (LLM)   (mensaje cálido + alerta si hay rezago)
      -> WhatsApp          (respuesta a la tía)

El "0 horas": la tía manda la evidencia por WhatsApp y el sistema hace el resto.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from . import config, marco
from .bedrock import GatewayModelos
from .clasificador import Clasificador
from .plataforma import Plataforma
from .procesadores import Entrada, Procesador
from .whatsapp import Canal, MensajeEntrante, crear_canal


class AgenteIntegra:
    def __init__(self, canal: Canal | None = None, plataforma: Plataforma | None = None,
                 gateway: GatewayModelos | None = None, clasificador: Clasificador | None = None) -> None:
        self.gateway = gateway or GatewayModelos()
        self.procesador = Procesador()
        self.clasificador = clasificador or Clasificador()
        self.plataforma = plataforma or Plataforma()
        self.canal = canal or crear_canal(config.WHATSAPP_CANAL)

    # ------------------------------------------------------------------
    def _redactar(self, msg: MensajeEntrante, clas: dict, tray: dict | None) -> str:
        nivel = clas.get("nivel")
        nombre = clas.get("nombre_nivel") or "—"
        doms = ", ".join(marco.nombre_dominio(d) for d in clas.get("dominios", [])) or "sin dominios claros"
        linea_nivel = f"📊 Nivel estimado: **{nivel} · {nombre}**" if nivel else "📊 Aún no hay evidencia suficiente para estimar el nivel."
        alerta = ""
        if clas.get("alerta_rezago"):
            alerta = "\n⚠️ Alerta: el nivel observado está por debajo de la banda esperada para la edad. Vale la pena reforzar."
        prompt = (
            "Eres un asistente que ayuda a educadoras de párvulos de Fundación Integra. "
            "Redacta un mensaje cálido de WhatsApp (máx. 90 palabras) confirmando que se registró la observación. "
            "Incluye el nivel estimado y los dominios, en tono cercano y sin tecnicismos.\n"
            f"Niño/a: {msg.id_nino}\nNivel: {nivel} ({nombre})\nDominios: {doms}\nAlerta: {'sí' if clas.get('alerta_rezago') else 'no'}"
        )
        if self.gateway.disponible:
            try:
                return self.gateway.generar(prompt, tarea="razonamiento").texto
            except Exception:
                pass
        # plantilla determinista (MOCK)
        extra = ""
        if tray and tray.get("nivel_actual") and tray.get("n_observaciones", 0) > 1:
            extra = f"\n📈 Su trayectoria va en nivel {tray['nivel_actual']} ({tray.get('tendencia')}), con {tray['n_observaciones']} observaciones."
        return (f"¡Hola! 👋 Registré la observación de {msg.id_nino}. ¡Gracias por documentarla!\n\n"
                f"{linea_nivel}\n🎯 Dominios con evidencia: {doms}.{alerta}{extra}\n\n"
                f"Todo quedó guardado en la plataforma. ✔️")

    # ------------------------------------------------------------------
    def procesar_mensaje(self, msg: MensajeEntrante) -> dict[str, Any]:
        fecha = msg.ts or date.today().isoformat()
        entradas = list(msg.adjuntos)
        if msg.texto:
            entradas.insert(0, Entrada(tipo="texto", ref="mensaje", pie=msg.texto))

        texto, detalle = self.procesador.procesar(entradas)

        nin = self.plataforma.nino(msg.id_nino) if msg.id_nino else None
        edad = marco.edad_meses(nin["fecha_nacimiento"], fecha) if (nin and nin.get("fecha_nacimiento")) else None

        clas = self.clasificador.clasificar(texto, edad)
        cdict = clas.to_dict()

        oid = None
        if msg.id_nino:
            oid = self.plataforma.registrar_observacion(
                id_nino=msg.id_nino, id_educadora=msg.id_educadora, fecha=fecha,
                formato=msg.formato, nivel=clas.nivel, nota=texto,
                dominios=clas.dominios, manifestaciones=[m.manifestacion["id"] for m in clas.matches],
                confianza=clas.confianza, origen="whatsapp")

        tray = self.plataforma.trayectoria(msg.id_nino) if msg.id_nino else None
        respuesta = self._redactar(msg, cdict, tray)
        self.canal.responder(msg.de, respuesta)

        return {"ok": True, "observacion_id": oid, "texto": texto, "detalle": detalle,
                "clasificacion": cdict, "trayectoria": tray, "respuesta": respuesta}
