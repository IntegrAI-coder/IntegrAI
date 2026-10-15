export function Tarjeta({
  etiqueta,
  valor,
  descripcion,
  alerta = false,
}: {
  etiqueta: string;
  valor: string;
  descripcion?: string;
  alerta?: boolean;
}) {
  return (
    <div className={`tarjeta${alerta ? ' tarjeta--alerta' : ''}`}>
      <p className="tarjeta__etiqueta">{etiqueta}</p>
      <p className="tarjeta__valor">{valor}</p>
      {descripcion && <p className="tarjeta__descripcion">{descripcion}</p>}
    </div>
  );
}
