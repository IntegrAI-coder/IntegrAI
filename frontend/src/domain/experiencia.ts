import type { Datos } from '../data/cargar';
import type { Nino, Observacion } from './tipos';
import type { FichaNino } from './consultas';

export interface DominioInfo {
  id: string;
  nombre: string;
}

export const DOMINIOS: DominioInfo[] = [
  { id: 'motor_grueso', nombre: 'Motor grueso' },
  { id: 'motor_fino', nombre: 'Motor fino' },
  { id: 'lenguaje_comunicacion', nombre: 'Lenguaje y comunicación' },
  { id: 'socioemocional', nombre: 'Socioemocional' },
  { id: 'cognitivo', nombre: 'Cognitivo' },
];

export function nombreDominio(id: string): string {
  return DOMINIOS.find((d) => d.id === id)?.nombre ?? id;
}

/** Dominios con al menos una manifestación observada en la ficha. */
export function dominiosCubiertos(ficha: FichaNino): string[] {
  const observados = new Set<string>();
  for (const obs of ficha.observaciones) {
    for (const man of obs.manifestaciones) {
      observados.add(man.dominio);
    }
  }
  return DOMINIOS.map((d) => d.id).filter((id) => observados.has(id));
}

/** Dominios del marco sin evidencia registrada todavía. */
export function dominiosFaltantes(ficha: FichaNino): string[] {
  const cubiertos = new Set(dominiosCubiertos(ficha));
  return DOMINIOS.map((d) => d.id).filter((id) => !cubiertos.has(id));
}

export type EstadoAcompanamiento = 'sin-datos' | 'alerta' | 'observar' | 'al-dia';

export interface Diagnostico {
  estado: EstadoAcompanamiento;
  titulo: string;
  detalle: string;
}

/** Lectura en palabras del nivel del niño/a, para decidir el acompañamiento. */
export function diagnostico(ficha: FichaNino): Diagnostico {
  if (ficha.observaciones.length === 0) {
    return {
      estado: 'sin-datos',
      titulo: 'Sin observaciones todavía',
      detalle:
        'Aún no hay registros para este niño/a. Registra una observación para situar su nivel.',
    };
  }
  const brecha = ficha.brecha ?? 0;
  if (ficha.alerta) {
    return {
      estado: 'alerta',
      titulo: 'Necesita apoyo',
      detalle: `Su nivel actual (${ficha.nivelVigente}) está ${Math.abs(brecha)} por debajo de lo esperado para su edad (${ficha.nivelEsperado}). Prioriza el acompañamiento.`,
    };
  }
  if (brecha < 0) {
    return {
      estado: 'observar',
      titulo: 'Un poco por debajo',
      detalle: `Está ${Math.abs(brecha)} nivel por debajo de lo esperado (${ficha.nivelEsperado}). Conviene observarlo con atención.`,
    };
  }
  return {
    estado: 'al-dia',
    titulo: 'Al día',
    detalle:
      'Su nivel está en línea con lo esperado para su edad. Mantén el registro para sostener la trayectoria.',
  };
}

export interface ResumenTrayectorias {
  avanzan: number;
  planos: number;
  retroceden: number;
  sinSeguimiento: number;
  conSeguimiento: number;
}

/** Cuántos niños/as avanzan, se mantienen o retroceden entre su primera y última observación. */
export function resumenTrayectorias(
  datos: Datos,
  ninos: Nino[] = datos.ninos,
): ResumenTrayectorias {
  const porNino = new Map<string, Observacion[]>();
  for (const obs of datos.observaciones) {
    const lista = porNino.get(obs.idNino) ?? [];
    lista.push(obs);
    porNino.set(obs.idNino, lista);
  }

  let avanzan = 0;
  let planos = 0;
  let retroceden = 0;
  let sinSeguimiento = 0;

  for (const nino of ninos) {
    const observaciones = porNino.get(nino.idNino) ?? [];
    if (observaciones.length < 2) {
      sinSeguimiento += 1;
      continue;
    }
    const ordenadas = [...observaciones].sort((a, b) =>
      a.fechaObservacion.localeCompare(b.fechaObservacion),
    );
    const primera = ordenadas[0];
    const ultima = ordenadas[ordenadas.length - 1];
    if (!primera || !ultima) {
      sinSeguimiento += 1;
      continue;
    }
    const delta = ultima.nivelEstimado - primera.nivelEstimado;
    if (delta > 0) {
      avanzan += 1;
    } else if (delta < 0) {
      retroceden += 1;
    } else {
      planos += 1;
    }
  }

  const conSeguimiento = avanzan + planos + retroceden;
  return { avanzan, planos, retroceden, sinSeguimiento, conSeguimiento };
}
