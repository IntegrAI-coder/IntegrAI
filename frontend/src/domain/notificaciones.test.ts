import { describe, expect, it } from 'vitest';
import { notificacionesDesdePendientes } from './notificaciones';
import type { Pendiente } from './tipos';

function pendiente(
  idPendiente: string,
  idNinoPropuesto: string,
  margen: number | null,
  creadoEn: string,
  nivelPropuesto = 3,
): Pendiente {
  return {
    idPendiente,
    idNinoPropuesto,
    idEducadora: 'EDU-1',
    nivelPropuesto,
    dominio: null,
    margen,
    motivo: 'margen bajo',
    evidencia: '',
    estado: 'pendiente',
    creadoEn,
    idJardin: 'JAR-1',
    salaGrupo: 'Sala A',
  };
}

describe('notificaciones de advertencia', () => {
  it('mapea el texto, detalle, fecha y vínculo exactos', () => {
    const caso = pendiente('P-1', 'NINO-X', 0.08, '2026-02-03T10:00:00');
    const [notificacion] = notificacionesDesdePendientes([caso]);

    expect(notificacion).toEqual({
      idNotificacion: 'P-1',
      tipo: 'advertencia',
      titulo: 'Revisar a NINO-X: clasificación bajo el umbral',
      detalle: 'El modelo propuso el nivel 3 con margen 0,08 (umbral 0,15)',
      fecha: '2026-02-03T10:00:00',
      href: '/nino/NINO-X',
      pendiente: caso,
    });
  });

  it('solo crea advertencias bajo el umbral', () => {
    const notificaciones = notificacionesDesdePendientes([
      pendiente('baja', 'N-1', 0.149, '2026-01-01'),
      pendiente('igual', 'N-2', 0.15, '2026-01-02'),
      pendiente('alta', 'N-3', 0.4, '2026-01-03'),
      pendiente('sin-margen', 'N-4', null, '2026-01-04'),
    ]);
    expect(notificaciones.map((n) => n.idNotificacion)).toEqual(['baja']);
  });

  it('ordena de nueva a antigua y conserva el orden en empates', () => {
    const notificaciones = notificacionesDesdePendientes([
      pendiente('antigua', 'N-1', 0.1, '2026-01-01'),
      pendiente('empate-1', 'N-2', 0.1, '2026-02-01'),
      pendiente('empate-2', 'N-3', 0.1, '2026-02-01'),
    ]);
    expect(notificaciones.map((n) => n.idNotificacion)).toEqual([
      'empate-1',
      'empate-2',
      'antigua',
    ]);
  });
});
