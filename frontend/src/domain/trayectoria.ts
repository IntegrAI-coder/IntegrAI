import type { Datos } from '../data/cargar';
import { fichaNino, nivelPorNumero, observacionesDeSala } from './consultas';
import type { Nino, Nivel } from './tipos';

/** Mínimo de observaciones para trazar la trayectoria de un niño/a. */
export const MIN_OBSERVACIONES = 2;

/** Pendiente (niveles por mes) a partir de la cual la tendencia deja de ser "estable".
 *  Se clasifica "sube" si la pendiente es MAYOR que el umbral y "baja" si es MENOR que
 *  su negativo; el valor exacto del umbral cuenta como "estable". */
export const UMBRAL_TENDENCIA = 0.1;

/** Una observación puntual del niño/a, lista para graficar y tabular. */
export interface PuntoObservacion {
  idObservacion: string;
  fecha: string;
  nivel: number;
  nombreNivel: string;
  /** Dominios distintos de las manifestaciones observadas, ordenados. */
  dominios: string[];
  /** Cantidad de manifestaciones asociadas a la observación. */
  manifestaciones: number;
  /** Formato de captura (texto, foto, audio o video). */
  fuente: string;
}

/** Media de `nivel_estimado` de un mes `YYYY-MM`; `n` = observaciones promediadas. */
export interface PuntoMensual {
  mes: string;
  promedio: number;
  n: number;
}

export type DireccionTendencia = 'sube' | 'estable' | 'baja' | 'insuficiente';

/** Resultado de la regresión lineal sobre la serie mensual. `extremos` son los dos
 *  puntos de la recta ajustada (primer y último mes); vacío si es `insuficiente`. */
export interface Tendencia {
  direccion: DireccionTendencia;
  pendienteMes: number | null;
  extremos: { mes: string; valor: number }[];
}

export interface Trayectoria {
  nino: Nino;
  /** Observaciones del niño/a, ordenadas por fecha. */
  observaciones: PuntoObservacion[];
  mensualNino: PuntoMensual[];
  /** Media mensual de TODAS las observaciones de su sala (incluido el niño/a). */
  mensualGrupo: PuntoMensual[];
  nNinosGrupo: number;
  nObsGrupo: number;
  tendencia: Tendencia;
  /** `true` si hay al menos `MIN_OBSERVACIONES` observaciones. */
  suficiente: boolean;
}

/** Quién mira el gráfico: la parvularia ve su sala; la directora, su jardín
 *  (`idJardin: null` = todos los jardines, comportamiento de la demo sin login). */
export type AlcanceRol =
  | { rol: 'parvularia'; idJardin: string; salaGrupo: string }
  | { rol: 'directora'; idJardin: string | null };

export interface NarrativaTrayectoria {
  ve: string;
  significa: string;
  importa: string;
  hago: string;
}

/** Mes `YYYY-MM` de una fecha `YYYY-MM-DD` (tolera `YYYY-MM-DDTHH:mm` del modo API). */
export function mesDe(fecha: string): string {
  return fecha.slice(0, 7);
}

/** Copia de las observaciones ordenada por fecha y, a igual fecha, por id. No muta. */
export function ordenarPorFecha<T extends { fechaObservacion: string; idObservacion: string }>(
  obs: T[],
): T[] {
  return [...obs].sort(
    (a, b) =>
      a.fechaObservacion.localeCompare(b.fechaObservacion) ||
      a.idObservacion.localeCompare(b.idObservacion),
  );
}

/** Media aritmética de `nivel_estimado` por mes `YYYY-MM`, ordenada por mes. Es el
 *  método de `drawTrayectoria` del dashboard anterior: la media es de TODAS las
 *  observaciones del conjunto (no una media de medias) y no se redondea. */
export function promedioPorMes(
  obs: { fechaObservacion: string; nivelEstimado: number }[],
): PuntoMensual[] {
  const acumulado = new Map<string, { suma: number; n: number }>();
  for (const o of obs) {
    const mes = mesDe(o.fechaObservacion);
    const previo = acumulado.get(mes) ?? { suma: 0, n: 0 };
    acumulado.set(mes, { suma: previo.suma + o.nivelEstimado, n: previo.n + 1 });
  }
  return [...acumulado.entries()]
    .map(([mes, { suma, n }]) => ({ mes, promedio: suma / n, n }))
    .sort((a, b) => a.mes.localeCompare(b.mes));
}

/** Índice de mes calendario (`año * 12 + mes`) de un `YYYY-MM`; permite medir
 *  distancias reales en meses, también cuando la serie tiene huecos. */
export function indiceMes(mes: string): number {
  const [anio, mm] = mes.split('-');
  return Number(anio) * 12 + Number(mm);
}

