import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useEstadoDatos } from '../data/DatosContext';
import { resumenJardines, type ResumenJardin } from '../domain/consultas';
import { formatearPromedio } from '../domain/formato';
import { Breadcrumbs } from '../components/Breadcrumbs';
import { Tabla, type Columna } from '../components/Tabla';
import { Cargando, ErrorEstado, Vacio } from '../components/Estado';

const HOY = new Date();

export function Jardines() {
  const estado = useEstadoDatos();

  const jardines = useMemo(
    () => (estado.estado === 'listo' ? resumenJardines(estado.datos, HOY) : []),
    [estado],
  );

  const columnas: Columna<ResumenJardin>[] = [
    { clave: 'jardin', encabezado: 'Jardín', ordenable: true, valor: (j) => j.nombreJardin },
    { clave: 'comuna', encabezado: 'Comuna', ordenable: true, valor: (j) => j.comuna },
    { clave: 'salas', encabezado: 'Salas', numerica: true, ordenable: true, valor: (j) => j.totalSalas },
    { clave: 'ninos', encabezado: 'Niños/as', numerica: true, ordenable: true, valor: (j) => j.totalNinos },
    {
      clave: 'promedio',
      encabezado: 'Nivel promedio',
      numerica: true,
      ordenable: true,
      valor: (j) => j.nivelPromedio ?? -1,
      render: (j) => <>{formatearPromedio(j.nivelPromedio)}</>,
    },
    { clave: 'alertas', encabezado: 'Alertas', numerica: true, ordenable: true, valor: (j) => j.totalAlertas },
    {
      clave: 'rezagada',
      encabezado: 'Sala más rezagada',
      ordenable: true,
      valor: (j) => j.salaMasRezagada?.salaGrupo ?? '',
      render: (j) =>
        j.salaMasRezagada ? (
          <Link to={`/curso/${j.idJardin}/${encodeURIComponent(j.salaMasRezagada.salaGrupo)}`}>
            {j.salaMasRezagada.salaGrupo} · promedio {formatearPromedio(j.salaMasRezagada.nivelPromedio)}
          </Link>
        ) : (
          <>—</>
        ),
    },
  ];

  return (
    <>
      <Breadcrumbs migas={[{ etiqueta: 'Jardines' }]} />
      <h2>Jardines</h2>
      <p className="ficha-descripcion">
        Panorama para la directora: cada jardín con su nivel promedio y la <strong>sala más
        rezagada</strong> respecto al resto del jardín (alerta de grupo-curso).
      </p>

      {estado.estado === 'cargando' && <Cargando />}
      {estado.estado === 'error' && (
        <ErrorEstado mensaje={`No se pudieron cargar los datos: ${estado.mensaje}`} />
      )}
      {estado.estado === 'listo' &&
        (jardines.length === 0 ? (
          <Vacio mensaje="No hay jardines para mostrar." />
        ) : (
          <Tabla
            columnas={columnas}
            filas={jardines}
            claveFila={(j) => j.idJardin}
            descripcion="Panorama por jardín"
          />
        ))}
    </>
  );
}
