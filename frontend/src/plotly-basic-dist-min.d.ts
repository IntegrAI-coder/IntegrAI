/** Declaración mínima de `plotly.js-basic-dist-min` (el paquete no trae tipos).
 *  Solo se tipa lo que usa la app; los datos y la disposición se tipan en
 *  `components/plotly/tipos.ts`. */
declare module 'plotly.js-basic-dist-min' {
  interface PlotlyApi {
    react(
      div: HTMLElement,
      data: readonly object[],
      layout: object,
      config: object,
    ): Promise<unknown>;
    purge(div: HTMLElement): void;
    Plots: {
      resize(div: HTMLElement): void;
    };
  }

  const Plotly: PlotlyApi;
  export default Plotly;
}
