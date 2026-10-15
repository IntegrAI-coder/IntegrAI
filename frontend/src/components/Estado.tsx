export function Cargando({ mensaje = 'Cargando datos…' }: { mensaje?: string }) {
  return (
    <p className="estado" role="status">
      {mensaje}
    </p>
  );
}

export function Vacio({ mensaje }: { mensaje: string }) {
  return <p className="estado">{mensaje}</p>;
}

export function ErrorEstado({ mensaje }: { mensaje: string }) {
  return (
    <p className="estado estado--error" role="alert">
      {mensaje}
    </p>
  );
}
