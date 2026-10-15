import Papa from 'papaparse';
import type {
  Evaluacion,
  Jardin,
  Manifestacion,
  Nino,
  Nivel,
  Observacion,
  ObservacionManifestacion,
} from '../domain/tipos';

export interface Datos {
  niveles: Nivel[];
  jardines: Jardin[];
  ninos: Nino[];
  observaciones: Observacion[];
  manifestaciones: Manifestacion[];
  observacionManifestaciones: ObservacionManifestacion[];
  /** Nivel consolidado + alerta (que produce el cron en el backend). Opcional:
   *  en el modo CSV estático no existe y el dashboard usa la observación más reciente. */
  evaluaciones?: Evaluacion[];
}

type Fila = Record<string, string>;

/**
 * Fuente de datos. Si `VITE_API_BASE` está definido, el dashboard lee los datos
 * VIVOS del backend (`GET /api/datos`: incluye JAR-EQUIPO y las observaciones que
 * llegan por WhatsApp). Si no está definido —o si la API falla— cae de vuelta a
 * los CSV estáticos (dataset sintético E-1) que ya vivían en `data/`.
 *
 *   VITE_API_BASE sin definir  -> CSV estáticos (GitHub Pages)
 *   VITE_API_BASE="" (vacío)   -> mismo origen (CloudFront enruta /api/* al backend)
 *   VITE_API_BASE="http://..." -> backend absoluto (requiere CORS)
 */
const RAW_API_BASE = import.meta.env.VITE_API_BASE;
const USAR_API = RAW_API_BASE !== undefined;
const API_BASE = (RAW_API_BASE ?? '').replace(/\/+$/, '');

interface DatosCrudos {
  ruta_niveles?: Fila[];
  jardines?: Fila[];
  ninos?: Fila[];
  observaciones?: Fila[];
  manifestaciones?: Fila[];
  observacion_manifestaciones?: Fila[];
  evaluaciones?: Fila[];
}

function nivelesDesde(filas: Fila[]): Nivel[] {
  return filas.map((f) => ({
    nivel: Number(f.nivel),
    nombreNivel: f.nombre_nivel ?? '',
    edadMinMeses: Number(f.edad_min_meses),
    edadMaxMeses: Number(f.edad_max_meses),
    descripcion: f.descripcion ?? '',
  }));
}

function jardinesDesde(filas: Fila[]): Jardin[] {
  return filas.map((f) => ({
    idJardin: f.id_jardin ?? '',
    nombreFantasia: f.nombre_fantasia ?? '',
    comuna: f.comuna ?? '',
    region: f.region ?? '',
  }));
}

function ninosDesde(filas: Fila[]): Nino[] {
  return filas.map((f) => ({
    idNino: f.id_nino ?? '',
    fechaNacimiento: f.fecha_nacimiento ?? '',
    idJardin: f.id_jardin ?? '',
    salaGrupo: f.sala_grupo ?? '',
    fechaIngreso: f.fecha_ingreso ?? '',
  }));
}

function observacionesDesde(filas: Fila[]): Observacion[] {
  return filas.map((f) => ({
    idObservacion: f.id_observacion ?? '',
    idNino: f.id_nino ?? '',
    fechaObservacion: f.fecha_observacion ?? '',
    formatoCaptura: f.formato_captura ?? '',
    nivelEstimado: Number(f.nivel_estimado),
  }));
}

function manifestacionesDesde(filas: Fila[]): Manifestacion[] {
  return filas.map((f) => ({
    idManifestacion: f.id_manifestacion ?? '',
    nivel: Number(f.nivel),
    dominio: f.dominio ?? '',
    textoObservable: f.texto_observable ?? '',
  }));
}

function omDesde(filas: Fila[]): ObservacionManifestacion[] {
  return filas.map((f) => ({
    idObservacion: f.id_observacion ?? '',
    idManifestacion: f.id_manifestacion ?? '',
  }));
}

function evaluacionesDesde(filas: Fila[]): Evaluacion[] {
  return filas.map((f) => ({
    idNino: f.id_nino ?? '',
    dominio: f.dominio ?? '',
    nivel: Number(f.nivel),
    margen: Number(f.margen),
    periodo: f.periodo ?? '',
    tendencia: f.tendencia ?? '',
    alerta: f.alerta && f.alerta !== '' ? f.alerta : null,
  }));
}

function armarDatos(r: DatosCrudos): Datos {
  return {
    niveles: nivelesDesde(r.ruta_niveles ?? []),
    jardines: jardinesDesde(r.jardines ?? []),
    ninos: ninosDesde(r.ninos ?? []),
    observaciones: observacionesDesde(r.observaciones ?? []),
    manifestaciones: manifestacionesDesde(r.manifestaciones ?? []),
    observacionManifestaciones: omDesde(r.observacion_manifestaciones ?? []),
    evaluaciones: evaluacionesDesde(r.evaluaciones ?? []),
  };
}

async function desdeApi(): Promise<Datos> {
  const respuesta = await fetch(`${API_BASE}/api/datos`);
  if (!respuesta.ok) {
    throw new Error(`El backend respondió ${respuesta.status} en /api/datos`);
  }
  return armarDatos((await respuesta.json()) as DatosCrudos);
}

function rutaCsv(nombre: string): string {
  return `${import.meta.env.BASE_URL}${nombre}`;
}

async function leerCsv(nombre: string): Promise<Fila[]> {
  const ruta = rutaCsv(nombre);
  const respuesta = await fetch(ruta);
  if (!respuesta.ok) {
    throw new Error(`No se pudo cargar ${ruta} (${respuesta.status})`);
  }
  const texto = await respuesta.text();
  const resultado = Papa.parse<Fila>(texto, { header: true, skipEmptyLines: true });
  return resultado.data;
}

async function desdeCsv(): Promise<Datos> {
  const [
    ruta_niveles,
    jardines,
    ninos,
    observaciones,
    manifestaciones,
    observacion_manifestaciones,
  ] = await Promise.all([
    leerCsv('ruta_niveles.csv'),
    leerCsv('jardines.csv'),
    leerCsv('ninos.csv'),
    leerCsv('observaciones.csv'),
    leerCsv('manifestaciones.csv'),
    leerCsv('observacion_manifestaciones.csv'),
  ]);
  return armarDatos({
    ruta_niveles,
    jardines,
    ninos,
    observaciones,
    manifestaciones,
    observacion_manifestaciones,
  });
}

export async function cargarDatos(): Promise<Datos> {
  if (USAR_API) {
    try {
      return await desdeApi();
    } catch (error) {
      console.warn('No se pudo leer /api/datos; uso los CSV estáticos.', error);
    }
  }
  return desdeCsv();
}
