import type { Datos } from '../data/cargar';
import { tieneAccesoNino } from './acceso';
import type { Pendiente, Profesora } from './tipos';

const ESCALA_MARGEN = 0.6;
const TOTAL_UINT32 = 0x1_0000_0000;
const MAX_OBSERVACIONES = 12;

export function fnv1a32(texto: string): number {
  let hash = 0x811c9dc5;
  for (let indice = 0; indice < texto.length; indice += 1) {
    hash ^= texto.charCodeAt(indice);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash;
}

export function margenDemo(idObservacion: string): number {
  return (fnv1a32(idObservacion) / TOTAL_UINT32) * ESCALA_MARGEN;
}

export function generarPendientesDemo(datos: Datos, profesora: Profesora): Pendiente[] {
  const ninosPorId = new Map(datos.ninos.map((nino) => [nino.idNino, nino]));
  return datos.observaciones
    .filter((observacion) => {
      const nino = ninosPorId.get(observacion.idNino);
      return nino ? tieneAccesoNino(profesora, nino) : false;
    })
    .sort(
      (a, b) =>
        b.fechaObservacion.localeCompare(a.fechaObservacion) ||
        a.idObservacion.localeCompare(b.idObservacion),
    )
    .slice(0, MAX_OBSERVACIONES)
    .map((observacion) => ({ observacion, margen: margenDemo(observacion.idObservacion) }))
    .filter(({ margen }) => margen < 0.15)
    .map(({ observacion, margen }) => {
      const nino = ninosPorId.get(observacion.idNino);
      return {
        idPendiente: `DEMO-${observacion.idObservacion}`,
        idNinoPropuesto: observacion.idNino,
        idEducadora: profesora.idEducadora,
        nivelPropuesto: observacion.nivelEstimado,
        dominio: null,
        margen,
        motivo: 'Clasificación bajo el umbral',
        evidencia: '',
        estado: 'por_verificar',
        creadoEn: observacion.fechaObservacion,
        idJardin: nino?.idJardin ?? null,
        salaGrupo: nino?.salaGrupo ?? null,
      };
    });
}
