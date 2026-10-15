import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useEstadoDatos } from '../data/DatosContext';
import { resumenCursos, type ResumenCurso } from '../domain/consultas';
import { formatearPromedio } from '../domain/formato';
import { Breadcrumbs } from '../components/Breadcrumbs';
import { Tabla, type Columna } from '../components/Tabla';
import { Cargando, ErrorEstado, Vacio } from '../components/Estado';

const HOY = new Date();

export function Cursos() {
  const estado = useEstadoDatos();
  const [busqueda, setBusqueda] = useState('');

  const cursos = useMemo(() => {
    if (estado.estado !== 'listo') {
      return [];
    }
    return resumenCursos(estado.datos, HOY);
  }, [estado]);

  const filtrados = useMemo(() => {
    const texto = busqueda.trim().toLowerCase();
    if (!texto) {
      return cursos;
    }
    return cursos.filter((c) =>
      [c.nombreJardin, c.comuna, c.salaGrupo, c.idJardin]
        .join(' ')
        .toLowerCase()
        .includes(texto),
    );
  }, [cursos, busqueda]);

  return (
    <>
      <Breadcrumbs migas={[{ etiqueta: 'Cursos' }]} />
      <h2>Cursos</h2>
      <p className="ayuda">
        Elige un curso (jardín y sala) para ver cómo está el grupo y cada niño o
        niña. La columna "Necesitan apoyo" indica cuántos están por debajo del nivel
        esperado para su edad.
      </p>

      {estado.estado === 'cargando' && <Cargando />}
      {estado.estado === 'error' && (
        <ErrorEstado mensaje={`No se pudieron cargar los datos: ${estado.mensaje}`} />
      )}

      {estado.estado === 'listo' && (
        <>
          <div className="buscador">
            <label htmlFor="buscador-cursos">Buscar por jardín, comuna o sala</label>
            <input
              id="buscador-cursos"
              type="search"
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              placeholder="Ej.: Valparaíso, SG-A…"
            />
          </div>

          {filtrados.length === 0 ? (
            <Vacio mensaje="No hay cursos que coincidan con la búsqueda." />
          ) : (
            <div className="panel lista-cursos">
              <Tabla
                descripcion="Listado de cursos agrupados por jardín"
                filas={filtrados}
                claveFila={(c) => `${c.idJardin}-${c.salaGrupo}`}
                columnas={columnas}
              />
            </div>
          )}
        </>
      )}
    </>
  );
}

const columnas: Columna<ResumenCurso>[] = [
  {
    clave: 'jardin',
    encabezado: 'Jardín',
    valor: (c) => c.nombreJardin,
    render: (c) => (
      <Link to={`/curso/${c.idJardin}/${c.salaGrupo}`}>{c.nombreJardin}</Link>
    ),
  },
  { clave: 'comuna', encabezado: 'Comuna', valor: (c) => c.comuna },
  { clave: 'sala', encabezado: 'Sala', valor: (c) => c.salaGrupo },
  {
    clave: 'ninos',
    encabezado: 'Niños y niñas',
    numerica: true,
    valor: (c) => c.totalNinos,
  },
  {
    clave: 'promedio',
    encabezado: 'Nivel promedio',
    numerica: true,
    valor: (c) => c.nivelPromedio,
    render: (c) => formatearPromedio(c.nivelPromedio),
  },
  {
    clave: 'alertas',
    encabezado: 'Necesitan apoyo',
    numerica: true,
    valor: (c) => c.totalAlertas,
  },
];
