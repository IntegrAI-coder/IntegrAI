import { useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import { BadgeAlerta } from '../components/BadgeAlerta';
import { BadgeNivel } from '../components/BadgeNivel';
import { Breadcrumbs } from '../components/Breadcrumbs';
import { Cargando, ErrorEstado, Vacio } from '../components/Estado';
import { GraficoDistribucion } from '../components/GraficoDistribucion';
import { Tabla, type Columna } from '../components/Tabla';
import { Tarjeta } from '../components/Tarjeta';
import { useEstadoDatos } from '../data/DatosContext';
import { useRevision } from '../data/RevisionContext';
import { tieneAccesoCurso } from '../domain/acceso';
import {
  alumnosDeCurso,
  distribucionNiveles,
  type AlumnoCurso,
} from '../domain/consultas';
import { formatearPromedio } from '../domain/formato';
import { promedio } from '../domain/metrics';

const HOY = new Date();

export function Curso() {
  const { idJardin = '', sala = '' } = useParams();
  const estado = useEstadoDatos();
  const { profesora } = useRevision();
  const autorizado = !profesora || tieneAccesoCurso(profesora, idJardin, sala);

  const vista = useMemo(() => {
    if (estado.estado !== 'listo' || !autorizado) {
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
  }, [autorizado, estado, idJardin, sala]);

  const nombreJardin = vista?.jardin?.nombreFantasia ?? idJardin;

  return (
    <>
      <Breadcrumbs
        migas={[
          profesora
            ? { etiqueta: 'Inicio', ruta: '/profesora/inicio' }
            : { etiqueta: 'Cursos', ruta: '/' },
          { etiqueta: `${nombreJardin} · ${sala}` },
        ]}
      />

      {estado.estado === 'cargando' && <Cargando />}
      {estado.estado === 'error' && (
        <ErrorEstado mensaje={`No se pudieron cargar los datos: ${estado.mensaje}`} />
      )}
      {estado.estado === 'listo' && !autorizado && <Vacio mensaje="No tienes acceso" />}

      {estado.estado === 'listo' && autorizado && vista && (
        <>
          <h2>{nombreJardin} · Sala {sala}</h2>

          {vista.alumnos.length === 0 ? (
            <Vacio mensaje="Este curso no tiene niños/as registrados." />
          ) : (
            <>
              <section aria-label="Resumen del curso" className="tarjetas">
                <Tarjeta etiqueta="Niños/as" valor={String(vista.alumnos.length)} />
                <Tarjeta
                  etiqueta="Nivel promedio"
                  valor={formatearPromedio(vista.nivelPromedio)}
                />
                <Tarjeta
                  etiqueta="Con alerta"
                  valor={String(vista.totalAlertas)}
                  alerta={vista.totalAlertas > 0}
                />
              </section>

              <section aria-label="Distribución por nivel" className="panel">
                <h3 className="tarjeta__etiqueta">Distribución por nivel (1–9)</h3>
                <GraficoDistribucion datos={vista.distribucion} />
              </section>

              <section aria-label="Alumnos del curso" className="panel">
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
    encabezado: 'Nivel vigente',
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
    encabezado: 'Brecha',
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
    encabezado: 'Alerta',
    valor: (a) => (a.alerta ? 1 : 0),
    render: (a) => <BadgeAlerta activa={a.alerta} />,
  },
];
