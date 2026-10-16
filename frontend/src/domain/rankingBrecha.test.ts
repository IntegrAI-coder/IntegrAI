import Papa from 'papaparse';
import { describe, it, expect } from 'vitest';
import type { Datos } from '../data/cargar';
import observacionesCsv from '../../../data/observaciones.csv?raw';
import ninosCsv from '../../../data/ninos.csv?raw';
import rutaNivelesCsv from '../../../data/ruta_niveles.csv?raw';
import manifestacionesCsv from '../../../data/manifestaciones.csv?raw';
import observacionManifestacionesCsv from '../../../data/observacion_manifestaciones.csv?raw';
import { fichaNino } from './consultas';
import { ninosEnAlcance } from './trayectoria';
import { rankingBrecha } from './rankingBrecha';
import type { Nivel } from './tipos';

const HOY = new Date('2026-01-01');

// Niveles: cada tramo de edad corresponde a un nivel esperado creciente, para
// construir casos de brecha controlados en el conjunto sintético en memoria.
const niveles: Nivel[] = [
  { nivel: 1, nombreNivel: 'Atención inicial', edadMinMeses: 0, edadMaxMeses: 2, descripcion: '' },
  { nivel: 5, nombreNivel: 'Juego simbólico', edadMinMeses: 2, edadMaxMeses: 60, descripcion: '' },
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

// N1..N4 en la sala J1/SA; con nivel esperado 5 para su edad (2024-01-01 → 24
// meses al 2026-01-01). N0 sin observaciones. N3 y N4 empatan en diferencia −3.
const datos: Datos = {
  niveles,
  jardines: [],
  ninos: [
    nino('N0', 'J1', 'SA'),
    nino('N1', 'J1', 'SA'),
    nino('N2', 'J1', 'SA'),
    nino('N4', 'J1', 'SA'),
    nino('N3', 'J1', 'SA'),
    nino('N5', 'J1', 'SB'),
    nino('N6', 'J2', 'SA'),
  ],
  observaciones: [
    obs('O1', 'N1', '2025-05-10', 1), // diferencia 1 − 5 = −4 (más rezagado)
    obs('O2', 'N2', '2025-05-10', 4), // diferencia 4 − 5 = −1
    obs('O3', 'N3', '2025-05-10', 2), // diferencia 2 − 5 = −3 (empate con N4)
    obs('O4', 'N4', '2025-05-10', 2), // diferencia 2 − 5 = −3 (empate con N3)
    obs('O5', 'N5', '2025-05-10', 1), // otra sala
    obs('O6', 'N6', '2025-05-10', 1), // otro jardín
  ],
  manifestaciones: [],
  observacionManifestaciones: [],
};

const salaJ1SA = () =>
  ninosEnAlcance(datos.ninos, { rol: 'parvularia', idJardin: 'J1', salaGrupo: 'SA' });

describe('rankingBrecha · orden', () => {
  it('ordena por diferencia ascendente (más rezagado primero) y brecha descendente', () => {
    const filas = rankingBrecha(datos, salaJ1SA(), { hoy: HOY });
    const rankeables = filas.filter((f) => f.diferencia !== null);
    expect(rankeables.map((f) => f.idNino)).toEqual(['N1', 'N3', 'N4', 'N2']);
    expect(rankeables.map((f) => f.diferencia)).toEqual([-4, -3, -3, -1]);
    expect(rankeables.map((f) => f.brecha)).toEqual([4, 3, 3, 1]);
    // La brecha (magnitud) queda en orden descendente para los rankeables.
    const brechas = rankeables.map((f) => f.brecha as number);
    for (let i = 1; i < brechas.length; i += 1) {
      expect(brechas[i - 1]).toBeGreaterThanOrEqual(brechas[i] as number);
    }
  });

  it('empates deterministas por idNino y estables entre ejecuciones', () => {
    const a = rankingBrecha(datos, salaJ1SA(), { hoy: HOY }).map((f) => f.idNino);
    const b = rankingBrecha(datos, [...salaJ1SA()].reverse(), { hoy: HOY }).map((f) => f.idNino);
    expect(a).toEqual(b);
    const idxN3 = a.indexOf('N3');
    const idxN4 = a.indexOf('N4');
    expect(idxN3).toBeLessThan(idxN4); // 'N3'.localeCompare('N4') < 0
  });

  it('es una función pura: no muta las entradas', () => {
    const ninos = salaJ1SA();
    const copiaIds = ninos.map((n) => n.idNino);
    const obsAntes = datos.observaciones.length;
    rankingBrecha(datos, ninos, { hoy: HOY });
    expect(ninos.map((n) => n.idNino)).toEqual(copiaIds);
    expect(datos.observaciones.length).toBe(obsAntes);
  });
});

describe('rankingBrecha · niño sin observaciones', () => {
  it('coloca al final a quien no tiene observaciones suficientes, con brecha nula', () => {
    const filas = rankingBrecha(datos, salaJ1SA(), { hoy: HOY });
    const ultima = filas[filas.length - 1];
    expect(ultima?.idNino).toBe('N0');
    expect(ultima?.diferencia).toBeNull();
    expect(ultima?.brecha).toBeNull();
    expect(ultima?.nObservaciones).toBe(0);
    expect(ultima?.razon).toContain('Sin observaciones suficientes');
    // Nunca antes de un niño/a con brecha medible.
    const idxN0 = filas.findIndex((f) => f.idNino === 'N0');
    const ultimoRankeable = filas.reduce(
      (acc, f, i) => (f.diferencia !== null ? i : acc),
      -1,
    );
    expect(idxN0).toBeGreaterThan(ultimoRankeable);
  });

  it('minObservaciones=2 manda al final a quien tiene una sola observación', () => {
    const unaObs: Datos = {
      ...datos,
      ninos: [nino('U1', 'J1', 'SA'), nino('U2', 'J1', 'SA')],
      observaciones: [obs('P1', 'U1', '2025-05-10', 1), obs('P2', 'U2', '2025-06-10', 2)],
    };
    const ninos = ninosEnAlcance(unaObs.ninos, { rol: 'parvularia', idJardin: 'J1', salaGrupo: 'SA' });
    const conMin1 = rankingBrecha(unaObs, ninos, { hoy: HOY, minObservaciones: 1 });
    expect(conMin1.find((f) => f.idNino === 'U1')?.diferencia).not.toBeNull();
    const conMin2 = rankingBrecha(unaObs, ninos, { hoy: HOY, minObservaciones: 2 });
    const u1Min2 = conMin2.find((f) => f.idNino === 'U1');
    expect(u1Min2?.diferencia).toBeNull();
    expect(u1Min2?.nObservaciones).toBe(1);
  });
});

describe('rankingBrecha · alcance por rol', () => {
  it('la parvularia solo rankea su sala', () => {
    const filas = rankingBrecha(datos, salaJ1SA(), { hoy: HOY });
    const ids = filas.map((f) => f.idNino);
    expect(ids).toEqual(expect.arrayContaining(['N0', 'N1', 'N2', 'N3', 'N4']));
    expect(ids).not.toContain('N5'); // otra sala del mismo jardín
    expect(ids).not.toContain('N6'); // otro jardín
  });

  it('la directora de un jardín no ve otros jardines', () => {
    const ninosJ1 = ninosEnAlcance(datos.ninos, { rol: 'directora', idJardin: 'J1' });
    const ids = rankingBrecha(datos, ninosJ1, { hoy: HOY }).map((f) => f.idNino);
    expect(ids).toContain('N5'); // misma sala SB del jardín J1 sí entra
    expect(ids).not.toContain('N6'); // jardín J2 queda fuera
  });

  it('la directora con idJardin null ve todos los jardines del alcance', () => {
    const todos = ninosEnAlcance(datos.ninos, { rol: 'directora', idJardin: null });
    const ids = rankingBrecha(datos, todos, { hoy: HOY }).map((f) => f.idNino);
    expect(ids).toContain('N6');
    expect(ids).toHaveLength(datos.ninos.length);
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

describe('rankingBrecha · paridad con la ficha (NINO-00002, data/*.csv)', () => {
  it('la diferencia del ranking coincide con la "Diferencia" de la ficha', () => {
    const nino = datosCsv.ninos.find((n) => n.idNino === 'NINO-00002');
    expect(nino).toBeDefined();
    const ficha = fichaNino(datosCsv, 'NINO-00002', HOY);
    expect(ficha).not.toBeNull();
    const filas = rankingBrecha(datosCsv, [nino!], { hoy: HOY });
    const fila = filas.find((f) => f.idNino === 'NINO-00002');
    expect(fila).toBeDefined();
    expect(fila!.diferencia).toBe(ficha!.brecha);
    expect(fila!.nivelActual).toBe(ficha!.nivelVigente);
    expect(fila!.nivelEsperado).toBe(ficha!.nivelEsperado);
    expect(fila!.edadMeses).toBe(ficha!.edadMeses);
    expect(fila!.nObservaciones).toBe(ficha!.observaciones.length);
  });

  it('no reimplementa el cálculo: toda fila rankeable iguala la ficha', () => {
    const alcance = datosCsv.ninos.slice(0, 20);
    const filas = rankingBrecha(datosCsv, alcance, { hoy: HOY });
    for (const fila of filas) {
      const ficha = fichaNino(datosCsv, fila.idNino, HOY);
      expect(ficha).not.toBeNull();
      if (fila.diferencia !== null) {
        expect(fila.diferencia).toBe(ficha!.brecha);
      }
    }
  });
});
