import type { Datos } from '../data/cargar';
import type { Evaluacion, Manifestacion, Nino, Nivel, Observacion } from './tipos';
import {
  brecha,
  edadMeses,
  nivelEsperado,
  nivelVigente,
  promedio,
  tieneAlerta,
} from './metrics';

export interface AlumnoCurso {
  idNino: string;
  edadMeses: number;
  nivelVigente: number | null;
  nivelEsperado: number | null;
  brecha: number | null;
  alerta: boolean;
}

export interface ResumenCurso {
  idJardin: string;
  salaGrupo: string;
  nombreJardin: string;
  comuna: string;
  totalNinos: number;
  nivelPromedio: number | null;
  totalAlertas: number;
}

export function claveCurso(idJardin: string, salaGrupo: string): string {
  return `${idJardin}__${salaGrupo}`;
}

/** Nivel CONSOLIDADO por niño/a (la evaluación `global` más reciente que produce el
 *  cron en el backend). Si no hay, el dashboard cae a la observación más reciente. */
function evaluacionesGlobales(datos: Datos): Map<string, Evaluacion> {
  const mapa = new Map<string, Evaluacion>();
  for (const e of datos.evaluaciones ?? []) {
    if (e.dominio !== 'global') continue;
    const previo = mapa.get(e.idNino);
    if (!previo || e.periodo >= previo.periodo) {
      mapa.set(e.idNino, e);
    }
  }
  return mapa;
}

function observacionesDe(datos: Datos): Map<string, Observacion[]> {
  const mapa = new Map<string, Observacion[]>();
  for (const obs of datos.observaciones) {
    const lista = mapa.get(obs.idNino) ?? [];
    lista.push(obs);
    mapa.set(obs.idNino, lista);
  }
  return mapa;
}

export function alumnoDesde(
  nino: Nino,
  observaciones: Observacion[],
  niveles: Nivel[],
  hoy: Date,
  evaluacion?: Evaluacion,
): AlumnoCurso {
  const meses = edadMeses(nino.fechaNacimiento, hoy);
  // Si hay evaluación consolidada del backend, esa manda (nivel + alerta rubric-aware).
  const vigente = evaluacion ? evaluacion.nivel : nivelVigente(observaciones);
  const esperado = nivelEsperado(meses, niveles);
  const valorBrecha = brecha(vigente, esperado);
  const alerta = evaluacion
    ? (evaluacion.alerta ?? '').trim() !== ''
    : tieneAlerta(valorBrecha);
  return {
    idNino: nino.idNino,
    edadMeses: meses,
    nivelVigente: vigente,
    nivelEsperado: esperado,
    brecha: valorBrecha,
    alerta,
  };
}

export function alumnosDeCurso(
  datos: Datos,
  idJardin: string,
  salaGrupo: string,
  hoy: Date,
): AlumnoCurso[] {
  const obsPorNino = observacionesDe(datos);
  const evs = evaluacionesGlobales(datos);
  return datos.ninos
    .filter((n) => n.idJardin === idJardin && n.salaGrupo === salaGrupo)
    .map((n) => alumnoDesde(n, obsPorNino.get(n.idNino) ?? [], datos.niveles, hoy, evs.get(n.idNino)));
}

