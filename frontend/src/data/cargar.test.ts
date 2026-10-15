import { afterEach, describe, expect, it, vi } from 'vitest';

describe('cargarDatos con API', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it('carga coordinación aunque educadoras.csv no esté publicado', async () => {
    vi.stubEnv('VITE_API_BASE', '');
    const fetchMock = vi.fn(async (entrada: string | URL | Request) => {
      const ruta = String(entrada);
      if (ruta === '/api/datos') {
        return new Response(JSON.stringify({
          ruta_niveles: [],
          jardines: [],
          ninos: [],
          observaciones: [],
          manifestaciones: [],
          observacion_manifestaciones: [],
          evaluaciones: [],
        }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response('', { status: 404 });
    });
    vi.stubGlobal('fetch', fetchMock);

    const { cargarDatos } = await import('./cargar');
    const datos = await cargarDatos();

    expect(datos.jardines).toEqual([]);
    expect(datos.educadoras[6]?.idEducadora).toBe('EDU-0007');
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith('/api/datos');
  });
});
