import { describe, it, expect } from 'vitest';
import {
  edadMeses,
  nivelEsperado,
  brecha,
  tieneAlerta,
  observacionMasReciente,
  nivelVigente,
  promedio,
  UMBRAL_ALERTA,
} from './metrics';
import type { Nivel, Observacion } from './tipos';

const niveles: Nivel[] = [
  { nivel: 1, nombreNivel: 'N1', edadMinMeses: 0, edadMaxMeses: 2, descripcion: '' },
  { nivel: 2, nombreNivel: 'N2', edadMinMeses: 2, edadMaxMeses: 4, descripcion: '' },
  { nivel: 6, nombreNivel: 'N6', edadMinMeses: 12, edadMaxMeses: 18, descripcion: '' },
  { nivel: 9, nombreNivel: 'N9', edadMinMeses: 27, edadMaxMeses: 36, descripcion: '' },
];

function obs(id: string, fecha: string, nivel: number): Observacion {
  return {
    idObservacion: id,
    idNino: 'NINO-00001',
    fechaObservacion: fecha,
    formatoCaptura: 'texto',
    nivelEstimado: nivel,
  };
}

describe('edadMeses', () => {
  it('calcula meses completos', () => {
    expect(edadMeses('2024-01-01', new Date('2025-01-01'))).toBe(12);
  });

  it('resta un mes si no se cumplió el día', () => {
    expect(edadMeses('2024-01-15', new Date('2025-01-10'))).toBe(11);
  });

  it('nunca es negativa', () => {
    expect(edadMeses('2025-06-01', new Date('2025-01-01'))).toBe(0);
  });
});

describe('nivelEsperado', () => {
  it('ubica la edad en el rango correcto (min inclusivo, max exclusivo)', () => {
    expect(nivelEsperado(0, niveles)).toBe(1);
    expect(nivelEsperado(2, niveles)).toBe(2);
    expect(nivelEsperado(14, niveles)).toBe(6);
  });

  it('devuelve el último nivel si supera el rango máximo', () => {
    expect(nivelEsperado(40, niveles)).toBe(9);
  });

  it('devuelve null si no hay rango que la contenga', () => {
    expect(nivelEsperado(5, niveles)).toBeNull();
  });
});

describe('brecha', () => {
  it('resta nivel vigente menos esperado', () => {
    expect(brecha(5, 7)).toBe(-2);
    expect(brecha(8, 6)).toBe(2);
  });

  it('es null si falta algún dato', () => {
    expect(brecha(null, 7)).toBeNull();
    expect(brecha(5, null)).toBeNull();
  });
});

describe('tieneAlerta', () => {
  it('alerta cuando la brecha alcanza el umbral', () => {
    expect(tieneAlerta(UMBRAL_ALERTA)).toBe(true);
    expect(tieneAlerta(-3)).toBe(true);
  });

  it('no alerta sobre el umbral ni con null', () => {
    expect(tieneAlerta(-1)).toBe(false);
    expect(tieneAlerta(0)).toBe(false);
    expect(tieneAlerta(null)).toBe(false);
  });
});

describe('observacionMasReciente y nivelVigente', () => {
  const observaciones = [
    obs('OBS-1', '2025-01-01', 3),
    obs('OBS-2', '2025-06-01', 5),
    obs('OBS-3', '2025-03-01', 4),
  ];

  it('toma la de fecha más reciente', () => {
    expect(observacionMasReciente(observaciones)?.idObservacion).toBe('OBS-2');
    expect(nivelVigente(observaciones)).toBe(5);
  });

  it('devuelve null sin observaciones', () => {
    expect(observacionMasReciente([])).toBeNull();
    expect(nivelVigente([])).toBeNull();
  });
});

describe('promedio', () => {
  it('promedia los valores', () => {
    expect(promedio([2, 4, 6])).toBe(4);
  });

  it('es null para lista vacía', () => {
    expect(promedio([])).toBeNull();
  });
});
