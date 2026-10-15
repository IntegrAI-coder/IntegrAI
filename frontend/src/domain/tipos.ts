export type FormatoCaptura = 'texto' | 'audio' | 'video';

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
