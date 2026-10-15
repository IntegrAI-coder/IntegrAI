import type { Nivel, Observacion } from './tipos';

export const UMBRAL_ALERTA = -2;

export function edadMeses(fechaNacimiento: string, hoy: Date): number {
  const nacimiento = new Date(fechaNacimiento);
  let meses =
    (hoy.getFullYear() - nacimiento.getFullYear()) * 12 +
    (hoy.getMonth() - nacimiento.getMonth());
  if (hoy.getDate() < nacimiento.getDate()) {
    meses -= 1;
  }
  return Math.max(0, meses);
}

export function nivelEsperado(meses: number, niveles: Nivel[]): number | null {
  const ordenados = [...niveles].sort((a, b) => a.nivel - b.nivel);
  for (const nivel of ordenados) {
    if (meses >= nivel.edadMinMeses && meses < nivel.edadMaxMeses) {
      return nivel.nivel;
    }
  }
  const ultimo = ordenados[ordenados.length - 1];
  if (ultimo && meses >= ultimo.edadMaxMeses) {
    return ultimo.nivel;
  }
  return null;
}

export function brecha(
  nivelVigente: number | null,
  esperado: number | null,
): number | null {
  if (nivelVigente === null || esperado === null) {
    return null;
  }
  return nivelVigente - esperado;
}

export function tieneAlerta(valorBrecha: number | null): boolean {
  return valorBrecha !== null && valorBrecha <= UMBRAL_ALERTA;
}

export function observacionMasReciente(
  observaciones: Observacion[],
): Observacion | null {
  if (observaciones.length === 0) {
    return null;
  }
  return observaciones.reduce((reciente, actual) =>
    actual.fechaObservacion > reciente.fechaObservacion ? actual : reciente,
  );
}

export function nivelVigente(observaciones: Observacion[]): number | null {
  const reciente = observacionMasReciente(observaciones);
  return reciente ? reciente.nivelEstimado : null;
}

export function promedio(valores: number[]): number | null {
  if (valores.length === 0) {
    return null;
  }
  const suma = valores.reduce((acc, v) => acc + v, 0);
  return suma / valores.length;
}
