import Papa from 'papaparse';
import { describe, it, expect } from 'vitest';
import type { Datos } from '../data/cargar';
import observacionesCsv from '../../../data/observaciones.csv?raw';
import ninosCsv from '../../../data/ninos.csv?raw';
import rutaNivelesCsv from '../../../data/ruta_niveles.csv?raw';
import manifestacionesCsv from '../../../data/manifestaciones.csv?raw';
import observacionManifestacionesCsv from '../../../data/observacion_manifestaciones.csv?raw';
import {
  MIN_OBSERVACIONES,
  UMBRAL_TENDENCIA,
  construirTrayectoria,
  describirTrayectoria,
  etiquetaNivel,
  indiceMes,
  mesDe,
  narrativaTrayectoria,
  ninosEnAlcance,
  ordenarPorFecha,
  promedioPorMes,
  tendenciaLineal,
} from './trayectoria';
import type { DireccionTendencia, PuntoMensual, Trayectoria } from './trayectoria';
import type { Nivel } from './tipos';

const HOY = new Date('2026-01-01');

const niveles: Nivel[] = [
  { nivel: 1, nombreNivel: 'Atención inicial', edadMinMeses: 0, edadMaxMeses: 2, descripcion: '' },
  { nivel: 3, nombreNivel: 'Exploración con objetos cotidianos', edadMinMeses: 4, edadMaxMeses: 6, descripcion: '' },
  { nivel: 4, nombreNivel: 'Juego simbólico', edadMinMeses: 6, edadMaxMeses: 8, descripcion: '' },
  { nivel: 5, nombreNivel: '   ', edadMinMeses: 8, edadMaxMeses: 10, descripcion: '' },
];

const nino = (idNino: string, idJardin: string, salaGrupo: string) => ({
  idNino,
  fechaNacimiento: '2024-01-01',
  idJardin,
  salaGrupo,
  fechaIngreso: '2024-06-01',
});

const obs = (idObservacion: string, idNino: string, fechaObservacion: string, nivelEstimado: number) => ({
  idObservacion,
  idNino,
  fechaObservacion,
  formatoCaptura: 'texto',
  nivelEstimado,
});

const datos: Datos = {
  niveles,
  jardines: [],
  ninos: [
    nino('N0', 'J1', 'SA'),
    nino('N1', 'J1', 'SA'),
    nino('N2', 'J1', 'SA'),
    nino('N3', 'J1', 'SB'),
    nino('N4', 'J2', 'SA'),
    nino('N5', 'J3', 'SA'),
    nino('N6', 'J3', 'SB'),
  ],
  observaciones: [
    obs('O3', 'N1', '2025-05-10', 4),
    obs('O1', 'N1', '2025-03-03', 3),
    obs('O2', 'N1', '2025-05-03', 4),
    obs('O4', 'N2', '2025-03-10', 5),
    obs('O5', 'N3', '2025-03-01', 9),
    obs('O6', 'N4', '2025-03-01', 1),
    obs('O7', 'N5', '2025-06-02', 2),
    obs('O8', 'N5', '2025-06-20', 4),
    obs('O9', 'N6', '2025-07-01', 6),
  ],
  manifestaciones: [
    { idManifestacion: 'M1', nivel: 3, dominio: 'lenguaje', textoObservable: 'a' },
    { idManifestacion: 'M2', nivel: 3, dominio: 'cognitivo', textoObservable: 'b' },
    { idManifestacion: 'M3', nivel: 3, dominio: 'lenguaje', textoObservable: 'c' },
  ],
  observacionManifestaciones: [
    { idObservacion: 'O1', idManifestacion: 'M1' },
    { idObservacion: 'O1', idManifestacion: 'M2' },
    { idObservacion: 'O1', idManifestacion: 'M3' },
  ],
};

const mensual = (...pares: [string, number][]): PuntoMensual[] =>
  pares.map(([mes, promedio]) => ({ mes, promedio, n: 1 }));

function requerir<T>(valor: T | null | undefined): T {
  if (valor === null || valor === undefined) {
    throw new Error('Se esperaba un valor');
  }
  return valor;
}

