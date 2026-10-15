const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
const TOKEN = import.meta.env.VITE_API_TOKEN ?? '';

export interface ArchivoRepo {
  ruta: string;
  lenguaje: string;
  extension: string;
  tamano: number;
}

export interface ResumenRepo {
  total: number;
  bytes: number;
  por_lenguaje: Record<string, number>;
}

export interface RepoResumen {
  owner: string;
  repo: string;
  ruta: string;
  total_archivos: number;
  archivos: ArchivoRepo[];
  resumen?: ResumenRepo;
}

export interface ResultadoClon {
  ok: boolean;
  mensaje: string;
  owner: string;
  repo: string;
  ruta: string;
  actualizado: boolean;
}

export interface ResultadoIndexado {
  source_repo: string;
  archivos: number;
  trozos: number;
  truncado: boolean;
  modelo_embedding: string;
  dimensiones: number;
}

export interface RespuestaClon {
  clone: ResultadoClon;
  repo?: RepoResumen;
  indexado?: ResultadoIndexado;
}

async function pedir<T>(ruta: string, opciones?: RequestInit): Promise<T> {
  const respuesta = await fetch(`${BASE}${ruta}`, {
    ...opciones,
    headers: {
      'Content-Type': 'application/json',
      ...(TOKEN ? { 'X-Api-Key': TOKEN } : {}),
      ...(opciones?.headers ?? {}),
    },
  });

  if (!respuesta.ok) {
    let detalle = respuesta.statusText;
    try {
      const cuerpo = (await respuesta.json()) as { detail?: string };
      if (cuerpo.detail) {
        detalle = cuerpo.detail;
      }
    } catch {
      // sin cuerpo JSON: nos quedamos con el statusText
    }
    throw new Error(`API ${respuesta.status}: ${detalle}`);
  }
  return (await respuesta.json()) as T;
}

export function listarRepos(): Promise<{ repos: RepoResumen[] }> {
  return pedir('/api/repos');
}

export function escanearRepo(repo?: string): Promise<{ repos: RepoResumen[] }> {
  return pedir('/api/repos/scan', {
    method: 'POST',
    body: JSON.stringify({ repo: repo ?? null }),
  });
}

export function clonarRepo(url: string, indexar: boolean): Promise<RespuestaClon> {
  return pedir('/api/repos/clone', {
    method: 'POST',
    body: JSON.stringify({ url, indexar }),
  });
}
