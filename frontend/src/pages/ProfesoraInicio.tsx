import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Breadcrumbs } from '../components/Breadcrumbs';
import { ListaAdvertencias } from '../components/ListaAdvertencias';
import { Cargando, ErrorEstado, Vacio } from '../components/Estado';
import { Tabla, type Columna } from '../components/Tabla';
import { Tarjeta } from '../components/Tarjeta';
import { useEstadoDatos } from '../data/DatosContext';
import { useRevision } from '../data/RevisionContext';
import { filtrarCursosDeProfesora } from '../domain/acceso';
import { resumenCursos, type ResumenCurso } from '../domain/consultas';
import { formatearPromedio } from '../domain/formato';

const HOY = new Date();

export function ProfesoraInicio() {
  const estadoDatos = useEstadoDatos();
  const { profesora, modo, notificaciones, estadoPendientes } = useRevision();

  const cursos = useMemo(() => {
    if (estadoDatos.estado !== 'listo' || !profesora) {
      return [];
    }
    return filtrarCursosDeProfesora(resumenCursos(estadoDatos.datos, HOY), profesora);
  }, [estadoDatos, profesora]);

  return (
    <>
      <Breadcrumbs migas={[{ etiqueta: 'Inicio' }]} />
      <h2>Inicio</h2>

      {modo === 'demo' && (
        <p className="aviso-demo" role="status">
          <strong>Modo demostración</strong>: los márgenes bajo el umbral son simulados.
        </p>
      )}

      <section aria-label="Resumen de profesora" className="tarjetas">
        <Tarjeta etiqueta="Mis cursos" valor={String(cursos.length)} />
        <Tarjeta
          etiqueta="Casos por revisar"
          valor={String(notificaciones.length)}
          alerta={notificaciones.length > 0}
        />
      </section>

      <section id="advertencias" className="seccion-profesora" aria-labelledby="titulo-advertencias">
        <h3 id="titulo-advertencias">Advertencias</h3>
        {estadoPendientes.estado === 'cargando' && <Cargando mensaje="Cargando advertencias…" />}
        {estadoPendientes.estado === 'error' && (
          <ErrorEstado mensaje={`No se pudieron cargar las advertencias: ${estadoPendientes.mensaje}`} />
        )}
        {estadoPendientes.estado === 'listo' && (
          notificaciones.length === 0 ? (
            <Vacio mensaje="No hay casos por revisar." />
          ) : (
            <ListaAdvertencias notificaciones={notificaciones} />
          )
        )}
      </section>

      <section className="seccion-profesora" aria-labelledby="titulo-mis-cursos">
        <h3 id="titulo-mis-cursos">Mis cursos</h3>
        {estadoDatos.estado === 'cargando' && <Cargando />}
        {estadoDatos.estado === 'error' && (
          <ErrorEstado mensaje={`No se pudieron cargar los datos: ${estadoDatos.mensaje}`} />
        )}
        {estadoDatos.estado === 'listo' && (
          cursos.length === 0 ? (
            <Vacio mensaje="No tienes cursos registrados." />
          ) : (
            <div className="panel lista-cursos">
              <Tabla
                descripcion="Cursos asociados a la profesora"
                filas={cursos}
                claveFila={(curso) => `${curso.idJardin}-${curso.salaGrupo}`}
                columnas={columnas}
              />
            </div>
          )
        )}
      </section>
    </>
  );
}

const columnas: Columna<ResumenCurso>[] = [
  {
    clave: 'jardin',
    encabezado: 'Jardín',
    valor: (curso) => curso.nombreJardin,
    render: (curso) => (
      <Link to={`/curso/${encodeURIComponent(curso.idJardin)}/${encodeURIComponent(curso.salaGrupo)}`}>
        {curso.nombreJardin}
      </Link>
    ),
  },
  { clave: 'sala', encabezado: 'Sala', valor: (curso) => curso.salaGrupo },
  {
    clave: 'ninos',
    encabezado: 'Niños/as',
    numerica: true,
    valor: (curso) => curso.totalNinos,
  },
  {
    clave: 'promedio',
    encabezado: 'Nivel promedio',
    numerica: true,
    valor: (curso) => curso.nivelPromedio,
    render: (curso) => formatearPromedio(curso.nivelPromedio),
  },
];