/** Tendencia por mínimos cuadrados sobre la serie mensual: x = meses calendario desde
 *  el primer mes con dato, y = media mensual. Pendiente en niveles por mes. Requiere
 *  al menos 2 meses distintos; si no, `insuficiente` y sin recta. */
export function tendenciaLineal(mensual: PuntoMensual[]): Tendencia {
  if (mensual.length < 2) {
    return { direccion: 'insuficiente', pendienteMes: null, extremos: [] };
  }
  const base = indiceMes(mensual[0]?.mes ?? '');
  const xs = mensual.map((p) => indiceMes(p.mes) - base);
  const ys = mensual.map((p) => p.promedio);
  const xMedia = xs.reduce((a, v) => a + v, 0) / xs.length;
  const yMedia = ys.reduce((a, v) => a + v, 0) / ys.length;
  let sxy = 0;
  let sxx = 0;
  xs.forEach((x, i) => {
    sxy += (x - xMedia) * ((ys[i] ?? 0) - yMedia);
    sxx += (x - xMedia) ** 2;
  });
  const pendiente = sxy / sxx;
  const direccion: DireccionTendencia =
    pendiente > UMBRAL_TENDENCIA ? 'sube' : pendiente < -UMBRAL_TENDENCIA ? 'baja' : 'estable';
  const valorEn = (x: number): number => yMedia + pendiente * (x - xMedia);
  const primero = mensual[0];
  const ultimo = mensual[mensual.length - 1];
  const extremos =
    primero && ultimo
      ? [
          { mes: primero.mes, valor: valorEn(xs[0] ?? 0) },
          { mes: ultimo.mes, valor: valorEn(xs[xs.length - 1] ?? 0) },
        ]
      : [];
  return { direccion, pendienteMes: pendiente, extremos };
}

/** Arma la trayectoria de un niño/a. `null` si no existe. Sin observaciones devuelve
 *  listas vacías y `suficiente: false`. El grupo son todas las observaciones de su
 *  sala (mismo jardín + misma sala), incluido el niño/a. */
export function construirTrayectoria(
  datos: Datos,
  idNino: string,
  hoy: Date = new Date(),
): Trayectoria | null {
  // `hoy` solo alimenta campos de edad de la ficha, que la trayectoria no usa.
  const ficha = fichaNino(datos, idNino, hoy);
  if (!ficha) {
    return null;
  }
  const nombres = nivelPorNumero(datos.niveles);
  const observaciones: PuntoObservacion[] = ordenarPorFecha(ficha.observaciones).map((o) => ({
    idObservacion: o.idObservacion,
    fecha: o.fechaObservacion,
    nivel: o.nivelEstimado,
    nombreNivel: nombres.get(o.nivelEstimado)?.nombreNivel ?? '',
    dominios: [...new Set(o.manifestaciones.map((m) => m.dominio))].sort(),
    manifestaciones: o.manifestaciones.length,
    fuente: o.formatoCaptura,
  }));
  const { idJardin, salaGrupo } = ficha.nino;
  const obsGrupo = observacionesDeSala(datos, idJardin, salaGrupo);
  const mensualNino = promedioPorMes(
    observaciones.map((o) => ({ fechaObservacion: o.fecha, nivelEstimado: o.nivel })),
  );
  return {
    nino: ficha.nino,
    observaciones,
    mensualNino,
    mensualGrupo: promedioPorMes(obsGrupo),
    nNinosGrupo: datos.ninos.filter((n) => n.idJardin === idJardin && n.salaGrupo === salaGrupo)
      .length,
    nObsGrupo: obsGrupo.length,
    tendencia: tendenciaLineal(mensualNino),
    suficiente: observaciones.length >= MIN_OBSERVACIONES,
  };
}

/** Etiqueta de eje `"7 · Nombre del nivel"`. El nombre se trunca a `max` caracteres
 *  (elipsis incluida). Nivel sin nombre => solo el número. */
export function etiquetaNivel(nivel: number, niveles: Nivel[], max = 24): string {
  const nombre = niveles.find((n) => n.nivel === nivel)?.nombreNivel.trim() ?? '';
  if (nombre === '') {
    return String(nivel);
  }
  const corto = nombre.length > max ? `${nombre.slice(0, Math.max(max - 1, 1)).trimEnd()}…` : nombre;
  return `${nivel} · ${corto}`;
}

function decimales(valor: number): string {
  return valor.toFixed(2).replace('.', ',');
}

function textoTendencia(t: Tendencia): string {
  if (t.direccion === 'insuficiente' || t.pendienteMes === null) {
    return 'sin tendencia (se necesitan observaciones en al menos 2 meses)';
  }
  const magnitud = decimales(Math.abs(t.pendienteMes));
  if (t.direccion === 'sube') return `sube ${magnitud} niveles por mes`;
  if (t.direccion === 'baja') return `baja ${magnitud} niveles por mes`;
  return `estable (${magnitud} niveles por mes)`;
}

