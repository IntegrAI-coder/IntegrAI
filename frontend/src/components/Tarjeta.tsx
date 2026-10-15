export function Tarjeta({
  etiqueta,
  valor,
  alerta = false,
}: {
  etiqueta: string;
  valor: string;
  alerta?: boolean;
}) {
  return (
    <div className={`tarjeta${alerta ? ' tarjeta--alerta' : ''}`}>
      <p className="tarjeta__etiqueta">{etiqueta}</p>
      <p className="tarjeta__valor">{valor}</p>
    </div>
  );
}
