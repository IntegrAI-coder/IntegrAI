import { Link } from 'react-router-dom';
import { Tabla, type Columna } from './Tabla';
import { Vacio } from './Estado';
import type { FilaRankingBrecha } from '../domain/rankingBrecha';

interface TablaRankingBrechaProps {
  filas: FilaRankingBrecha[];
  titulo?: string;
}

/** Panel de solo lectura que ordena a los niños/as de MAYOR a MENOR brecha para
 *  orientar dónde enfocar las horas que el registro automático devuelve a las
 *  parvularias. No automatiza acciones ni crea campañas: solo muestra el ranking
 *  como apoyo a la decisión. */
export function TablaRankingBrecha({
  filas,
  titulo = 'Ranking de brecha — dónde enfocar las horas ganadas',
}: TablaRankingBrechaProps) {
  const rankeables = filas.filter((f) => f.brecha !== null);
  const sinDatos = filas.filter((f) => f.brecha === null);

  const indicePorId = new Map<string, number>();
  rankeables.forEach((f, i) => indicePorId.set(f.idNino, i + 1));

  const columnas: Columna<FilaRankingBrecha>[] = [
    {
      clave: 'posicion',
      encabezado: '#',
      numerica: true,
      ordenable: false,
      valor: (f) => indicePorId.get(f.idNino) ?? 0,
    },
    {
      clave: 'nino',
      encabezado: 'Niño/a',
      valor: (f) => f.nombreVisible,
      render: (f) => <Link to={`/nino/${f.idNino}`}>{f.nombreVisible}</Link>,
    },
    { clave: 'edad', encabezado: 'Edad (meses)', numerica: true, valor: (f) => f.edadMeses },
    {
      clave: 'esperado',
      encabezado: 'Nivel esperado',
      numerica: true,
      valor: (f) => f.nivelEsperado,
    },
    {
      clave: 'actual',
      encabezado: 'Nivel actual',
      numerica: true,
      valor: (f) => f.nivelActual,
    },
    {
      clave: 'brecha',
      encabezado: 'Brecha',
      numerica: true,
      valor: (f) => f.diferencia,
      render: (f) =>
        f.diferencia === null ? (
          '—'
        ) : (
          <span className={f.diferencia < 0 ? 'brecha-neg' : undefined}>
            {f.diferencia > 0 ? `+${f.diferencia}` : f.diferencia}
          </span>
        ),
    },
    {
      clave: 'observaciones',
      encabezado: 'N.º de observaciones',
      numerica: true,
      valor: (f) => f.nObservaciones,
    },
    { clave: 'razon', encabezado: 'Razón', valor: (f) => f.razon },
  ];

  return (
    <section className="panel" aria-label="Ranking de brecha">
      <h3 className="seccion__titulo">{titulo}</h3>
      <p className="ayuda">
        Brecha = nivel esperado para la edad menos el nivel observado; a mayor
        brecha, más rezago. Solo es una lectura para decidir a quién acompañar, no
        inicia ninguna acción.
      </p>

      {rankeables.length === 0 ? (
        <Vacio mensaje="Sin niños/as con observaciones suficientes para rankear." />
      ) : (
        <>
          <p className="ayuda">
            {rankeables.length} niño/a{rankeables.length === 1 ? '' : 's'} con brecha
            medible, ordenados de mayor a menor rezago.
          </p>
          <Tabla
            descripcion="Ranking de niños/as por brecha, del más rezagado al menos rezagado"
            filas={rankeables}
            claveFila={(f) => f.idNino}
            columnas={columnas}
          />
          <div className="origen-alerta">
            <p className="ayuda">
              <strong>Qué veo:</strong> arriba están los niños/as con mayor brecha
              frente a lo esperado para su edad.
            </p>
            <p className="ayuda">
              <strong>Qué significa:</strong> ahí la edad no explica el nivel
              observado; es donde más rezago hay que recuperar.
            </p>
            <p className="ayuda">
              <strong>Qué hago:</strong> enfoca las horas ganadas en los primeros de
              la lista y abre su ficha para ver la trayectoria.
            </p>
          </div>
        </>
      )}

      {sinDatos.length > 0 && (
        <p className="ayuda">
          {sinDatos.length} niño/a{sinDatos.length === 1 ? '' : 's'} sin observaciones
          suficientes para medir brecha; aún no entran al ranking.
        </p>
      )}
    </section>
  );
}
