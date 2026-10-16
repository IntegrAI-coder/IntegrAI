import { lazy, Suspense, type ReactNode } from 'react';
import type { DisposicionPlotly, TrazaPlotly } from './plotly/tipos';
import { Cargando, Vacio } from './Estado';

const PlotlyRender = lazy(() => import('./plotly/PlotlyRender'));

interface Props {
  data: TrazaPlotly[];
  layout: DisposicionPlotly;
  titulo: string;
  /** Texto para lectores de pantalla (`aria-label` del gráfico). */
  descripcion: string;
  /** Si viene definido se muestra este mensaje y NO se descarga Plotly. */
  vacio?: string;
  altura?: number;
  children?: ReactNode;
}

/**
 * Figura con gráfico Plotly: título visible, descripción accesible y carga perezosa
 * de la librería (chunk aparte). Con `vacio` muestra el mensaje en lugar del gráfico.
 */
export function GraficoPlotly({
  data,
  layout,
  titulo,
  descripcion,
  vacio,
  altura = 440,
  children,
}: Props) {
  return (
    <figure className="figura">
      <figcaption className="figura__titulo">{titulo}</figcaption>
      {vacio !== undefined ? (
        <Vacio mensaje={vacio} />
      ) : (
        <div role="img" aria-label={descripcion}>
          <Suspense fallback={<Cargando mensaje="Cargando gráfico…" />}>
            <PlotlyRender data={data} layout={layout} altura={altura} />
          </Suspense>
        </div>
      )}
      {children}
    </figure>
  );
}