describe('constantes', () => {
  it('fija el mínimo de observaciones y el umbral de tendencia', () => {
    expect(MIN_OBSERVACIONES).toBe(2);
    expect(UMBRAL_TENDENCIA).toBe(0.1);
  });
});

describe('mesDe e indiceMes', () => {
  it('toma YYYY-MM de una fecha, con o sin hora', () => {
    expect(mesDe('2025-03-03')).toBe('2025-03');
    expect(mesDe('2025-03-03T10:15')).toBe('2025-03');
  });

  it('mide meses calendario también entre años', () => {
    expect(indiceMes('2026-01') - indiceMes('2025-12')).toBe(1);
    expect(indiceMes('2025-08') - indiceMes('2025-03')).toBe(5);
  });
});

describe('ordenarPorFecha', () => {
  it('ordena ascendente por fecha con entrada desordenada y desempata por id', () => {
    const entrada = [
      obs('B', 'N1', '2025-05-03', 4),
      obs('C', 'N1', '2025-01-01', 2),
      obs('A', 'N1', '2025-05-03', 3),
    ];
    expect(ordenarPorFecha(entrada).map((o) => o.idObservacion)).toEqual(['C', 'A', 'B']);
  });

  it('no muta la entrada', () => {
    const entrada = [obs('B', 'N1', '2025-05-03', 4), obs('A', 'N1', '2025-01-01', 3)];
    ordenarPorFecha(entrada);
    expect(entrada.map((o) => o.idObservacion)).toEqual(['B', 'A']);
  });
});

describe('promedioPorMes', () => {
  it('devuelve [] sin observaciones', () => {
    expect(promedioPorMes([])).toEqual([]);
  });

  it('una observación da un mes con n = 1', () => {
    expect(promedioPorMes([obs('A', 'N1', '2025-03-03', 4)])).toEqual([
      { mes: '2025-03', promedio: 4, n: 1 },
    ]);
  });

  it('promedia varias observaciones del mismo mes sin redondear', () => {
    const r = promedioPorMes([
      obs('A', 'N1', '2025-03-03', 3),
      obs('B', 'N1', '2025-03-20', 4),
      obs('C', 'N1', '2025-03-25', 4),
    ]);
    expect(r).toHaveLength(1);
    expect(r[0]?.n).toBe(3);
    expect(r[0]?.promedio).toBeCloseTo(11 / 3, 10);
  });

  it('ordena varios meses ascendente', () => {
    const r = promedioPorMes([
      obs('A', 'N1', '2025-08-03', 5),
      obs('B', 'N1', '2025-03-03', 3),
      obs('C', 'N1', '2025-05-03', 4),
    ]);
    expect(r.map((p) => p.mes)).toEqual(['2025-03', '2025-05', '2025-08']);
    expect(r.map((p) => p.promedio)).toEqual([3, 4, 5]);
  });
});