export function resumenCursos(datos: Datos, hoy: Date): ResumenCurso[] {
  const obsPorNino = observacionesDe(datos);
  const evs = evaluacionesGlobales(datos);
  const jardinPorId = new Map(datos.jardines.map((j) => [j.idJardin, j]));
  const porCurso = new Map<string, { idJardin: string; sala: string; ninos: Nino[] }>();

  for (const nino of datos.ninos) {
    const clave = claveCurso(nino.idJardin, nino.salaGrupo);
    const grupo =
      porCurso.get(clave) ??
      { idJardin: nino.idJardin, sala: nino.salaGrupo, ninos: [] };
    grupo.ninos.push(nino);
    porCurso.set(clave, grupo);
  }

  const resumenes: ResumenCurso[] = [];
  for (const { idJardin, sala, ninos } of porCurso.values()) {
    const alumnos = ninos.map((n) =>
      alumnoDesde(n, obsPorNino.get(n.idNino) ?? [], datos.niveles, hoy, evs.get(n.idNino)),
    );
    const nivelesVigentes = alumnos
      .map((a) => a.nivelVigente)
      .filter((v): v is number => v !== null);
    const jardin = jardinPorId.get(idJardin);
    resumenes.push({
      idJardin,
      salaGrupo: sala,
      nombreJardin: jardin?.nombreFantasia ?? idJardin,
      comuna: jardin?.comuna ?? '',
      totalNinos: ninos.length,
      nivelPromedio: promedio(nivelesVigentes),
      totalAlertas: alumnos.filter((a) => a.alerta).length,
    });
  }

  return resumenes.sort(
    (a, b) =>
      a.nombreJardin.localeCompare(b.nombreJardin) ||
      a.salaGrupo.localeCompare(b.salaGrupo),
  );
}

export function distribucionNiveles(alumnos: AlumnoCurso[]): { nivel: number; total: number }[] {
  const conteo = new Map<number, number>();
  for (let nivel = 1; nivel <= 9; nivel += 1) {
    conteo.set(nivel, 0);
  }
  for (const alumno of alumnos) {
    if (alumno.nivelVigente !== null) {
      conteo.set(alumno.nivelVigente, (conteo.get(alumno.nivelVigente) ?? 0) + 1);
    }
  }
  return [...conteo.entries()].map(([nivel, total]) => ({ nivel, total }));
}

export interface ObservacionDetallada {
  idObservacion: string;
  fechaObservacion: string;
  formatoCaptura: string;
  nivelEstimado: number;
  manifestaciones: Manifestacion[];
}

export interface FichaNino {
  nino: Nino;
  edadMeses: number;
  nivelVigente: number | null;
  nivelEsperado: number | null;
  brecha: number | null;
  alerta: boolean;
  observaciones: ObservacionDetallada[];
}

export function fichaNino(
  datos: Datos,
  idNino: string,
  hoy: Date,
): FichaNino | null {
  const nino = datos.ninos.find((n) => n.idNino === idNino);
  if (!nino) {
    return null;
  }

  const manifestacionPorId = new Map(
    datos.manifestaciones.map((m) => [m.idManifestacion, m]),
  );
  const manifestacionesPorObs = new Map<string, Manifestacion[]>();
  for (const om of datos.observacionManifestaciones) {
    const man = manifestacionPorId.get(om.idManifestacion);
    if (!man) {
      continue;
    }
    const lista = manifestacionesPorObs.get(om.idObservacion) ?? [];
    lista.push(man);
    manifestacionesPorObs.set(om.idObservacion, lista);
  }

  const observaciones = datos.observaciones
    .filter((o) => o.idNino === idNino)
    .sort((a, b) => a.fechaObservacion.localeCompare(b.fechaObservacion));

  const alumno = alumnoDesde(nino, observaciones, datos.niveles, hoy, evaluacionesGlobales(datos).get(idNino));

  const detalladas: ObservacionDetallada[] = observaciones.map((o) => ({
    idObservacion: o.idObservacion,
    fechaObservacion: o.fechaObservacion,
    formatoCaptura: o.formatoCaptura,
    nivelEstimado: o.nivelEstimado,
    manifestaciones: manifestacionesPorObs.get(o.idObservacion) ?? [],
  }));

  return {
    nino,
    edadMeses: alumno.edadMeses,
    nivelVigente: alumno.nivelVigente,
    nivelEsperado: alumno.nivelEsperado,
    brecha: alumno.brecha,
    alerta: alumno.alerta,
    observaciones: detalladas,
  };
}

export function nivelPorNumero(niveles: Nivel[]): Map<number, Nivel> {
  return new Map(niveles.map((n) => [n.nivel, n]));
}
