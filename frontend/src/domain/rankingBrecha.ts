import type { Datos } from '../data/cargar';
import type { Nino } from './tipos';
import { fichaNino } from './consultas';

/** Una fila del ranking de brecha. `diferencia` = nivel actual − nivel esperado
 *  (negativa = déficit), idéntica a la "Diferencia" de la ficha del niño/a.
 *  `brecha` es la MAGNITUD del déficit (= -diferencia cuando es negativa; 0 si no
 *  hay déficit), el valor por el que se ordena de mayor a menor. */
export interface FilaRankingBrecha {
  idNino: string;
  /** Identificador sintético (= idNino); el repositorio es público, sin PII. */
  nombreVisible: string;
  edadMeses: number;
  nivelEsperado: number | null;
  nivelActual: number | null;
  /** Nivel actual − nivel esperado (coincide con la "Diferencia" de la ficha). */
  diferencia: number | null;
  /** Magnitud del déficit: max(0, -diferencia); null si no es evaluable. */
  brecha: number | null;
  nObservaciones: number;
  /** Lectura breve: por qué está (o no) en el ranking. */
  razon: string;
}

export interface OpcionesRankingBrecha {
  /** Mínimo de observaciones para medir brecha. Por defecto 1 (basta una para
   *  tener nivel actual). Quienes no cumplen van al final con nota. */
  minObservaciones?: number;
  hoy?: Date;
}

const RAZON_SIN_DATOS = 'Sin observaciones suficientes para medir brecha';

function pluralNiveles(n: number): string {
  return n === 1 ? '1 nivel' : `${n} niveles`;
}

function razonRankeable(brecha: number): string {
  if (brecha <= 0) {
    return 'En el nivel esperado para su edad';
  }
  return `${pluralNiveles(brecha)} bajo lo esperado para su edad`;
}

/** Construye el ranking de brecha de una lista de niños/as YA ACOTADA al alcance
 *  (quien llama aplica `ninosEnAlcance`). Reutiliza `fichaNino`, la misma cadena de
 *  cálculo que la ficha del niño/a y la tabla de curso, de modo que la columna
 *  `diferencia` coincide con la "Diferencia" que ve el usuario.
 *
 *  Orden: los rankeables primero, por `diferencia` ASCENDENTE (más negativa =
 *  más rezagado primero) y, a igual diferencia, por `idNino` ascendente (estable).
 *  Los no evaluables (sin observaciones suficientes) van al final. Función pura:
 *  no muta `datos` ni `ninos`. */
export function rankingBrecha(
  datos: Datos,
  ninos: Nino[],
  opciones?: OpcionesRankingBrecha,
): FilaRankingBrecha[] {
  const minObservaciones = opciones?.minObservaciones ?? 1;
  const hoy = opciones?.hoy ?? new Date();

  const filas: FilaRankingBrecha[] = [];
  for (const nino of ninos) {
    const ficha = fichaNino(datos, nino.idNino, hoy);
    if (!ficha) {
      continue;
    }
    const nObservaciones = ficha.observaciones.length;
    const evaluable =
      nObservaciones >= minObservaciones &&
      ficha.nivelVigente !== null &&
      ficha.nivelEsperado !== null &&
      ficha.brecha !== null;

    if (evaluable) {
      const diferencia = ficha.brecha as number;
      filas.push({
        idNino: nino.idNino,
        nombreVisible: nino.idNino,
        edadMeses: ficha.edadMeses,
        nivelEsperado: ficha.nivelEsperado,
        nivelActual: ficha.nivelVigente,
        diferencia,
        brecha: Math.max(0, -diferencia),
        nObservaciones,
        razon: razonRankeable(Math.max(0, -diferencia)),
      });
    } else {
      filas.push({
        idNino: nino.idNino,
        nombreVisible: nino.idNino,
        edadMeses: ficha.edadMeses,
        nivelEsperado: ficha.nivelEsperado,
        nivelActual: ficha.nivelVigente,
        diferencia: null,
        brecha: null,
        nObservaciones,
        razon: RAZON_SIN_DATOS,
      });
    }
  }

  return filas.sort((a, b) => {
    const aEvaluable = a.diferencia !== null;
    const bEvaluable = b.diferencia !== null;
    if (aEvaluable !== bEvaluable) {
      return aEvaluable ? -1 : 1;
    }
    if (aEvaluable && bEvaluable) {
      const porDiferencia = (a.diferencia as number) - (b.diferencia as number);
      if (porDiferencia !== 0) {
        return porDiferencia;
      }
    }
    return a.idNino.localeCompare(b.idNino);
  });
}