describe('tendenciaLineal', () => {
  it('con 0 meses es insuficiente', () => {
    expect(tendenciaLineal([])).toEqual({ direccion: 'insuficiente', pendienteMes: null, extremos: [] });
  });

  it('con 1 mes es insuficiente', () => {
    const t = tendenciaLineal(mensual(['2025-03', 4]));
    expect(t.direccion).toBe('insuficiente');
    expect(t.pendienteMes).toBeNull();
    expect(t.extremos).toEqual([]);
  });

  it('3, 4, 5 en los meses 0, 2 y 5 da 0.3947 y sube', () => {
    const t = tendenciaLineal(mensual(['2025-03', 3], ['2025-05', 4], ['2025-08', 5]));
    expect(t.direccion).toBe('sube');
    expect(t.pendienteMes).toBeCloseTo(0.3947, 4);
    expect(t.extremos.map((e) => e.mes)).toEqual(['2025-03', '2025-08']);
  });

  it('la recta ajustada pasa por la media de los puntos', () => {
    const t = tendenciaLineal(mensual(['2025-01', 2], ['2025-02', 4], ['2025-03', 6]));
    expect(t.pendienteMes).toBeCloseTo(2, 10);
    expect(t.extremos[0]?.valor).toBeCloseTo(2, 10);
    expect(t.extremos[1]?.valor).toBeCloseTo(6, 10);
  });

  it('una serie constante es estable con pendiente 0', () => {
    const t = tendenciaLineal(mensual(['2025-01', 4], ['2025-02', 4], ['2025-03', 4]));
    expect(t.direccion).toBe('estable');
    expect(t.pendienteMes).toBeCloseTo(0, 10);
  });

  it('una serie decreciente baja', () => {
    const t = tendenciaLineal(mensual(['2025-01', 5], ['2025-02', 4], ['2025-03', 3]));
    expect(t.direccion).toBe('baja');
    expect(t.pendienteMes).toBeCloseTo(-1, 10);
  });

  it('con hueco de meses usa la distancia real y no la posición', () => {
    const t = tendenciaLineal(mensual(['2025-01', 1], ['2025-04', 2]));
    expect(t.pendienteMes).toBeCloseTo(1 / 3, 10);
  });

  it('mide la distancia entre años', () => {
    const t = tendenciaLineal(mensual(['2025-12', 1], ['2026-01', 3]));
    expect(t.pendienteMes).toBeCloseTo(2, 10);
  });

  it('el umbral exacto 0.1 (positivo o negativo) es estable', () => {
    const sube = tendenciaLineal(mensual(['2025-01', 1], ['2025-11', 2]));
    expect(sube.pendienteMes).toBe(0.1);
    expect(sube.direccion).toBe('estable');
    const baja = tendenciaLineal(mensual(['2025-01', 2], ['2025-11', 1]));
    expect(baja.pendienteMes).toBe(-0.1);
    expect(baja.direccion).toBe('estable');
  });

  it('apenas sobre el umbral ya sube o baja', () => {
    expect(tendenciaLineal(mensual(['2025-01', 1], ['2025-10', 2])).direccion).toBe('sube');
    expect(tendenciaLineal(mensual(['2025-01', 2], ['2025-10', 1])).direccion).toBe('baja');
  });
});

describe('construirTrayectoria', () => {
  it('devuelve null si el niño no existe', () => {
    expect(construirTrayectoria(datos, 'NO-EXISTE', HOY)).toBeNull();
  });

  it('niño sin observaciones: listas vacías, no suficiente y sin lanzar', () => {
    const t = requerir(construirTrayectoria(datos, 'N0', HOY));
    expect(t.observaciones).toEqual([]);
    expect(t.mensualNino).toEqual([]);
    expect(t.suficiente).toBe(false);
    expect(t.tendencia.direccion).toBe('insuficiente');
  });

  it('niño con 1 observación no es suficiente', () => {
    const t = requerir(construirTrayectoria(datos, 'N2', HOY));
    expect(t.observaciones).toHaveLength(1);
    expect(t.suficiente).toBe(false);
  });

  it('ordena la serie por fecha aunque lleguen desordenadas', () => {
    const t = requerir(construirTrayectoria(datos, 'N1', HOY));
    expect(t.observaciones.map((o) => o.idObservacion)).toEqual(['O1', 'O2', 'O3']);
    expect(t.suficiente).toBe(true);
  });

  it('une dominios únicos ordenados, manifestaciones y nombre de nivel', () => {
    const primera = requerir(requerir(construirTrayectoria(datos, 'N1', HOY)).observaciones[0]);
    expect(primera.dominios).toEqual(['cognitivo', 'lenguaje']);
    expect(primera.manifestaciones).toBe(3);
    expect(primera.nombreNivel).toBe('Exploración con objetos cotidianos');
    expect(primera.fuente).toBe('texto');
  });

  it('el grupo es solo su sala, incluido el niño', () => {
    const t = requerir(construirTrayectoria(datos, 'N1', HOY));
    expect(t.nNinosGrupo).toBe(3);
    expect(t.nObsGrupo).toBe(4);
    expect(t.mensualGrupo).toEqual([
      { mes: '2025-03', promedio: 4, n: 2 },
      { mes: '2025-05', promedio: 4, n: 2 },
    ]);
  });

  it('calcula serie mensual y tendencia del niño', () => {
    const t = requerir(construirTrayectoria(datos, 'N1', HOY));
    expect(t.mensualNino).toEqual([
      { mes: '2025-03', promedio: 3, n: 1 },
      { mes: '2025-05', promedio: 4, n: 2 },
    ]);
    expect(t.tendencia.direccion).toBe('sube');
    expect(t.tendencia.pendienteMes).toBeCloseTo(0.5, 10);
  });

  it('dos observaciones en un mismo mes son suficientes pero sin tendencia', () => {
    const t = requerir(construirTrayectoria(datos, 'N5', HOY));
    expect(t.suficiente).toBe(true);
    expect(t.mensualNino).toEqual([{ mes: '2025-06', promedio: 3, n: 2 }]);
    expect(t.tendencia.direccion).toBe('insuficiente');
  });
});

