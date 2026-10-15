import Papa from 'papaparse';
import type {
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
}

type Fila = Record<string, string>;

async function leerCsv(ruta: string): Promise<Fila[]> {
  const respuesta = await fetch(ruta);
  if (!respuesta.ok) {
    throw new Error(`No se pudo cargar ${ruta} (${respuesta.status})`);
  }
  const texto = await respuesta.text();
  const resultado = Papa.parse<Fila>(texto, {
    header: true,
    skipEmptyLines: true,
  });
  return resultado.data;
}

export async function cargarDatos(): Promise<Datos> {
  const [
    nivelesRaw,
    jardinesRaw,
    ninosRaw,
    observacionesRaw,
    manifestacionesRaw,
    observacionManifestacionesRaw,
  ] = await Promise.all([
    leerCsv('/ruta_niveles.csv'),
    leerCsv('/jardines.csv'),
    leerCsv('/ninos.csv'),
    leerCsv('/observaciones.csv'),
    leerCsv('/manifestaciones.csv'),
    leerCsv('/observacion_manifestaciones.csv'),
  ]);

  const niveles: Nivel[] = nivelesRaw.map((f) => ({
    nivel: Number(f.nivel),
    nombreNivel: f.nombre_nivel ?? '',
    edadMinMeses: Number(f.edad_min_meses),
    edadMaxMeses: Number(f.edad_max_meses),
    descripcion: f.descripcion ?? '',
  }));

  const jardines: Jardin[] = jardinesRaw.map((f) => ({
    idJardin: f.id_jardin ?? '',
    nombreFantasia: f.nombre_fantasia ?? '',
    comuna: f.comuna ?? '',
    region: f.region ?? '',
  }));

  const ninos: Nino[] = ninosRaw.map((f) => ({
    idNino: f.id_nino ?? '',
    fechaNacimiento: f.fecha_nacimiento ?? '',
    idJardin: f.id_jardin ?? '',
    salaGrupo: f.sala_grupo ?? '',
    fechaIngreso: f.fecha_ingreso ?? '',
  }));

  const observaciones: Observacion[] = observacionesRaw.map((f) => ({
    idObservacion: f.id_observacion ?? '',
    idNino: f.id_nino ?? '',
    fechaObservacion: f.fecha_observacion ?? '',
    formatoCaptura: f.formato_captura ?? '',
    nivelEstimado: Number(f.nivel_estimado),
  }));

  const manifestaciones: Manifestacion[] = manifestacionesRaw.map((f) => ({
    idManifestacion: f.id_manifestacion ?? '',
    nivel: Number(f.nivel),
    dominio: f.dominio ?? '',
    textoObservable: f.texto_observable ?? '',
  }));

  const observacionManifestaciones: ObservacionManifestacion[] =
    observacionManifestacionesRaw.map((f) => ({
      idObservacion: f.id_observacion ?? '',
      idManifestacion: f.id_manifestacion ?? '',
    }));

  return {
    niveles,
    jardines,
    ninos,
    observaciones,
    manifestaciones,
    observacionManifestaciones,
  };
}
