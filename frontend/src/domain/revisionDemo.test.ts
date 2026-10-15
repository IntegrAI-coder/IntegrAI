import { describe, expect, it } from 'vitest';
import type { Datos } from '../data/cargar';
import { generarPendientesDemo, margenDemo } from './revisionDemo';
import type { Observacion, Profesora } from './tipos';

const profesora: Profesora = {
  idEducadora: 'EDU-1',
  telefono: '56900000001',
  cursos: [{ idJardin: 'JAR-1', salaGrupo: 'Sala A' }],
};

function idConMargen(prefijo: string, condicion: (margen: number) => boolean): string {
  for (let indice = 0; indice < 10_000; indice += 1) {
    const id = `${prefijo}-${indice.toString().padStart(4, '0')}`;
    if (condicion(margenDemo(id))) {
      return id;
    }
  }
  throw new Error('No se encontró un id con el margen requerido');
}

function datosCon(observaciones: Observacion[]): Datos {
  return {
    educadoras: [],
    niveles: [],
    jardines: [],
    ninos: [
      { idNino: 'PROPIO', fechaNacimiento: '', fechaIngreso: '', idJardin: 'JAR-1', salaGrupo: 'Sala A' },
      { idNino: 'AJENO', fechaNacimiento: '', fechaIngreso: '', idJardin: 'JAR-1', salaGrupo: 'Sala B' },
    ],
    observaciones,
    manifestaciones: [],
    observacionManifestaciones: [],
  };
}

function observacion(
  idObservacion: string,
  fechaObservacion: string,
  idNino = 'PROPIO',
): Observacion {
  return {
    idObservacion,
    idNino,
    fechaObservacion,
    formatoCaptura: 'texto',
    nivelEstimado: 4,
  };
}

describe('margen demo FNV-1a', () => {
  it('es determinista y siempre queda en [0, 0.6)', () => {
    const ids = Array.from({ length: 100 }, (_, indice) => `OBS-${indice}`);
    const primera = ids.map(margenDemo);
    expect(ids.map(margenDemo)).toEqual(primera);
    expect(primera.every((margen) => margen >= 0 && margen < 0.6)).toBe(true);
  });
});

describe('pendientes demo', () => {
  it('solo incluye observaciones de cursos propios bajo el umbral', () => {
    const bajaPropia = idConMargen('BAJA-PROPIA', (margen) => margen < 0.15);
    const bajaAjena = idConMargen('BAJA-AJENA', (margen) => margen < 0.15);
    const altaPropia = idConMargen('ALTA-PROPIA', (margen) => margen >= 0.15);
    const pendientes = generarPendientesDemo(
      datosCon([
        observacion(bajaPropia, '2026-01-03'),
        observacion(bajaAjena, '2026-01-02', 'AJENO'),
        observacion(altaPropia, '2026-01-01'),
      ]),
      profesora,
    );

    expect(pendientes).toHaveLength(1);
    expect(pendientes[0]).toMatchObject({
      idPendiente: `DEMO-${bajaPropia}`,
      idNinoPropuesto: 'PROPIO',
      idEducadora: 'EDU-1',
      nivelPropuesto: 4,
      idJardin: 'JAR-1',
      salaGrupo: 'Sala A',
      creadoEn: '2026-01-03',
    });
    expect(pendientes[0]?.margen).toBe(margenDemo(bajaPropia));
  });

  it('evalúa como máximo las doce observaciones propias más recientes', () => {
    const recientesAltas = Array.from({ length: 12 }, (_, indice) => {
      const id = idConMargen(`ALTA-${indice}`, (margen) => margen >= 0.15);
      return observacion(id, `2026-02-${(indice + 1).toString().padStart(2, '0')}`);
    });
    const antiguaBaja = observacion(
      idConMargen('ANTIGUA-BAJA', (margen) => margen < 0.15),
      '2025-01-01',
    );

    expect(
      generarPendientesDemo(datosCon([...recientesAltas, antiguaBaja]), profesora),
    ).toEqual([]);
  });

  it('usa el id como desempate estable al seleccionar observaciones recientes', () => {
    const observaciones = Array.from({ length: 13 }, (_, indice) =>
      observacion(`EMPATE-${indice.toString().padStart(2, '0')}`, '2026-03-01'),
    );
    const pendientes = generarPendientesDemo(datosCon(observaciones), profesora);
    expect(pendientes.some((p) => p.idPendiente === 'DEMO-EMPATE-12')).toBe(false);
    expect(pendientes.every((p) => (p.margen ?? 1) < 0.15)).toBe(true);
  });
});