describe('etiquetaNivel', () => {
  it('une número y nombre', () => {
    expect(etiquetaNivel(4, niveles)).toBe('4 · Juego simbólico');
  });

  it('trunca con elipsis dentro del máximo', () => {
    const e = etiquetaNivel(3, niveles, 12);
    expect(e).toBe('3 · Exploración…');
    expect(e.replace('3 · ', '')).toHaveLength(12);
  });

  it('con el máximo por defecto (24) trunca nombres largos', () => {
    expect(etiquetaNivel(3, niveles)).toBe('3 · Exploración con objetos…');
  });

  it('nivel sin nombre o inexistente muestra solo el número', () => {
    expect(etiquetaNivel(5, niveles)).toBe('5');
    expect(etiquetaNivel(9, niveles)).toBe('9');
  });
});

function conTendencia(t: Trayectoria, direccion: DireccionTendencia, pendienteMes: number | null): Trayectoria {
  return { ...t, tendencia: { direccion, pendienteMes, extremos: [] } };
}

describe('describirTrayectoria', () => {
  it('sin observaciones lo dice', () => {
    const t = requerir(construirTrayectoria(datos, 'N0', HOY));
    expect(describirTrayectoria(t, niveles)).toBe(
      'N0: sin observaciones registradas; no se puede trazar la trayectoria.',
    );
  });

  it('con una observación indica que faltan datos', () => {
    const t = requerir(construirTrayectoria(datos, 'N2', HOY));
    const texto = describirTrayectoria(t, niveles);
    expect(texto).toContain('N2: 1 observación el 2025-03-10');
    expect(texto).toContain('se necesitan al menos 2');
  });

  it('con varias resume rango, cambio de nivel, tendencia y grupo', () => {
    const t = requerir(construirTrayectoria(datos, 'N1', HOY));
    const texto = describirTrayectoria(t, niveles);
    expect(texto).toContain('N1: 3 observaciones entre 2025-03-03 y 2025-05-10');
    expect(texto).toContain('nivel pasó de 3 · Exploración con objetos… a 4 · Juego simbólico');
    expect(texto).toContain('tendencia: sube 0,50 niveles por mes');
    expect(texto).toContain('promedio del grupo J1 · SA: 3 niños');
  });

  it('cubre nivel sin cambios y tendencia insuficiente', () => {
    const t = requerir(construirTrayectoria(datos, 'N5', HOY));
    const texto = describirTrayectoria(t, niveles);
    expect(texto).toContain('nivel pasó de 2 a 4');
    expect(texto).toContain('sin tendencia');
    const igual = requerir(construirTrayectoria({ ...datos, observaciones: [
      obs('X1', 'N5', '2025-01-01', 4),
      obs('X2', 'N5', '2025-03-01', 4),
    ] }, 'N5', HOY));
    expect(describirTrayectoria(igual, niveles)).toContain('nivel sin cambios en 4 · Juego simbólico');
  });
});

