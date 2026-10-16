import { useEffect, useRef, useState } from 'react';
import { CONFIG_PLOTLY } from './trayectoriaNivelPlotly';
import type { DisposicionPlotly, TrazaPlotly } from './tipos';

interface Props {
  data: TrazaPlotly[];
  layout: DisposicionPlotly;
  altura: number;
}

type ApiPlotly = (typeof import('plotly.js-basic-dist-min'))['default'];

/**
 * Dibuja el gráfico con Plotly. Es el módulo que `GraficoPlotly` carga con
 * `React.lazy`: Plotly se descarga solo cuando hay un gráfico con datos que mostrar.
 */
export default function PlotlyRender({ data, layout, altura }: Props) {
  const contenedor = useRef<HTMLDivElement | null>(null);
  const plotly = useRef<ApiPlotly | null>(null);
  const [fallo, setFallo] = useState<string | null>(null);

  useEffect(() => {
    let cancelado = false;
    const div = contenedor.current;
    if (!div) {
      return undefined;
    }
    import('plotly.js-basic-dist-min')
      .then(async (mod) => {
        if (cancelado) {
          return;
        }
        plotly.current = mod.default;
        await mod.default.react(div, data, layout, CONFIG_PLOTLY);
      })
      .catch((error: unknown) => {
        if (!cancelado) {
          setFallo(error instanceof Error ? error.message : 'error desconocido');
        }
      });
    return () => {
      cancelado = true;
    };
  }, [data, layout]);

  useEffect(() => {
    const div = contenedor.current;
    if (!div || typeof ResizeObserver === 'undefined') {
      return undefined;
    }
    const observador = new ResizeObserver(() => {
      plotly.current?.Plots.resize(div);
    });
    observador.observe(div);
    return () => {
      observador.disconnect();
      plotly.current?.purge(div);
    };
  }, []);

  if (fallo !== null) {
    return (
      <p className="estado estado--error" role="alert">
        No se pudo cargar el gráfico: {fallo}. Revisa la tabla de datos más abajo.
      </p>
    );
  }

  return <div ref={contenedor} className="grafico-plotly" style={{ height: altura }} />;
}
