import {
  Bar,
  BarChart,
  CartesianGrid,
  Label,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

interface Dato {
  nivel: number;
  total: number;
}

interface Props {
  datos: Dato[];
  titulo?: string;
}

/**
 * Gráfico de barras: cuántos niños y niñas hay en cada nivel de desarrollo.
 * Pensado para leerse sin conocimientos técnicos: título, ejes rotulados con
 * unidades, leyenda y una nota con el total.
 */
export function GraficoDistribucion({
  datos,
  titulo = '¿En qué nivel está cada niño y niña del grupo?',
}: Props) {
  const total = datos.reduce((suma, d) => suma + d.total, 0);

  return (
    <figure className="figura">
      <figcaption className="figura__titulo">{titulo}</figcaption>
      <div
        className="grafico"
        role="img"
        aria-label={`${titulo} Eje vertical: cantidad de niños y niñas. Eje horizontal: nivel de desarrollo (${datos[0]?.nivel ?? 1} a ${datos[datos.length - 1]?.nivel ?? 9}).`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={datos} margin={{ top: 8, right: 16, bottom: 32, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e5ea" />
            <XAxis dataKey="nivel" tickLine={false} interval={0}>
              <Label
                value="Nivel de desarrollo"
                position="insideBottom"
                offset={-18}
                style={{ fontSize: '0.85rem', fill: '#5b6676' }}
              />
            </XAxis>
            <YAxis
              allowDecimals={false}
              tickLine={false}
              width={48}
              domain={[0, 'dataMax + 1']}
            >
              <Label
                value="Cantidad de niños/as"
                angle={-90}
                position="insideLeft"
                style={{ fontSize: '0.85rem', fill: '#5b6676', textAnchor: 'middle' }}
              />
            </YAxis>
            <Tooltip
              formatter={(valor: number) => [
                `${valor} ${valor === 1 ? 'niño/a' : 'niños/as'}`,
                'Cantidad',
              ]}
              labelFormatter={(nivel) => `Nivel ${nivel}`}
            />
            <Legend
              verticalAlign="top"
              height={28}
              formatter={() => 'Niños y niñas con ese nivel'}
            />
            <Bar dataKey="total" name="total" fill="#2563eb" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="figura__nota">
        {total === 0
          ? 'Todavía no hay niños/as con un nivel identificado en este grupo.'
          : `Total: ${total} ${total === 1 ? 'niño/a' : 'niños/as'} con un nivel identificado.`}
      </p>
    </figure>
  );
}
