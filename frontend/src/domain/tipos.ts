export type FormatoCaptura = 'texto' | 'foto' | 'audio' | 'video';

export interface Nivel {
  nivel: number;
  nombreNivel: string;
  edadMinMeses: number;
  edadMaxMeses: number;
  descripcion: string;
}

export interface Jardin {
  idJardin: string;
  nombreFantasia: string;
  comuna: string;
  region: string;
}

export interface Nino {
  idNino: string;
  fechaNacimiento: string;
  idJardin: string;
  salaGrupo: string;
  fechaIngreso: string;
}

export interface Observacion {
  idObservacion: string;
  idNino: string;
  fechaObservacion: string;
  formatoCaptura: string;
  nivelEstimado: number;
}

export interface Manifestacion {
  idManifestacion: string;
  nivel: number;
  dominio: string;
  textoObservable: string;
}

export interface ObservacionManifestacion {
  idObservacion: string;
  idManifestacion: string;
}

export interface Evaluacion {
  idNino: string;
  dominio: string;
  nivel: number;
  margen: number;
  periodo: string;
  tendencia: string;
  alerta: string | null;
}

export interface Pendiente {
  idPendiente: string;
  idNinoPropuesto: string;
  idEducadora: string | null;
  nivelPropuesto: number | null;
  dominio: string | null;
  margen: number | null;
  motivo: string;
  evidencia: string;
  estado: string;
  creadoEn: string;
  idJardin: string | null;
  salaGrupo: string | null;
}
