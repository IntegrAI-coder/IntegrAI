import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { Breadcrumbs } from '../components/Breadcrumbs';
import { Tabla, type Columna } from '../components/Tabla';
import { Cargando, ErrorEstado, Vacio } from '../components/Estado';
import { parsearUrlRepo } from '../domain/repos';
import {
  clonarRepo,
  listarRepos,
  type ArchivoRepo,
  type RepoResumen,
} from '../data/api';

function formatearBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  const unidades = ['KB', 'MB', 'GB'];
  let valor = bytes / 1024;
  let indice = 0;
  while (valor >= 1024 && indice < unidades.length - 1) {
    valor /= 1024;
    indice += 1;
  }
  return `${valor.toFixed(1)} ${unidades[indice]}`;
}

const claveRepo = (r: { owner: string; repo: string }) => `${r.owner}/${r.repo}`;

export function Sincronizacion() {
  const [repos, setRepos] = useState<RepoResumen[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [url, setUrl] = useState('');
  const [indexar, setIndexar] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [seleccionado, setSeleccionado] = useState<string | null>(null);

  const recargar = useCallback(async () => {
    setCargando(true);
    try {
      const { repos: lista } = await listarRepos();
      setRepos(lista);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido');
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    void recargar();
  }, [recargar]);

  async function sincronizar(evento: FormEvent) {
    evento.preventDefault();
    const referencia = parsearUrlRepo(url);
    if (!referencia) {
      setError('Ingresa owner/repo o https://github.com/owner/repo');
      return;
    }
    setEnviando(true);
    setError(null);
    setAviso(null);
    try {
      const resultado = await clonarRepo(referencia.url, indexar);
      const partes = [resultado.clone.actualizado ? 'actualizado' : 'clonado'];
      if (resultado.indexado) {
        partes.push(
          `${resultado.indexado.trozos} trozos indexados (${resultado.indexado.modelo_embedding})`,
        );
      }
      setAviso(`${claveRepo(resultado.repo ?? referencia)}: ${partes.join(' · ')}`);
      await recargar();
      setSeleccionado(`${referencia.owner}/${referencia.repo}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido');
    } finally {
      setEnviando(false);
    }
  }

  const columnasRepos = useMemo<Columna<RepoResumen>[]>(
    () => [
      { clave: 'repositorio', encabezado: 'Repositorio', valor: claveRepo },
      {
        clave: 'archivos',
        encabezado: 'Archivos',
        numerica: true,
        valor: (r) => r.total_archivos,
      },
      {
        clave: 'peso',
        encabezado: 'Peso',
        numerica: true,
        valor: (r) => r.resumen?.bytes ?? 0,
        render: (r) => formatearBytes(r.resumen?.bytes ?? 0),
      },
      {
        clave: 'acciones',
        encabezado: 'Acciones',
        ordenable: false,
        valor: () => null,
        render: (r) => (
          <button
            type="button"
            className="enlace-boton"
            onClick={() => setSeleccionado(claveRepo(r))}
          >
            Ver archivos
          </button>
        ),
      },
    ],
    [],
  );

  const columnasArchivos: Columna<ArchivoRepo>[] = [
    { clave: 'ruta', encabezado: 'Archivo', valor: (a) => a.ruta },
    { clave: 'lenguaje', encabezado: 'Lenguaje', valor: (a) => a.lenguaje },
    {
      clave: 'tamano',
      encabezado: 'Tamaño',
      numerica: true,
      valor: (a) => a.tamano,
      render: (a) => formatearBytes(a.tamano),
    },
  ];

  const detalle = repos.find((r) => claveRepo(r) === seleccionado);

  return (
    <>
      <Breadcrumbs migas={[{ etiqueta: 'Sincronización' }]} />
      <h2>Sincronización de repositorios</h2>
      <p className="ayuda">
        Clona un repositorio (solo <code>github.com</code>, https) en
        <code> repos/[owner]/[repo]</code>, lo escanea y, si lo pides, lo indexa en
        el pipeline RAG. Solo se indexa <strong>código sintético</strong>
        (<code>data_type = "synthetic_code"</code>): nunca datos reales de niños y
        niñas.
      </p>

      <form className="panel sync__form" onSubmit={sincronizar}>
        <div className="buscador">
          <label htmlFor="repo-url">Repositorio (owner/repo o URL https)</label>
          <input
            id="repo-url"
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="Ej.: anthropics/claude-cookbooks"
            autoComplete="off"
          />
        </div>
        <label className="sync__check">
          <input
            type="checkbox"
            checked={indexar}
            onChange={(e) => setIndexar(e.target.checked)}
          />
          Indexar en el RAG (trocear + embeddings)
        </label>
        <button type="submit" className="boton" disabled={enviando}>
          {enviando ? 'Sincronizando…' : 'Sincronizar'}
        </button>
      </form>

      {aviso && (
        <p className="estado estado--ok" role="status">
          {aviso}
        </p>
      )}
      {error && <ErrorEstado mensaje={error} />}

      <h3 className="seccion__titulo">Repositorios sincronizados</h3>
      {cargando && <Cargando mensaje="Cargando repositorios…" />}
      {!cargando && repos.length === 0 && (
        <Vacio mensaje="Todavía no hay repositorios. Sincroniza uno para empezar." />
      )}
      {!cargando && repos.length > 0 && (
        <div className="panel">
          <Tabla
            descripcion="Repositorios clonados y su cantidad de archivos"
            filas={repos}
            claveFila={claveRepo}
            columnas={columnasRepos}
          />
        </div>
      )}

      {detalle && (
        <>
          <h3 className="seccion__titulo">
            {claveRepo(detalle)} · {detalle.total_archivos} archivos
          </h3>
          {detalle.resumen && (
            <div className="chips">
              {Object.entries(detalle.resumen.por_lenguaje).map(([lenguaje, n]) => (
                <span key={lenguaje} className="chip">
                  {lenguaje}: {n}
                </span>
              ))}
            </div>
          )}
          <div className="panel">
            <Tabla
              descripcion="Archivos indexables del repositorio"
              filas={detalle.archivos}
              claveFila={(a) => a.ruta}
              columnas={columnasArchivos}
            />
          </div>
        </>
      )}
    </>
  );
}
