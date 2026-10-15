import { describe, expect, it } from 'vitest';
import type { Datos } from '../data/cargar';
import type { FichaNino, ObservacionDetallada } from './consultas';
import type { Manifestacion, Nino, Observacion } from './tipos';
import {
  dominiosCubiertos,
  dominiosFaltantes,
  diagnostico,
  resumenTrayectorias,
} from './experiencia';

function manifestacion(dominio: string): Manifestacion {
  return { idManifestacion: `M-${dominio}`, nivel: 3, dominio, textoObservable: 'x' };
}

function ficha(parcial: Partial<FichaNino> = {}): FichaNino {
  return {
    nino: {
      idNino: 'N1',
      fechaNacimiento: '2024-01-01',
      idJardin: 'J1',
      salaGrupo: 'A',
      fechaIngreso: '2024-02-01',
    },
    edadMeses: 12,
    nivelVigente: 3,
    nivelEsperado: 3,
    brecha: 0,
    alerta: false,
    rezagoRelativo: false,
    observaciones: [],
    ...parcial,
  };
}

function obsFicha(nivel = 3): ObservacionDetallada {
  return {
    idObservacion: 'O1',
    fechaObservacion: '2025-01-01',
    formatoCaptura: 'texto',
    nivelEstimado: nivel,
    manifestaciones: [],
  };
}

describe('dominiosCubiertos / dominiosFaltantes', () => {
  it('deduce los dominios observados y los que faltan', () => {
    const f = ficha({
      observaciones: [
        {
          idObservacion: 'O1',
          fechaObservacion: '2025-01-01',
          formatoCaptura: 'texto',
          nivelEstimado: 3,
          manifestaciones: [manifestacion('motor_grueso'), manifestacion('cognitivo')],
        },
      ],
    });
    expect(dominiosCubiertos(f)).toEqual(['motor_grueso', 'cognitivo']);
    expect(dominiosFaltantes(f)).toEqual([
      'motor_fino',
      'lenguaje_comunicacion',
      'socioemocional',
    ]);
  });

  it('sin observaciones, todos los dominios faltan', () => {
    expect(dominiosCubiertos(ficha())).toEqual([]);
    expect(dominiosFaltantes(ficha())).toHaveLength(5);
  });
});

describe('diagnostico', () => {
  it('sin observaciones', () => {
    expect(diagnostico(ficha()).estado).toBe('sin-datos');
  });

  it('con brecha crítica exige apoyo', () => {
    expect(
      diagnostico(
        ficha({
          alerta: true,
          nivelVigente: 1,
          nivelEsperado: 4,
          brecha: -3,
          observaciones: [obsFicha(1)],
        }),
      ).estado,
    ).toBe('alerta');
  });

  it('levemente por debajo, a observar', () => {
    expect(
      diagnostico(
        ficha({ nivelVigente: 2, nivelEsperado: 3, brecha: -1, observaciones: [obsFicha(2)] }),
      ).estado,
    ).toBe('observar');
  });

  it('en línea con lo esperado', () => {
    expect(diagnostico(ficha({ brecha: 0, observaciones: [obsFicha(3)] })).estado).toBe('al-dia');
    expect(diagnostico(ficha({ brecha: 1, observaciones: [obsFicha(4)] })).estado).toBe('al-dia');
  });
});

function nino(id: string): Nino {
  return {
    idNino: id,
    fechaNacimiento: '2024-01-01',
    idJardin: 'J1',
    salaGrupo: 'A',
    fechaIngreso: '2024-02-01',
  };
}

function obs(id: string, idNino: string, fecha: string, nivel: number): Observacion {
  return { idObservacion: id, idNino, fechaObservacion: fecha, formatoCaptura: 'texto', nivelEstimado: nivel };
}

function datos(ninos: Nino[], observaciones: Observacion[]): Datos {
  return {
    niveles: [],
    jardines: [],
    ninos,
    observaciones,
    manifestaciones: [],
    observacionManifestaciones: [],
  };
}

describe('resumenTrayectorias', () => {
  it('clasifica avance, estancamiento, retroceso y falta de seguimiento', () => {
    const ninos = [nino('N1'), nino('N2'), nino('N3'), nino('N4')];
    const observaciones = [
      obs('O1', 'N1', '2025-01-01', 2),
      obs('O2', 'N1', '2025-06-01', 4),
      obs('O3', 'N2', '2025-01-01', 3),
      obs('O4', 'N2', '2025-06-01', 3),
      obs('O5', 'N3', '2025-01-01', 5),
      obs('O6', 'N4', '2025-01-01', 5),
      obs('O7', 'N4', '2025-06-01', 4),
    ];
    const r = resumenTrayectorias(datos(ninos, observaciones));
    expect(r).toEqual({
      avanzan: 1,
      planos: 1,
      retroceden: 1,
      sinSeguimiento: 1,
      conSeguimiento: 3,
    });
  });

  it('puede restringirse a un subconjunto de niños', () => {
    const ninos = [nino('N1'), nino('N2')];
    const observaciones = [
      obs('O1', 'N1', '2025-01-01', 2),
      obs('O2', 'N1', '2025-06-01', 4),
      obs('O3', 'N2', '2025-01-01', 3),
      obs('O4', 'N2', '2025-06-01', 3),
    ];
    const r = resumenTrayectorias(datos(ninos, observaciones), [nino('N2')]);
    expect(r.avanzan).toBe(0);
    expect(r.planos).toBe(1);
    expect(r.sinSeguimiento).toBe(0);
  });
});
