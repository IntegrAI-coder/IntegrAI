import { useEffect, useMemo, useState } from 'react';
import { useEstadoDatos, useVersionDatos } from '../data/DatosContext';
import { cargarPendientes, resolverPendiente, usaApi } from '../data/cargar';
import type { Pendiente } from '../domain/tipos';
import { Breadcrumbs } from '../components/Breadcrumbs';
import { Tabla, type Columna } from '../components/Tabla';
import { Cargando, ErrorEstado, Vacio } from '../components/Estado';

type EstadoCarga =
  | { estado: 'cargando' }
  | { estado: 'error'; mensaje: string }
  | { estado: 'listo'; pendientes: Pendiente[] };

export function Pendientes() {
  // Aseguramos que el contexto de datos esté montado (misma app).
  useEstadoDatos();
  const version = useVersionDatos();
  const hayApi = usaApi();
  const [carga, setCarga] = useState<EstadoCarga>({ estado: 'cargando' });
  const [accionError, setAccionError] = useState<string | null>(null);
  const [resolviendo, setResolviendo] = useState<string | null>(null);

  useEffect(() => {
    if (!hayApi) {
      setCarga({ estado: 'listo', pendientes: [] });
      return;
    }
    let activo = true;
    cargarPendientes()
      .then((pendientes) => {
        if (activo) setCarga({ estado: 'listo', pendientes });
      })
      .catch((error: unknown) => {
        if (activo) {
          setCarga({ estado: 'error', mensaje: error instanceof Error ? error.message : 'Error desconocido' });
        }
      });
    return () => {
      activo = false;
    };
  }, [hayApi, version]);

  const columnas: Columna<Pendiente>[] = useMemo(
    () => [
      {
        clave: 'nino',
        encabezado: 'Niño/a',
        ordenable: true,
        valor: (p) => p.nombreVisible || p.idNinoPropuesto,
        render: (p) => <span title={p.idNinoPropuesto}>{p.nombreVisible || p.idNinoPropuesto}</span>,
      },
      {
        clave: 'curso',
        encabezado: 'Curso',
        ordenable: true,
        valor: (p) => `${p.idJardin ?? ''} ${p.salaGrupo ?? ''}`,
        render: (p) => (
          <>
            {p.idJardin ?? '—'} · {p.salaGrupo ?? '—'}
          </>
        ),
      },
      { clave: 'tia', encabezado: 'Tía', ordenable: true, valor: (p) => p.idEducadora ?? '—' },
      { clave: 'nivel', encabezado: 'Nivel prop.', numerica: true, ordenable: true, valor: (p) => p.nivelPropuesto ?? -1 },
      { clave: 'margen', encabezado: 'Margen', numerica: true, ordenable: true, valor: (p) => p.margen ?? 0,
        render: (p) => <>{p.margen === null ? '—' : p.margen.toFixed(3)}</> },
      { clave: 'motivo', encabezado: 'Motivo', ordenable: true, valor: (p) => p.motivo },
      { clave: 'creado', encabezado: 'Creado', ordenable: true, valor: (p) => p.creadoEn },
      {
        clave: 'acciones',
        encabezado: 'Verificar',
        valor: () => '',
        render: (p) => (
          <div className="advertencia__acciones">
            <button type="button" disabled={resolviendo === p.idPendiente}
                    onClick={() => accion(p, 'aprobado')}>
              ✓ Aprobar
            </button>
            <button type="button" disabled={resolviendo === p.idPendiente}
                    onClick={() => accion(p, 'editado', p.nivelPropuesto ?? undefined)}>
              ✏️ Editar {p.nivelPropuesto ?? ''}
            </button>
            <button type="button" disabled={resolviendo === p.idPendiente}
                    onClick={() => accion(p, 'rechazado')}>
              🚫 Rechazar
            </button>
          </div>
        ),
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [resolviendo],
  );

  async function accion(p: Pendiente, accionTipo: 'aprobado' | 'editado' | 'rechazado', nivel?: number) {
    setResolviendo(p.idPendiente);
    setAccionError(null);
    try {
      await resolverPendiente(p.idPendiente, accionTipo, nivel);
      const nuevos = await cargarPendientes();
      setCarga({ estado: 'listo', pendientes: nuevos });
    } catch (error: unknown) {
      setAccionError(error instanceof Error ? error.message : 'No se pudo resolver');
    } finally {
      setResolviendo(null);
    }
  }

  return (
    <>
      <Breadcrumbs migas={[{ etiqueta: 'Por verificar' }]} />
      <h2>Por verificar</h2>
      <p className="ficha-descripcion">
        Cola de la tía: observaciones con margen bajo que el modelo dejó para confirmación humana.
        Aprobar o editar (por WhatsApp) escribe la evaluación canónica.
      </p>

      {!hayApi && <Vacio mensaje="Esta vista requiere datos vivos del backend (no disponible en modo CSV)." />}
      {hayApi && carga.estado === 'cargando' && <Cargando mensaje="Cargando cola…" />}
      {carga.estado === 'error' && <ErrorEstado mensaje={`No se pudo cargar la cola: ${carga.mensaje}`} />}
      {accionError && <ErrorEstado mensaje={accionError} />}
      {hayApi && carga.estado === 'listo' && (
        carga.pendientes.length === 0 ? (
          <Vacio mensaje="No hay pendientes por verificar." />
        ) : (
          <>
            <p className="estado">{carga.pendientes.length} pendientes. Aprobar o editar escribe la evaluación canónica.</p>
            <Tabla
              columnas={columnas}
              filas={carga.pendientes}
              claveFila={(p) => p.idPendiente}
              descripcion="Cola de observaciones por verificar"
            />
          </>
        )
      )}
    </>
  );
}
