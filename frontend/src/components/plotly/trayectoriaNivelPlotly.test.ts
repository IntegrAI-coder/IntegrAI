import { describe, it, expect } from 'vitest';
import type { Datos } from '../../data/cargar';
import type { Nivel } from '../../domain/tipos';
import { construirTrayectoria, type Trayectoria } from '../../domain/trayectoria';
import {
  CONFIG_PLOTLY,
  COLOR_GRUPO,
  COLOR_NINO,
  COLOR_TENDENCIA,
  construirDisposicion,
  construirTrazas,
  escaparHtml,
  formatearDecimal,
  textoTendencia,
} from './trayectoriaNivelPlotly';

const HOY = new Date('2026-01-01');

const niveles: Nivel[] = Array.from({ length: 9 }, (_, i) => ({
  nivel: i + 1,
  nombreNivel: `Nivel número ${i + 1} con un nombre bastante largo para truncar`,
  edadMinMeses: i * 4,
  edadMaxMeses: i * 4 + 4,
  descripcion: '',
}));

const nino = (idNino: string, salaGrupo: string) => ({
  idNino,
  fechaNacimiento: '2024-01-01',
  idJardin: 'J1',
  salaGrupo,
  fechaIngreso: '2024-06-01',
});

const obs = (id: string, idNino: string, fecha: string, nivel: number) => ({
  idObservacion: id,
  idNino,
  fechaObservacion: fecha,
  formatoCaptura: 'audio',
  nivelEstimado: nivel,
});

const datos: Datos = {
  niveles,
  jardines: [],
  ninos: [nino('N1', 'SA'), nino('N2', 'SA'), nino('N3', 'SA'), nino('N4', 'SA')],
  observaciones: [
    obs('O3', 'N1', '2025-08-03', 5),
    obs('O1', 'N1', '2025-03-03', 3),
    obs('O2', 'N1', '2025-05-03', 4),
    obs('O4', 'N2', '2025-03-10', 6),
    obs('O5', 'N3', '2025-04-01', 7),
    obs('O6', 'N4', '2025-03-03', 2),
    obs('O7', 'N4', '2025-03-20', 4),
  ],
  manifestaciones: [
    { idManifestacion: 'M1', nivel: 3, dominio: 'lenguaje', textoObservable: 'a' },
    { idManifestacion: 'M2', nivel: 3, dominio: '<script>alert(1)</script>', textoObservable: 'b' },
  ],
  observacionManifestaciones: [
    { idObservacion: 'O1', idManifestacion: 'M1' },
    { idObservacion: 'O1', idManifestacion: 'M2' },
  ],
};

function trayectoria(id: string): Trayectoria {
  const t = construirTrayectoria(datos, id, HOY);
  if (!t) {
    throw new Error(`Falta la trayectoria de ${id}`);
  }
  return t;
}

describe('escaparHtml', () => {
  it('escapa los caracteres que Plotly interpretaría como HTML', () => {
    expect(escaparHtml('<b>"a" & b</b>')).toBe('&lt;b&gt;&quot;a&quot; &amp; b&lt;/b&gt;');
  });

  it('deja intacto el texto sin caracteres especiales', () => {
    expect(escaparHtml('Nivel 3 · lenguaje')).toBe('Nivel 3 · lenguaje');
  });
});

describe('formato de números y tendencia', () => {
  it('usa coma decimal', () => {
    expect(formatearDecimal(0.3947)).toBe('0,39');
    expect(formatearDecimal(4, 1)).toBe('4,0');
  });

  it('describe la dirección de la tendencia', () => {
    expect(textoTendencia(trayectoria('N1').tendencia)).toBe('sube 0,39 niveles por mes');
    expect(textoTendencia(trayectoria('N4').tendencia)).toBe(
      'se necesitan observaciones en al menos 2 meses',
    );
  });
});

