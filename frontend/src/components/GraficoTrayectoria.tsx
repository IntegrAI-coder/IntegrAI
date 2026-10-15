import {
  CartesianGrid,
  Label,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

interface Punto {
  fecha: string;
  nivel: number;
}

interface Props {
  datos: Punto[];
  titulo?: string;
}

/**
 * Gráfico de línea: cómo cambia el nivel del niño/a a lo largo del tiempo.
 * Pensado para leerse sin conocimientos técnicos: título, ejes rotulados con
 * unidades, puntos visibles y una nota con el último nivel observado.
 */
export function GraficoTrayectoria({
  datos,
  titulo = '¿Cómo ha avanzado en el tiempo?',
}: Props) {
  const ultimo = datos[datos.length - 1];

  return (
    <figure className="figura">
      <figcaption className="figura__titulo">{titulo}</figcaption>
      <div
        className="grafico"
        role="img"
        aria-label={`${titulo} Eje vertical: nivel de desarrollo (1 a 9). Eje horizontal: fecha de la observación.`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={datos} margin={{ top: 8, right: 24, bottom: 32, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e5ea" />
            <XAxis dataKey="fecha" tickLine={false}>
              <Label
                value="Fecha de la observación"
                position="insideBottom"
                offset={-18}
                style={{ fontSize: '0.85rem', fill: '#5b6676' }}
              />
            </XAxis>
            <YAxis domain={[1, 9]} allowDecimals={false} tickLine={false} width={48}>
              <Label
                value="Nivel de desarrollo (1 a 9)"
                angle={-90}
                position="insideLeft"
                style={{ fontSize: '0.85rem', fill: '#5b6676', textAnchor: 'middle' }}
              />
            </YAxis>
            <Tooltip
              formatter={(valor: number) => [`Nivel ${valor}`, 'Nivel estimado']}
              labelFormatter={(fecha) => `Observación del ${fecha}`}
            />
            <Legend
              verticalAlign="top"
              height={28}
              formatter={() => 'Nivel observado'}
            />
            <ReferenceLine
              y={9}
              stroke="#c7ced8"
              strokeDasharray="4 4"
              label={{ value: 'Nivel máximo', position: 'insideTopRight', fontSize: 11, fill: '#5b6676' }}
            />
            <Line
              type="monotone"
              dataKey="nivel"
              name="nivel"
              stroke="#2563eb"
              strokeWidth={2}
              dot={{ r: 4 }}
              activeDot={{ r: 6 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="figura__nota">
        {ultimo
          ? `Último nivel observado: ${ultimo.nivel} (${ultimo.fecha}).`
          : 'Sin observaciones registradas todavía.'}
      </p>
    </figure>
  );
}
