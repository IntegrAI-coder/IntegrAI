import type { NotificacionAdvertencia, Pendiente } from './tipos';

export const UMBRAL_ADVERTENCIA = 0.15;

function decimalEspanol(valor: number): string {
  return valor.toFixed(2).replace('.', ',');
}

export function notificacionesDesdePendientes(
  pendientes: Pendiente[],
): NotificacionAdvertencia[] {
  return pendientes
    .map((pendiente, indice) => ({ pendiente, indice }))
    .filter(
      ({ pendiente }) =>
        pendiente.margen !== null && pendiente.margen < UMBRAL_ADVERTENCIA,
    )
    .sort(
      (a, b) =>
        b.pendiente.creadoEn.localeCompare(a.pendiente.creadoEn) ||
        a.indice - b.indice,
    )
    .map(({ pendiente }) => ({
      idNotificacion: pendiente.idPendiente,
      tipo: 'advertencia',
      titulo: `Revisar a ${pendiente.idNinoPropuesto}: clasificación bajo el umbral`,
      detalle: `El modelo propuso el nivel ${pendiente.nivelPropuesto ?? '—'} con margen ${decimalEspanol(pendiente.margen as number)} (umbral 0,15)`,
      fecha: pendiente.creadoEn,
      href: `/nino/${encodeURIComponent(pendiente.idNinoPropuesto)}`,
    }));
}
