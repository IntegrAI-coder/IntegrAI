import {
  Bar,
  BarChart,
  CartesianGrid,
  Label,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

interface Dato {
  nombre: string;
  valor: number;
}

interface Props {
  datos: Dato[];
  titulo: string;
  etiquetaX?: string;
  etiquetaY?: string;
  unidad?: string;
  nota?: string;
}

/**
 * Gráfico de barras horizontales para comparar categorías (dominios, salas, grupos).
 * Pensado para leerse sin conocimientos técnicos: título, ejes rotulados, herramienta
 * de ayuda con la unidad y una nota con el total.
 */
export function GraficoBarras({
  datos,
  titulo,
  etiquetaX = 'Cantidad',
  etiquetaY = 'Categoría',
  unidad = 'registro',
  nota,
}: Props) {
  const total = datos.reduce((suma, d) => suma + d.valor, 0);

  return (
    <figure className="figura">
      <figcaption className="figura__titulo">{titulo}</figcaption>
      <div
        className="grafico"
        role="img"
        aria-label={`${titulo} Eje vertical: ${etiquetaY.toLowerCase()}. Eje horizontal: ${etiquetaX.toLowerCase()}. Total ${total}.`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={datos}
            layout="vertical"
            margin={{ top: 8, right: 24, bottom: 8, left: 8 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e5ea" />
            <XAxis
              type="number"
              allowDecimals={false}
              domain={[0, 'dataMax + 1']}
              tickLine={false}
            >
              <Label
                value={etiquetaX}
                position="insideBottom"
                offset={-4}
                style={{ fontSize: '0.85rem', fill: '#5b6676' }}
              />
            </XAxis>
            <YAxis
              type="category"
              dataKey="nombre"
              width={140}
              tickLine={false}
              interval={0}
              tick={{ fontSize: '0.85rem', fill: '#5b6676' }}
            />
            <Tooltip
              formatter={(valor: number) => [
                `${valor} ${valor === 1 ? unidad : pluralizar(unidad)}`,
                etiquetaX,
              ]}
            />
            <Bar dataKey="valor" name={etiquetaX} fill="#2563eb" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="figura__nota">
        {nota ??
          (total === 0
            ? 'Todavía no hay datos para mostrar en este grupo.'
            : `Total: ${total} ${total === 1 ? unidad : pluralizar(unidad)}.`)}
      </p>
    </figure>
  );
}

function pluralizar(unidad: string): string {
  if (unidad.endsWith('ón')) {
    return `${unidad.slice(0, -2)}ones`;
  }
  return `${unidad}s`;
}
