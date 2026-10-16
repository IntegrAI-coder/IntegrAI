/** Tipos propios y mínimos para las trazas y la disposición de Plotly que usa la app
 *  (solo `scatter`). Reemplazan a `@types/plotly.js*`, que no se instala. */

export interface LineaPlotly {
  color: string;
  dash: 'solid' | 'dash' | 'dot';
  width: number;
}

export interface MarcadorPlotly {
  symbol: 'circle' | 'circle-open' | 'diamond' | 'square';
  size: number;
  color: string;
  line?: { color: string; width: number };
}

export interface TrazaPlotly {
  type: 'scatter';
  mode: 'lines' | 'markers' | 'lines+markers';
  name: string;
  x: string[];
  y: number[];
  text?: string[];
  hovertemplate?: string;
  line?: LineaPlotly;
  marker?: MarcadorPlotly;
  connectgaps?: boolean;
  showlegend?: boolean;
}

export interface EjePlotly {
  title: { text: string };
  type?: 'date' | 'linear';
  tickvals?: number[];
  ticktext?: string[];
  range?: [number | string, number | string];
  tickformat?: string;
  automargin?: boolean;
  dtick?: number | string;
  gridcolor?: string;
  zeroline?: boolean;
  fixedrange?: boolean;
}

export interface DisposicionPlotly {
  xaxis: EjePlotly;
  yaxis: EjePlotly;
  legend: {
    orientation: 'h' | 'v';
    x: number;
    y: number;
    xanchor: 'left' | 'center' | 'right';
    yanchor: 'top' | 'bottom' | 'middle';
  };
  margin: { l: number; r: number; t: number; b: number };
  paper_bgcolor: string;
  plot_bgcolor: string;
  font: { family: string; size: number; color: string };
  hoverlabel: { align: 'left' | 'right' | 'auto'; bgcolor: string; font: { color: string } };
  hovermode: 'closest';
}

export interface ConfigPlotly {
  responsive: boolean;
  displaylogo: boolean;
}