describe('narrativaTrayectoria', () => {
  const base = requerir(construirTrayectoria(datos, 'N1', HOY));

  it('sin observaciones', () => {
    const n = narrativaTrayectoria(requerir(construirTrayectoria(datos, 'N0', HOY)));
    expect(n.ve).toContain('Todavía no hay observaciones');
    expect(n.significa).toContain('Con menos de 2 observaciones');
    expect(n.hago).toContain('Registra una observación');
  });

  it('con una observación', () => {
    const n = narrativaTrayectoria(requerir(construirTrayectoria(datos, 'N2', HOY)));
    expect(n.ve).toBe('Hay solo 1 observación (2025-03-10, nivel 5).');
    expect(n.significa).toContain('Con menos de 2 observaciones');
    expect(n.hago).toContain('Registra otra observación');
  });

  it('sube', () => {
    const n = narrativaTrayectoria(conTendencia(base, 'sube', 0.5));
    expect(n.ve).toContain('3 observaciones');
    expect(n.ve).toContain('4 observaciones de 3 niños/as de su sala');
    expect(n.significa).toBe('La línea sube: hay avance (sube 0,50 niveles por mes).');
  });

  it('baja', () => {
    const n = narrativaTrayectoria(conTendencia(base, 'baja', -0.5));
    expect(n.significa).toContain('La línea baja');
    expect(n.significa).toContain('baja 0,50 niveles por mes');
  });

  it('estable', () => {
    const n = narrativaTrayectoria(conTendencia(base, 'estable', 0.02));
    expect(n.significa).toBe('La línea se aplana: se quedó en el mismo nivel.');
    expect(n.importa).toContain('señal más honesta');
    expect(n.hago).toContain('actividad distinta');
  });

  it('insuficiente con 2 o más observaciones', () => {
    const n = narrativaTrayectoria(requerir(construirTrayectoria(datos, 'N5', HOY)));
    expect(n.ve).toContain('2 observaciones');
    expect(n.significa).toContain('faltan observaciones en al menos 2 meses');
  });
});

describe('ninosEnAlcance', () => {
  it('la parvularia ve solo su sala', () => {
    const ids = ninosEnAlcance(datos.ninos, { rol: 'parvularia', idJardin: 'J1', salaGrupo: 'SA' }).map(
      (n) => n.idNino,
    );
    expect(ids).toEqual(['N0', 'N1', 'N2']);
  });

  it('la parvularia no ve otra sala del mismo jardín ni la misma sala de otro jardín', () => {
    const ids = ninosEnAlcance(datos.ninos, { rol: 'parvularia', idJardin: 'J1', salaGrupo: 'SA' }).map(
      (n) => n.idNino,
    );
    expect(ids).not.toContain('N3');
    expect(ids).not.toContain('N4');
    expect(ids).not.toContain('N5');
  });

  it('la directora ve solo su jardín', () => {
    const ids = ninosEnAlcance(datos.ninos, { rol: 'directora', idJardin: 'J1' }).map((n) => n.idNino);
    expect(ids).toEqual(['N0', 'N1', 'N2', 'N3']);
  });

  it('la directora con idJardin null ve todos', () => {
    expect(ninosEnAlcance(datos.ninos, { rol: 'directora', idJardin: null })).toHaveLength(7);
  });

  it('sin coincidencias devuelve []', () => {
    expect(ninosEnAlcance(datos.ninos, { rol: 'parvularia', idJardin: 'J9', salaGrupo: 'SA' })).toEqual([]);
    expect(ninosEnAlcance(datos.ninos, { rol: 'directora', idJardin: 'J9' })).toEqual([]);
  });
});

type Fila = Record<string, string>;

function filas(csv: string): Fila[] {
  return Papa.parse<Fila>(csv, { header: true, skipEmptyLines: true }).data;
}

