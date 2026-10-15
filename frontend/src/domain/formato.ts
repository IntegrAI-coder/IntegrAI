export function formatearPromedio(valor: number | null): string {
  return valor === null ? '—' : valor.toFixed(1);
}

export function formatearEntero(valor: number): string {
  return String(valor);
}
