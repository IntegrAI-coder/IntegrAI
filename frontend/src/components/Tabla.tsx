import { useState, type ReactNode } from 'react';

export interface Columna<T> {
  clave: string;
  encabezado: string;
  numerica?: boolean;
  ordenable?: boolean;
  valor: (fila: T) => string | number | null;
  render?: (fila: T) => ReactNode;
}

interface TablaProps<T> {
  columnas: Columna<T>[];
  filas: T[];
  claveFila: (fila: T) => string;
  descripcion: string;
}

type Direccion = 'asc' | 'desc';

export function Tabla<T>({ columnas, filas, claveFila, descripcion }: TablaProps<T>) {
  const [orden, setOrden] = useState<{ clave: string; direccion: Direccion } | null>(
    null,
  );

  const columnaOrden = orden
    ? columnas.find((c) => c.clave === orden.clave)
    : undefined;

  const filasOrdenadas = columnaOrden
    ? [...filas].sort((a, b) => comparar(columnaOrden.valor(a), columnaOrden.valor(b)) *
        (orden?.direccion === 'desc' ? -1 : 1))
    : filas;

  function alternar(clave: string) {
    setOrden((previo) => {
      if (previo?.clave !== clave) {
        return { clave, direccion: 'asc' };
      }
      return { clave, direccion: previo.direccion === 'asc' ? 'desc' : 'asc' };
    });
  }

  return (
    <table className="tabla">
      <caption className="sr-only">{descripcion}</caption>
      <thead>
        <tr>
          {columnas.map((columna) => {
            const activa = orden?.clave === columna.clave;
            const aria = activa
              ? orden?.direccion === 'asc'
                ? 'ascending'
                : 'descending'
              : undefined;
            return (
              <th
                key={columna.clave}
                className={columna.numerica ? 'num' : undefined}
                aria-sort={aria}
                scope="col"
              >
                {columna.ordenable === false ? (
                  columna.encabezado
                ) : (
                  <button type="button" onClick={() => alternar(columna.clave)}>
                    {columna.encabezado}
                    <span aria-hidden="true">
                      {activa ? (orden?.direccion === 'asc' ? ' ▲' : ' ▼') : ' ↕'}
                    </span>
                  </button>
                )}
              </th>
            );
          })}
        </tr>
      </thead>
      <tbody>
        {filasOrdenadas.map((fila) => (
          <tr key={claveFila(fila)}>
            {columnas.map((columna) => (
              <td
                key={columna.clave}
                className={columna.numerica ? 'num' : undefined}
              >
                {columna.render ? columna.render(fila) : mostrar(columna.valor(fila))}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function mostrar(valor: string | number | null): string {
  return valor === null ? '—' : String(valor);
}

function comparar(a: string | number | null, b: string | number | null): number {
  if (a === null && b === null) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  if (typeof a === 'number' && typeof b === 'number') {
    return a - b;
  }
  return String(a).localeCompare(String(b));
}