const datosCsv: Datos = {
  niveles: filas(rutaNivelesCsv).map((f) => ({
    nivel: Number(f.nivel),
    nombreNivel: f.nombre_nivel ?? '',
    edadMinMeses: Number(f.edad_min_meses),
    edadMaxMeses: Number(f.edad_max_meses),
    descripcion: f.descripcion ?? '',
  })),
  jardines: [],
  ninos: filas(ninosCsv).map((f) => ({
    idNino: f.id_nino ?? '',
    fechaNacimiento: f.fecha_nacimiento ?? '',
    idJardin: f.id_jardin ?? '',
    salaGrupo: f.sala_grupo ?? '',
    fechaIngreso: f.fecha_ingreso ?? '',
  })),
  observaciones: filas(observacionesCsv).map((f) => ({
    idObservacion: f.id_observacion ?? '',
    idNino: f.id_nino ?? '',
    fechaObservacion: f.fecha_observacion ?? '',
    formatoCaptura: f.formato_captura ?? '',
    nivelEstimado: Number(f.nivel_estimado),
  })),
  manifestaciones: filas(manifestacionesCsv).map((f) => ({
    idManifestacion: f.id_manifestacion ?? '',
    nivel: Number(f.nivel),
    dominio: f.dominio ?? '',
    textoObservable: f.texto_observable ?? '',
  })),
  observacionManifestaciones: filas(observacionManifestacionesCsv).map((f) => ({
    idObservacion: f.id_observacion ?? '',
    idManifestacion: f.id_manifestacion ?? '',
  })),
};

function promedioDe(serie: PuntoMensual[], mes: string): PuntoMensual {
  return requerir(serie.find((p) => p.mes === mes));
}

describe('paridad con el dashboard anterior (pandas sobre data/*.csv)', () => {
  it('NINO-00002: medias mensuales 3, 4, 5 y pendiente 0.3947 (sube)', () => {
    const t = requerir(construirTrayectoria(datosCsv, 'NINO-00002', HOY));
    expect(t.observaciones).toHaveLength(6);
    expect(t.mensualNino.map((p) => p.mes)).toEqual(['2025-03', '2025-05', '2025-08']);
    expect(promedioDe(t.mensualNino, '2025-03').promedio).toBeCloseTo(3, 5);
    expect(promedioDe(t.mensualNino, '2025-05').promedio).toBeCloseTo(4, 5);
    expect(promedioDe(t.mensualNino, '2025-08').promedio).toBeCloseTo(5, 5);
    expect(t.tendencia.pendienteMes).toBeCloseTo(0.3947, 4);
    expect(t.tendencia.direccion).toBe('sube');
    expect(t.suficiente).toBe(true);
  });

  it('grupo JAR-0010 / SG-A: medias mensuales de la sala', () => {
    const t = requerir(construirTrayectoria(datosCsv, 'NINO-00002', HOY));
    expect(t.nino.idJardin).toBe('JAR-0010');
    expect(t.nino.salaGrupo).toBe('SG-A');
    const esperado: [string, number, number][] = [
      ['2025-02', 5.285714, 7],
      ['2025-05', 3.888889, 9],
      ['2025-06', 2.9, 10],
      ['2025-07', 7.166667, 6],
      ['2026-02', 7.0, 5],
    ];
    for (const [mes, promedio, n] of esperado) {
      const punto = promedioDe(t.mensualGrupo, mes);
      expect(punto.promedio).toBeCloseTo(promedio, 5);
      expect(punto.n).toBe(n);
    }
  });

  it('dataset completo: promedioPorMes equivale al dashboard anterior sin filtros', () => {
    const serie = promedioPorMes(datosCsv.observaciones);
    expect(promedioDe(serie, '2025-01').promedio).toBeCloseTo(3.823529, 5);
    expect(promedioDe(serie, '2025-03').promedio).toBeCloseTo(3.669856, 5);
    expect(promedioDe(serie, '2025-07').promedio).toBeCloseTo(4.9125, 5);
    expect(promedioDe(serie, '2026-10').promedio).toBeCloseTo(8.0, 5);
  });

  it('NINO-00014 tiene 1 observación y no es suficiente', () => {
    const t = requerir(construirTrayectoria(datosCsv, 'NINO-00014', HOY));
    expect(t.observaciones).toHaveLength(1);
    expect(t.suficiente).toBe(false);
    expect(t.tendencia.direccion).toBe('insuficiente');
  });

  it('NINO-00001: dos observaciones del mismo mes promedian 7 con n = 2', () => {
    const t = requerir(construirTrayectoria(datosCsv, 'NINO-00001', HOY));
    expect(t.mensualNino).toEqual([{ mes: '2026-08', promedio: 7, n: 2 }]);
  });
});
