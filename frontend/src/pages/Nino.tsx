import { useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { useEstadoDatos } from '../data/DatosContext';
import { fichaNino, nivelPorNumero } from '../domain/consultas';
import { Breadcrumbs } from '../components/Breadcrumbs';
import { Tarjeta } from '../components/Tarjeta';
import { BadgeNivel } from '../components/BadgeNivel';
import { BadgeAlerta } from '../components/BadgeAlerta';
import { GraficoTrayectoria } from '../components/GraficoTrayectoria';
import { Cargando, ErrorEstado, Vacio } from '../components/Estado';

const HOY = new Date();

export function Nino() {
  const { idNino = '' } = useParams();
  const estado = useEstadoDatos();

  const vista = useMemo(() => {
    if (estado.estado !== 'listo') {
      return null;
    }
    const ficha = fichaNino(estado.datos, idNino, HOY);
    if (!ficha) {
      return null;
    }
    const niveles = nivelPorNumero(estado.datos.niveles);
    return {
      ficha,
      nivelVigenteInfo:
        ficha.nivelVigente !== null ? niveles.get(ficha.nivelVigente) : undefined,
      trayectoria: ficha.observaciones.map((o) => ({
        fecha: o.fechaObservacion,
        nivel: o.nivelEstimado,
      })),
    };
  }, [estado, idNino]);

  const idJardin = vista?.ficha.nino.idJardin;
  const sala = vista?.ficha.nino.salaGrupo;

  return (
    <>
      <Breadcrumbs
        migas={[
          { etiqueta: 'Cursos', ruta: '/' },
          ...(idJardin && sala
            ? [{ etiqueta: `${idJardin} · ${sala}`, ruta: `/curso/${idJardin}/${sala}` }]
            : []),
          { etiqueta: idNino },
        ]}
      />

      {estado.estado === 'cargando' && <Cargando />}
      {estado.estado === 'error' && (
        <ErrorEstado mensaje={`No se pudieron cargar los datos: ${estado.mensaje}`} />
      )}

      {estado.estado === 'listo' && !vista && (
        <Vacio mensaje={`No se encontró el niño/a ${idNino}.`} />
      )}

      {estado.estado === 'listo' && vista && (
        <>
          <h2>{vista.ficha.nino.idNino}</h2>

          <section aria-label="Resumen del niño/a" className="tarjetas">
            <Tarjeta etiqueta="Edad (meses)" valor={String(vista.ficha.edadMeses)} />
            <Tarjeta
              etiqueta="Nivel vigente"
              valor={vista.ficha.nivelVigente?.toString() ?? '—'}
            />
            <Tarjeta
              etiqueta="Nivel esperado"
              valor={vista.ficha.nivelEsperado?.toString() ?? '—'}
            />
            <Tarjeta
              etiqueta="Brecha"
              valor={
                vista.ficha.brecha === null
                  ? '—'
                  : vista.ficha.brecha > 0
                    ? `+${vista.ficha.brecha}`
                    : String(vista.ficha.brecha)
              }
              alerta={vista.ficha.alerta}
            />
          </section>

          {vista.nivelVigenteInfo && (
            <section aria-label="Nivel vigente" className="panel">
              <h3>
                Nivel {vista.nivelVigenteInfo.nivel}: {vista.nivelVigenteInfo.nombreNivel}{' '}
                {vista.ficha.alerta && <BadgeAlerta activa />}
              </h3>
              <p className="ficha-descripcion">{vista.nivelVigenteInfo.descripcion}</p>
            </section>
          )}

          <section aria-label="Trayectoria del nivel" className="panel">
            <h3 className="tarjeta__etiqueta">Trayectoria del nivel</h3>
            {vista.trayectoria.length === 0 ? (
              <Vacio mensaje="Sin observaciones registradas." />
            ) : (
              <GraficoTrayectoria datos={vista.trayectoria} />
            )}
          </section>

          <section aria-label="Observaciones" className="panel">
            <h3 className="tarjeta__etiqueta">Observaciones</h3>
            {vista.ficha.observaciones.length === 0 ? (
              <Vacio mensaje="Sin observaciones registradas." />
            ) : (
              [...vista.ficha.observaciones]
                .slice()
                .reverse()
                .map((obs) => (
                  <article key={obs.idObservacion} className="observacion">
                    <div className="observacion__cabecera">
                      <span className="observacion__fecha">{obs.fechaObservacion}</span>
                      <span className="observacion__formato">{obs.formatoCaptura}</span>
                      <BadgeNivel nivel={obs.nivelEstimado} />
                    </div>
                    {obs.manifestaciones.length > 0 ? (
                      <ul>
                        {obs.manifestaciones.map((m) => (
                          <li key={m.idManifestacion}>{m.textoObservable}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="ficha-descripcion">
                        Sin manifestaciones registradas.
                      </p>
                    )}
                  </article>
                ))
            )}
          </section>
        </>
      )}
    </>
  );
}
