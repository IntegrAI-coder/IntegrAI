import { describe, expect, it } from 'vitest';
import type { FichaNino, ObservacionDetallada } from './consultas';
import type { Manifestacion } from './tipos';
import { estadoManifestaciones, planEstimulacion } from './estimulacion';

function manifestacion(dominio: string, nivel = 3): Manifestacion {
  return { idManifestacion: `M-${dominio}`, nivel, dominio, textoObservable: 'x' };
}

function observacion(manifestaciones: Manifestacion[]): ObservacionDetallada {
  return {
    idObservacion: 'O1',
    fechaObservacion: '2025-01-01',
    formatoCaptura: 'texto',
    nivelEstimado: 3,
    manifestaciones,
  };
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

describe('estadoManifestaciones', () => {
  it('cuenta manifestaciones por dominio y detecta los sin evidencia', () => {
    const f = ficha({
      observaciones: [
        observacion([
          manifestacion('motor_grueso', 3),
          manifestacion('cognitivo', 5),
          manifestacion('cognitivo', 6),
        ]),
      ],
    });
    const estado = estadoManifestaciones(f);
    expect(estado.total).toBe(3);
    const cognitivo = estado.porDominio.find((d) => d.dominio === 'cognitivo');
    expect(cognitivo?.observadas).toBe(2);
    expect(cognitivo?.nivelPromedio).toBe(5.5);
    expect(estado.sinEvidencia).toEqual([
      'motor_fino',
      'lenguaje_comunicacion',
      'socioemocional',
    ]);
  });

  it('sin observaciones, todo queda sin evidencia', () => {
    const estado = estadoManifestaciones(ficha());
    expect(estado.total).toBe(0);
    expect(estado.sinEvidencia).toHaveLength(5);
  });
});

describe('planEstimulacion', () => {
  it('prioriza los dominios sin evidencia', () => {
    const f = ficha({
      observaciones: [
        observacion([manifestacion('motor_grueso'), manifestacion('cognitivo')]),
      ],
    });
    const plan = planEstimulacion(f);
    expect(plan).toHaveLength(3);
    expect(plan.every((p) => p.motivo === 'sin-evidencia')).toBe(true);
    expect(plan.map((p) => p.dominio)).toEqual([
      'motor_fino',
      'lenguaje_comunicacion',
      'socioemocional',
    ]);
    expect(plan[0]?.acciones.length).toBeGreaterThan(0);
  });

  it('con todos los dominios cubiertos, ordena por menor nivel promedio', () => {
    const f = ficha({
      observaciones: [
        observacion([
          manifestacion('motor_grueso', 2),
          manifestacion('motor_fino', 4),
          manifestacion('lenguaje_comunicacion', 6),
          manifestacion('socioemocional', 7),
          manifestacion('cognitivo', 8),
        ]),
      ],
    });
    const plan = planEstimulacion(f);
    expect(plan.every((p) => p.motivo === 'nivel-bajo')).toBe(true);
    expect(plan[0]?.dominio).toBe('motor_grueso');
  });
});