describe('construirTrazas', () => {
  it('devuelve 4 trazas cuando hay tendencia', () => {
    const trazas = construirTrazas(trayectoria('N1'), niveles);
    expect(trazas).toHaveLength(4);
    expect(trazas.every((z) => z.type === 'scatter')).toBe(true);
  });

  it('devuelve 3 trazas cuando hay un solo mes (sin tendencia)', () => {
    const trazas = construirTrazas(trayectoria('N4'), niveles);
    expect(trazas).toHaveLength(3);
    expect(trazas.some((z) => z.name.startsWith('Tendencia'))).toBe(false);
  });

  it('distingue las series por forma y estilo además del color', () => {
    const [obsZ, nino1, grupo, tendencia] = construirTrazas(trayectoria('N1'), niveles);
    expect(obsZ?.marker?.symbol).toBe('circle-open');
    expect(nino1?.marker?.symbol).toBe('diamond');
    expect(nino1?.line?.dash).toBe('solid');
    expect(grupo?.marker?.symbol).toBe('square');
    expect(grupo?.line?.dash).toBe('dash');
    expect(tendencia?.line?.dash).toBe('dot');
    expect(tendencia?.marker).toBeUndefined();
    expect(nino1?.line?.color).toBe(COLOR_NINO);
    expect(grupo?.line?.color).toBe(COLOR_GRUPO);
    expect(tendencia?.line?.color).toBe(COLOR_TENDENCIA);
    const estilos = [obsZ, nino1, grupo, tendencia].map(
      (z) => `${z?.marker?.symbol ?? 'sin'}|${z?.line?.dash ?? 'sin'}`,
    );
    expect(new Set(estilos).size).toBe(4);
  });

  it('ordena x de forma ascendente en todas las trazas', () => {
    for (const traza of construirTrazas(trayectoria('N1'), niveles)) {
      expect([...traza.x].sort()).toEqual(traza.x);
    }
  });

  it('la traza mensual del niño coincide con mensualNino (x en el día 15)', () => {
    const t = trayectoria('N1');
    const traza = construirTrazas(t, niveles)[1];
    expect(traza?.x).toEqual(['2025-03-15', '2025-05-15', '2025-08-15']);
    expect(traza?.y).toEqual(t.mensualNino.map((p) => p.promedio));
    expect(traza?.y).toEqual([3, 4, 5]);
  });

  it('la traza de observaciones usa la fecha exacta y el nivel de cada una', () => {
    const traza = construirTrazas(trayectoria('N1'), niveles)[0];
    expect(traza?.x).toEqual(['2025-03-03', '2025-05-03', '2025-08-03']);
    expect(traza?.y).toEqual([3, 4, 5]);
  });

  it('mantiene todas las y de observaciones y promedios entre 1 y 9', () => {
    const [obsZ, nino1, grupo] = construirTrazas(trayectoria('N1'), niveles);
    for (const traza of [obsZ, nino1, grupo]) {
      for (const y of traza?.y ?? []) {
        expect(y).toBeGreaterThanOrEqual(1);
        expect(y).toBeLessThanOrEqual(9);
      }
    }
  });

  it('el grupo es solo la sala del niño y promedia todas sus observaciones', () => {
    const grupo = construirTrazas(trayectoria('N1'), niveles)[2];
    // 2025-03: 3 (N1), 6 (N2), 2 y 4 (N4) => 15 / 4
    expect(grupo?.y[0]).toBeCloseTo(3.75, 10);
    expect(grupo?.text?.[0]).toContain('n = 4 observaciones');
  });

  it('incluye n en los nombres de leyenda', () => {
    const nombres = construirTrazas(trayectoria('N1'), niveles).map((z) => z.name);
    expect(nombres[0]).toContain('n = 3');
    expect(nombres[1]).toContain('3 meses');
    expect(nombres[2]).toContain('4 niños/as');
    expect(nombres[3]).toContain('sube 0,39 niveles por mes');
  });

  it('escapa el HTML de los textos del tooltip', () => {
    const traza = construirTrazas(trayectoria('N1'), niveles)[0];
    const primero = traza?.text?.[0] ?? '';
    expect(primero).not.toContain('<script>');
    expect(primero).toContain('&lt;script&gt;');
    expect(primero).toContain('Fuente: audio');
    expect(primero).toContain('Observación del 2025-03-03');
    expect(primero).toContain('Nivel 3 · ');
  });
});

describe('construirDisposicion', () => {
  it('rotula los ejes con título y unidad', () => {
    const d = construirDisposicion(trayectoria('N1'), niveles, false);
    expect(d.xaxis.title.text).toBe('Fecha de la observación (mes)');
    expect(d.yaxis.title.text).toBe('Nivel de la ruta (1 a 9)');
  });

  it('muestra 9 ticks con el nombre del nivel', () => {
    const d = construirDisposicion(trayectoria('N1'), niveles, false);
    expect(d.yaxis.tickvals).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9]);
    expect(d.yaxis.ticktext).toHaveLength(9);
    expect(d.yaxis.ticktext?.[6]).toMatch(/^7 · Nivel número 7/);
  });

  it('en modo compacto muestra solo los números', () => {
    const d = construirDisposicion(trayectoria('N1'), niveles, true);
    expect(d.yaxis.ticktext).toEqual(['1', '2', '3', '4', '5', '6', '7', '8', '9']);
  });

  it('fija el rango del eje Y y pone la leyenda horizontal debajo', () => {
    const d = construirDisposicion(trayectoria('N1'), niveles, false);
    expect(d.yaxis.range).toEqual([0.5, 9.5]);
    expect(d.legend.orientation).toBe('h');
    expect(d.legend.y).toBeLessThan(0);
    expect(d.xaxis.type).toBe('date');
  });
});

describe('CONFIG_PLOTLY', () => {
  it('es responsive y oculta el logo', () => {
    expect(CONFIG_PLOTLY).toEqual({ responsive: true, displaylogo: false });
  });
});
