import { useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useEstadoDatos } from '../data/DatosContext';
import {
  alumnosDeCurso,
  distribucionNiveles,
  type AlumnoCurso,
} from '../domain/consultas';
import { promedio } from '../domain/metrics';
import { formatearPromedio } from '../domain/formato';
import { Breadcrumbs } from '../components/Breadcrumbs';
import { Tabla, type Columna } from '../components/Tabla';
import { Tarjeta } from '../components/Tarjeta';
import { BadgeNivel } from '../components/BadgeNivel';
import { BadgeAlerta } from '../components/BadgeAlerta';
import { GraficoDistribucion } from '../components/GraficoDistribucion';
import { Cargando, ErrorEstado, Vacio } from '../components/Estado';

const HOY = new Date();

export function Curso() {
  const { idJardin = '', sala = '' } = useParams();
  const estado = useEstadoDatos();

  const vista = useMemo(() => {
    if (estado.estado !== 'listo') {
      return null;
    }
    const alumnos = alumnosDeCurso(estado.datos, idJardin, sala, HOY);
    const jardin = estado.datos.jardines.find((j) => j.idJardin === idJardin);
    const nivelesVigentes = alumnos
      .map((a) => a.nivelVigente)
      .filter((v): v is number => v !== null);
    return {
      alumnos,
      jardin,
      nivelPromedio: promedio(nivelesVigentes),
      totalAlertas: alumnos.filter((a) => a.alerta).length,
      distribucion: distribucionNiveles(alumnos),
    };
  }, [estado, idJardin, sala]);

  const nombreJardin = vista?.jardin?.nombreFantasia ?? idJardin;

  return (
    <>
      <Breadcrumbs
        migas={[
          { etiqueta: 'Cursos', ruta: '/' },
          { etiqueta: `${nombreJardin} · ${sala}` },
        ]}
      />

      {estado.estado === 'cargando' && <Cargando />}
      {estado.estado === 'error' && (
        <ErrorEstado mensaje={`No se pudieron cargar los datos: ${estado.mensaje}`} />
      )}

      {estado.estado === 'listo' && vista && (
        <>
          <h2>
            {nombreJardin} · Sala {sala}
          </h2>
          <p className="ayuda">
            Este panel muestra cómo está el grupo completo. Cada niño/a aparece con
            su nivel actual y el nivel esperado para su edad; si está muy por debajo,
            se marca con una alerta para revisarlo.
          </p>

          {vista.alumnos.length === 0 ? (
            <Vacio mensaje="Este curso no tiene niños/as registrados." />
          ) : (
            <>
              <section aria-label="Resumen del curso" className="tarjetas">
                <Tarjeta
                  etiqueta="Niños y niñas"
                  valor={String(vista.alumnos.length)}
                  descripcion="Matriculados en esta sala"
                />
                <Tarjeta
                  etiqueta="Nivel promedio"
                  valor={formatearPromedio(vista.nivelPromedio)}
                  descripcion="Promedio del grupo, escala 1 a 9"
                />
                <Tarjeta
                  etiqueta="Necesitan apoyo"
                  valor={String(vista.totalAlertas)}
                  descripcion="Nivel por debajo de lo esperado para su edad"
                  alerta={vista.totalAlertas > 0}
                />
              </section>

              <section aria-label="Distribución por nivel" className="panel">
                <GraficoDistribucion datos={vista.distribucion} />
              </section>

              <section aria-label="Alumnos del curso" className="panel">
                <h3 className="seccion__titulo">Niños y niñas de la sala</h3>
                <Tabla
                  descripcion="Tabla de alumnos del curso con su nivel y brecha"
                  filas={vista.alumnos}
                  claveFila={(a) => a.idNino}
                  columnas={columnas}
                />
              </section>
            </>
          )}
        </>
      )}
    </>
  );
}

const columnas: Columna<AlumnoCurso>[] = [
  {
    clave: 'codigo',
    encabezado: 'Código',
    valor: (a) => a.idNino,
    render: (a) => <Link to={`/nino/${a.idNino}`}>{a.idNino}</Link>,
  },
  {
    clave: 'edad',
    encabezado: 'Edad (meses)',
    numerica: true,
    valor: (a) => a.edadMeses,
  },
  {
    clave: 'vigente',
    encabezado: 'Nivel actual',
    numerica: true,
    valor: (a) => a.nivelVigente,
    render: (a) => <BadgeNivel nivel={a.nivelVigente} />,
  },
  {
    clave: 'esperado',
    encabezado: 'Nivel esperado',
    numerica: true,
    valor: (a) => a.nivelEsperado,
    render: (a) => <BadgeNivel nivel={a.nivelEsperado} />,
  },
  {
    clave: 'brecha',
    encabezado: 'Diferencia',
    numerica: true,
    valor: (a) => a.brecha,
    render: (a) =>
      a.brecha === null ? (
        '—'
      ) : (
        <span className={a.brecha < 0 ? 'brecha-neg' : undefined}>
          {a.brecha > 0 ? `+${a.brecha}` : a.brecha}
        </span>
      ),
  },
  {
    clave: 'alerta',
    encabezado: 'Revisar',
    valor: (a) => (a.alerta ? 1 : 0),
    render: (a) => <BadgeAlerta activa={a.alerta} />,
  },
];