function plural(n: number, singular: string, pluralTexto: string): string {
  return `${n} ${n === 1 ? singular : pluralTexto}`;
}

/** Descripción en una frase para `aria-label` del gráfico. */
export function describirTrayectoria(t: Trayectoria, niveles: Nivel[]): string {
  const id = t.nino.idNino;
  const total = t.observaciones.length;
  const primera = t.observaciones[0];
  const ultima = t.observaciones[total - 1];
  if (!primera || !ultima) {
    return `${id}: sin observaciones registradas; no se puede trazar la trayectoria.`;
  }
  if (total < MIN_OBSERVACIONES) {
    return (
      `${id}: 1 observación el ${primera.fecha}, nivel ${etiquetaNivel(primera.nivel, niveles)}; ` +
      `se necesitan al menos ${MIN_OBSERVACIONES} para trazar la trayectoria.`
    );
  }
  const cambio =
    primera.nivel === ultima.nivel
      ? `nivel sin cambios en ${etiquetaNivel(primera.nivel, niveles)}`
      : `nivel pasó de ${etiquetaNivel(primera.nivel, niveles)} a ${etiquetaNivel(ultima.nivel, niveles)}`;
  return (
    `${id}: ${total} observaciones entre ${primera.fecha} y ${ultima.fecha}; ${cambio}; ` +
    `tendencia: ${textoTendencia(t.tendencia)}; ` +
    `promedio del grupo ${t.nino.idJardin} · ${t.nino.salaGrupo}: ${plural(t.nNinosGrupo, 'niño', 'niños')}`
  );
}

/** Los cuatro textos de la tarjeta original: Qué veo / Qué significa / Por qué importa /
 *  Qué hago. `significa` y `hago` cambian según la dirección de la tendencia. */
export function narrativaTrayectoria(t: Trayectoria): NarrativaTrayectoria {
  const total = t.observaciones.length;
  const primera = t.observaciones[0];
  const ultima = t.observaciones[total - 1];
  const importa =
    'Una línea plana es la señal más honesta de que necesita otro tipo de experiencia.';
  if (!primera || !ultima) {
    return {
      ve: 'Todavía no hay observaciones de este niño/a.',
      significa: 'Con menos de 2 observaciones no se puede leer una trayectoria.',
      importa,
      hago: 'Registra una observación para empezar a trazar la línea.',
    };
  }
  if (!t.suficiente) {
    return {
      ve: `Hay solo 1 observación (${primera.fecha}, nivel ${primera.nivel}).`,
      significa: 'Con menos de 2 observaciones no se puede leer una trayectoria.',
      importa,
      hago: 'Registra otra observación para poder comparar y trazar la línea.',
    };
  }
  const ve =
    `Entre ${primera.fecha} y ${ultima.fecha} hay ${total} observaciones; ` +
    `el nivel va de ${primera.nivel} a ${ultima.nivel}. La línea gris es el promedio de ` +
    `${plural(t.nObsGrupo, 'observación', 'observaciones')} de ` +
    `${plural(t.nNinosGrupo, 'niño/a', 'niños/as')} de su sala.`;
  switch (t.tendencia.direccion) {
    case 'sube':
      return {
        ve,
        significa: `La línea sube: hay avance (${textoTendencia(t.tendencia)}).`,
        importa,
        hago: 'Mantén las experiencias actuales y vuelve a observar en dos semanas.',
      };
    case 'baja':
      return {
        ve,
        significa: `La línea baja: el nivel observado retrocede (${textoTendencia(t.tendencia)}).`,
        importa,
        hago: 'Revisa qué cambió en su rutina, prueba una actividad distinta y vuelve a observar en dos semanas.',
      };
    case 'estable':
      return {
        ve,
        significa: 'La línea se aplana: se quedó en el mismo nivel.',
        importa,
        hago: 'Prueba una actividad distinta y vuelve a observar en dos semanas.',
      };
    default:
      return {
        ve,
        significa:
          'Aún no se puede decir si avanza: faltan observaciones en al menos 2 meses distintos.',
        importa,
        hago: 'Vuelve a observar el mes siguiente para poder trazar la tendencia.',
      };
  }
}

/** Niños/as visibles según el rol. No autentica: solo acota listas y selectores. */
export function ninosEnAlcance(ninos: Nino[], alcance: AlcanceRol): Nino[] {
  if (alcance.rol === 'parvularia') {
    return ninos.filter(
      (n) => n.idJardin === alcance.idJardin && n.salaGrupo === alcance.salaGrupo,
    );
  }
  return alcance.idJardin === null ? [...ninos] : ninos.filter((n) => n.idJardin === alcance.idJardin);
}
