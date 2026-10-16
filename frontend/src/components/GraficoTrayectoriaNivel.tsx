import { useEffect, useMemo, useState } from 'react';
import type { Datos } from '../data/cargar';
import {
  MIN_OBSERVACIONES,
  construirTrayectoria,
  describirTrayectoria,
  etiquetaNivel,
  narrativaTrayectoria,
  type PuntoMensual,
  type PuntoObservacion,
} from '../domain/trayectoria';
import { GraficoPlotly } from './GraficoPlotly';
import { Tabla, type Columna } from './Tabla';
import { Vacio } from './Estado';
import {
  construirDisposicion,
  construirTrazas,
  formatearDecimal,
  textoTendencia,
} from './plotly/trayectoriaNivelPlotly';

const CONSULTA_COMPACTA = '(max-width: 520px)';

interface FilaMensual {
  mes: string;
  nino: PuntoMensual | undefined;
  grupo: PuntoMensual | undefined;
}

/** `true` en pantallas angostas: el eje Y muestra solo el número de nivel. */
function useCompacto(): boolean {
  const [compacto, setCompacto] = useState(
    () => typeof window !== 'undefined' && window.matchMedia(CONSULTA_COMPACTA).matches,
  );
  useEffect(() => {
    const consulta = window.matchMedia(CONSULTA_COMPACTA);
    const alCambiar = (e: MediaQueryListEvent) => setCompacto(e.matches);
    consulta.addEventListener('change', alCambiar);
    return () => consulta.removeEventListener('change', alCambiar);
  }, []);
  return compacto;
}

function celdaPromedio(p: PuntoMensual | undefined): string {
  return p ? `${formatearDecimal(p.promedio)} (n = ${p.n})` : '—';
}

/**
 * Trayectoria de nivel de un niño/a: observaciones, promedio mensual, promedio de su
 * sala y tendencia, con lectura en palabras y tablas equivalentes para accesibilidad.
 */
export function GraficoTrayectoriaNivel({ datos, idNino }: { datos: Datos; idNino: string }) {
  const t = useMemo(() => construirTrayectoria(datos, idNino), [datos, idNino]);
  const compacto = useCompacto();

  const trazas = useMemo(() => (t ? construirTrazas(t, datos.niveles) : []), [t, datos.niveles]);
  const disposicion = useMemo(
    () => (t ? construirDisposicion(t, datos.niveles, compacto) : null),
    [t, datos.niveles, compacto],
  );

  if (!t || !disposicion) {
    return <Vacio mensaje={`No se encontró el niño/a ${idNino}.`} />;
  }

  const total = t.observaciones.length;
  const unica: PuntoObservacion | undefined = total === 1 ? t.observaciones[0] : undefined;
  const narrativa = narrativaTrayectoria(t);
  const vacio = t.suficiente
    ? undefined
    : `Sin observaciones suficientes para trazar la trayectoria (n = ${total}; se necesitan al menos ${MIN_OBSERVACIONES}).`;

  const meses = new Map<string, FilaMensual>();
  for (const p of t.mensualGrupo) {
    meses.set(p.mes, { mes: p.mes, nino: undefined, grupo: p });
  }
  for (const p of t.mensualNino) {
    meses.set(p.mes, { mes: p.mes, nino: p, grupo: meses.get(p.mes)?.grupo });
  }
  const filasMensuales = [...meses.values()].sort((a, b) => a.mes.localeCompare(b.mes));

  return (
    <GraficoPlotly
      titulo={`Trayectoria de nivel de ${t.nino.idNino}`}
      descripcion={describirTrayectoria(t, datos.niveles)}
      data={trazas}
      layout={disposicion}
      vacio={vacio}
      altura={compacto ? 400 : 460}
    >
      {unica && (
        <p className="figura__nota">
          Única observación: {unica.fecha.slice(0, 10)}, nivel{' '}
          {etiquetaNivel(unica.nivel, datos.niveles, 60)}, fuente {unica.fuente}.
        </p>
      )}

      {t.suficiente && (
        <p className="figura__nota trayectoria-nota">
          n = {total} observaciones en {t.mensualNino.length}{' '}
          {t.mensualNino.length === 1 ? 'mes' : 'meses'}. Tendencia: {textoTendencia(t.tendencia)}.
          La línea gris es el promedio de {t.nObsGrupo} observaciones de {t.nNinosGrupo} niños/as de
          su sala ({t.nino.idJardin} · {t.nino.salaGrupo}).
        </p>
      )}

      <dl className="narrativa">
        <div>
          <dt>Qué veo</dt>
          <dd>{narrativa.ve}</dd>
        </div>
        <div>
          <dt>Qué significa</dt>
          <dd>{narrativa.significa}</dd>
        </div>
        <div>
          <dt>Por qué importa</dt>
          <dd>{narrativa.importa}</dd>
        </div>
        <div>
          <dt>Qué hago</dt>
          <dd>{narrativa.hago}</dd>
        </div>
      </dl>

      {total > 0 && (
        <details className="trayectoria-datos">
          <summary>Ver los datos del gráfico en tabla</summary>
          <Tabla
            descripcion={`Observaciones de ${t.nino.idNino} con fecha, nivel, dominios y fuente`}
            filas={t.observaciones}
            claveFila={(o) => o.idObservacion}
            columnas={columnasObservaciones(datos)}
          />
          <Tabla
            descripcion={`Nivel promedio por mes de ${t.nino.idNino} frente al promedio de su sala`}
            filas={filasMensuales}
            claveFila={(f) => f.mes}
            columnas={columnasMensuales}
          />
        </details>
      )}
    </GraficoPlotly>
  );
}

function columnasObservaciones(datos: Datos): Columna<PuntoObservacion>[] {
  return [
    { clave: 'fecha', encabezado: 'Fecha', valor: (o) => o.fecha.slice(0, 10) },
    {
      clave: 'nivel',
      encabezado: 'Nivel',
      valor: (o) => etiquetaNivel(o.nivel, datos.niveles, 60),
    },
    {
      clave: 'dominios',
      encabezado: 'Dominios',
      valor: (o) => (o.dominios.length > 0 ? o.dominios.join(', ') : '—'),
    },
    { clave: 'fuente', encabezado: 'Fuente', valor: (o) => o.fuente },
  ];
}

const columnasMensuales: Columna<FilaMensual>[] = [
  { clave: 'mes', encabezado: 'Mes', valor: (f) => f.mes },
  {
    clave: 'nino',
    encabezado: 'Niño/a (promedio)',
    numerica: true,
    valor: (f) => f.nino?.promedio ?? null,
    render: (f) => celdaPromedio(f.nino),
  },
  {
    clave: 'grupo',
    encabezado: 'Sala (promedio)',
    numerica: true,
    valor: (f) => f.grupo?.promedio ?? null,
    render: (f) => celdaPromedio(f.grupo),
  },
];
