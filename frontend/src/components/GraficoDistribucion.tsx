import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

interface Dato {
  nivel: number;
  total: number;
}

export function GraficoDistribucion({ datos }: { datos: Dato[] }) {
  return (
    <div className="grafico" role="img" aria-label="Distribución de niños y niñas por nivel vigente">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={datos} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e5ea" />
          <XAxis dataKey="nivel" tickLine={false} />
          <YAxis allowDecimals={false} tickLine={false} width={32} />
          <Tooltip
            formatter={(valor: number) => [`${valor}`, 'Niños/as']}
            labelFormatter={(nivel) => `Nivel ${nivel}`}
          />
          <Bar dataKey="total" fill="#2563eb" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
