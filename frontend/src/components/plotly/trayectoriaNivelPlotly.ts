import type { Nivel } from '../../domain/tipos';
import {
  etiquetaNivel,
  type PuntoMensual,
  type Tendencia,
  type Trayectoria,
} from '../../domain/trayectoria';
import type { ConfigPlotly, DisposicionPlotly, TrazaPlotly } from './tipos';

export const COLOR_NINO = '#1d4ed8';
export const COLOR_GRUPO = '#475569';
export const COLOR_TENDENCIA = '#b45309';

export const CONFIG_PLOTLY: ConfigPlotly = { responsive: true, displaylogo: false };

/** Escapa `& < > "` para textos que Plotly interpreta como HTML limitado (hover,
 *  leyenda). Los textos vienen de CSV/API y no se confía en ellos. */
export function escaparHtml(texto: string): string {
  return texto
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** Número con coma decimal, como se lee en español de Chile. */
export function formatearDecimal(valor: number, decimales = 2): string {
  return valor.toFixed(decimales).replace('.', ',');
}

/** Texto corto de la tendencia: "sube 0,39 niveles por mes", etc. */
export function textoTendencia(t: Tendencia): string {
  if (t.direccion === 'insuficiente' || t.pendienteMes === null) {
    return 'se necesitan observaciones en al menos 2 meses';
  }
  const magnitud = formatearDecimal(Math.abs(t.pendienteMes));
  if (t.direccion === 'sube') return `sube ${magnitud} niveles por mes`;
  if (t.direccion === 'baja') return `baja ${magnitud} niveles por mes`;
  return `estable (${magnitud} niveles por mes)`;
}

/** Las medias mensuales se ubican en el día 15 para dibujarlas en un eje de fechas. */
function fechaDeMes(mes: string): string {
  return `${mes}-15`;
}

function lineasHover(partes: string[]): string {
  return partes.map(escaparHtml).join('<br>');
}

function textoMensual(etiqueta: string, p: PuntoMensual): string {
  return lineasHover([
    `${etiqueta} · ${p.mes}`,
    `Nivel promedio: ${formatearDecimal(p.promedio)}`,
    `n = ${p.n} ${p.n === 1 ? 'observación' : 'observaciones'}`,
  ]);
}

/** Trazas del gráfico: observaciones, promedio mensual del niño/a, promedio de su
 *  sala y, si hay al menos 2 meses, la recta de tendencia. */
export function construirTrazas(t: Trayectoria, niveles: Nivel[]): TrazaPlotly[] {
  const nombreNivel = (nivel: number): string => etiquetaNivel(nivel, niveles, 60);
  const nObs = t.observaciones.length;

  const observaciones: TrazaPlotly = {
    type: 'scatter',
    mode: 'markers',
    name: `Observaciones del niño/a (n = ${nObs})`,
    x: t.observaciones.map((o) => o.fecha.slice(0, 10)),
    y: t.observaciones.map((o) => o.nivel),
    text: t.observaciones.map((o) =>
      lineasHover([
        `Observación del ${o.fecha.slice(0, 10)}`,
        `Nivel ${nombreNivel(o.nivel)}`,
        `Dominios: ${o.dominios.length > 0 ? o.dominios.join(', ') : 'sin manifestaciones'}`,
        `Fuente: ${o.fuente}`,
      ]),
    ),
    hovertemplate: '%{text}<extra></extra>',
    marker: {
      symbol: 'circle-open',
      size: 11,
      color: COLOR_NINO,
      line: { color: COLOR_NINO, width: 2 },
    },
  };

  const mensualNino: TrazaPlotly = {
    type: 'scatter',
    mode: 'lines+markers',
    name: `Promedio mensual del niño/a (${t.mensualNino.length} ${t.mensualNino.length === 1 ? 'mes' : 'meses'})`,
    x: t.mensualNino.map((p) => fechaDeMes(p.mes)),
    y: t.mensualNino.map((p) => p.promedio),
    text: t.mensualNino.map((p) => textoMensual('Niño/a', p)),
    hovertemplate: '%{text}<extra></extra>',
    line: { color: COLOR_NINO, dash: 'solid', width: 3 },
    marker: { symbol: 'diamond', size: 10, color: COLOR_NINO },
    connectgaps: true,
  };

  const grupo: TrazaPlotly = {
    type: 'scatter',
    mode: 'lines+markers',
    name: `Promedio de la sala (${t.nNinosGrupo} niños/as, ${t.nObsGrupo} obs.)`,
    x: t.mensualGrupo.map((p) => fechaDeMes(p.mes)),
    y: t.mensualGrupo.map((p) => p.promedio),
    text: t.mensualGrupo.map((p) => textoMensual('Sala', p)),
    hovertemplate: '%{text}<extra></extra>',
    line: { color: COLOR_GRUPO, dash: 'dash', width: 2 },
    marker: { symbol: 'square', size: 7, color: COLOR_GRUPO },
    connectgaps: true,
  };

  const trazas = [observaciones, mensualNino, grupo];

  if (t.tendencia.direccion !== 'insuficiente' && t.tendencia.extremos.length > 0) {
    trazas.push({
      type: 'scatter',
      mode: 'lines',
      name: `Tendencia (${textoTendencia(t.tendencia)})`,
      x: t.tendencia.extremos.map((e) => fechaDeMes(e.mes)),
      y: t.tendencia.extremos.map((e) => e.valor),
      hovertemplate: `Tendencia: ${escaparHtml(textoTendencia(t.tendencia))}<extra></extra>`,
      line: { color: COLOR_TENDENCIA, dash: 'dot', width: 3 },
    });
  }

  return trazas;
}

/** Ejes con título y unidad, eje Y fijo de 1 a 9 con el nombre de cada nivel (solo el
 *  número en pantallas angostas) y leyenda horizontal debajo del área de trazado. */
export function construirDisposicion(
  _t: Trayectoria,
  niveles: Nivel[],
  compacto: boolean,
): DisposicionPlotly {
  const valores = [1, 2, 3, 4, 5, 6, 7, 8, 9];
  return {
    xaxis: {
      title: { text: 'Fecha de la observación (mes)' },
      type: 'date',
      tickformat: '%Y-%m',
      automargin: true,
      gridcolor: '#e2e5ea',
      fixedrange: true,
    },
    yaxis: {
      title: { text: 'Nivel de la ruta (1 a 9)' },
      tickvals: valores,
      ticktext: valores.map((v) => (compacto ? String(v) : etiquetaNivel(v, niveles))),
      range: [0.5, 9.5],
      automargin: true,
      gridcolor: '#e2e5ea',
      zeroline: false,
      fixedrange: true,
    },
    legend: { orientation: 'h', x: 0, y: -0.28, xanchor: 'left', yanchor: 'top' },
    margin: { l: 8, r: 16, t: 12, b: 8 },
    paper_bgcolor: '#ffffff',
    plot_bgcolor: '#ffffff',
    font: { family: 'system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif', size: compacto ? 11 : 12, color: '#1f2733' },
    hoverlabel: { align: 'left', bgcolor: '#ffffff', font: { color: '#1f2733' } },
    hovermode: 'closest',
  };
}
