import type { FichaNino } from './consultas';
import { DOMINIOS, dominiosCubiertos, nombreDominio } from './experiencia';

/** Una acción concreta de estimulación para la sala, redactada para la parvularia. */
export interface AccionEstimulo {
  titulo: string;
  detalle: string;
}

/** Lectura del catálogo de manifestaciones observadas para un niño/a, por dominio. */
export interface EstadoDominio {
  dominio: string;
  nombre: string;
  observadas: number;
  nivelPromedio: number | null;
}

export interface EstadoManifestaciones {
  total: number;
  porDominio: EstadoDominio[];
  sinEvidencia: string[];
}

export interface PlanEstimulo {
  dominio: string;
  nombre: string;
  motivo: 'sin-evidencia' | 'nivel-bajo';
  acciones: AccionEstimulo[];
}

/** Acciones de estimulación sugeridas por dominio de desarrollo (lenguaje cercano,
 *  sin diagnosticar: son ideas para la experiencia cotidiana de la sala). */
export const ACCIONES_POR_DOMINIO: Record<string, AccionEstimulo[]> = {
  motor_grueso: [
    {
      titulo: 'Circuitos de movimiento',
      detalle: 'Armar un recorrido con conos, aros y líneas para saltar, trepar y equilibrarse.',
    },
    {
      titulo: 'Juegos de equilibrio',
      detalle: 'Caminar sobre una línea, mantenerse en un pie y pasar obstáculos bajos.',
    },
    {
      titulo: 'Pelota y coordinación',
      detalle: 'Lanzar, patear y atrapar una pelota de tamaño medio a distancias cortas.',
    },
  ],
  motor_fino: [
    {
      titulo: 'Pinza y traslado',
      detalle: 'Trasladar porotos, tapas o bloques con dos dedos entre recipientes.',
    },
    {
      titulo: 'Enhebrado y ensartado',
      detalle: 'Ensartar cuentas grandes en un cordón o pasar cintas por agujeros.',
    },
    {
      titulo: 'Trazo y dibujo',
      detalle: 'Garabatear con crayones gruesos, rellenar y seguir líneas simples.',
    },
  ],
  lenguaje_comunicacion: [
    {
      titulo: 'Ronda de conversación',
      detalle: 'Describir láminas y nombrar objetos, acciones y personas.',
    },
    {
      titulo: 'Cuentos y preguntas',
      detalle: 'Leer un cuento corto y preguntar qué pasó, quién y dónde.',
    },
    {
      titulo: 'Juegos de sonidos',
      detalle: 'Rimas, canciones y adivinanzas para ampliar vocabulario y escucha.',
    },
  ],
  socioemocional: [
    {
      titulo: 'Juego de turnos',
      detalle: 'Juegos simples de compartir materiales y esperar el turno.',
    },
    {
      titulo: 'Nombrar emociones',
      detalle: 'Reconocer y nombrar emociones con caras, cuentos o títeres.',
    },
    {
      titulo: 'Rutinas de cooperación',
      detalle: 'Tareas de ayuda en la sala: repartir, guardar y ordenar en grupo.',
    },
  ],
  cognitivo: [
    {
      titulo: 'Clasificar y comparar',
      detalle: 'Agrupar objetos por color, forma o tamaño y comparar cantidades.',
    },
    {
      titulo: 'Series y patrones',
      detalle: 'Continuar secuencias simples de colores o formas.',
    },
    {
      titulo: 'Conteo y memoria',
      detalle: 'Contar hasta cinco objetos y juegos de memoria con parejas.',
    },
  ],
};

/** Estado del catálogo de manifestaciones para un niño/a: cuántas se observaron y
 *  en qué dominios, para que la parvularia vea qué evidencia existe y qué falta. */
export function estadoManifestaciones(ficha: FichaNino): EstadoManifestaciones {
  const nivelesPorDominio = new Map<string, number[]>();
  for (const obs of ficha.observaciones) {
    for (const man of obs.manifestaciones) {
      const niveles = nivelesPorDominio.get(man.dominio) ?? [];
      niveles.push(man.nivel);
      nivelesPorDominio.set(man.dominio, niveles);
    }
  }

  const porDominio: EstadoDominio[] = DOMINIOS.map((d) => {
    const niveles = nivelesPorDominio.get(d.id) ?? [];
    const nivelPromedio =
      niveles.length > 0 ? niveles.reduce((a, b) => a + b, 0) / niveles.length : null;
    return {
      dominio: d.id,
      nombre: d.nombre,
      observadas: niveles.length,
      nivelPromedio,
    };
  });

  const total = porDominio.reduce((suma, d) => suma + d.observadas, 0);
  const sinEvidencia = porDominio.filter((d) => d.observadas === 0).map((d) => d.dominio);

  return { total, porDominio, sinEvidencia };
}

/** Plan de estimulación para un niño/a: prioriza los dominios SIN evidencia y, luego,
 *  los de menor nivel promedio. Devuelve hasta `max` focos con acciones concretas. */
export function planEstimulacion(ficha: FichaNino, max = 3): PlanEstimulo[] {
  const estado = estadoManifestaciones(ficha);
  const cubiertos = new Set(dominiosCubiertos(ficha));

  const sinEvidencia: PlanEstimulo[] = estado.porDominio
    .filter((d) => !cubiertos.has(d.dominio))
    .map((d) => ({
      dominio: d.dominio,
      nombre: nombreDominio(d.dominio),
      motivo: 'sin-evidencia' as const,
      acciones: ACCIONES_POR_DOMINIO[d.dominio] ?? [],
    }));

  const nivelBajo: PlanEstimulo[] = estado.porDominio
    .filter((d) => cubiertos.has(d.dominio))
    .sort((a, b) => (a.nivelPromedio ?? 0) - (b.nivelPromedio ?? 0))
    .map((d) => ({
      dominio: d.dominio,
      nombre: nombreDominio(d.dominio),
      motivo: 'nivel-bajo' as const,
      acciones: ACCIONES_POR_DOMINIO[d.dominio] ?? [],
    }));

  return [...sinEvidencia, ...nivelBajo].slice(0, max);
}
