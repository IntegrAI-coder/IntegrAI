import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { cargarDatos, urlEventos, type Datos } from './cargar';

type Estado =
  | { estado: 'cargando' }
  | { estado: 'error'; mensaje: string }
  | { estado: 'listo'; datos: Datos };

const DatosContext = createContext<Estado | null>(null);
const VersionContext = createContext<number>(0);

const REFRESCO_MS = 60_000; // respaldo por polling (por si SSE no está disponible)

export function DatosProvider({ children }: { children: ReactNode }) {
  const [estado, setEstado] = useState<Estado>({ estado: 'cargando' });
  const [version, setVersion] = useState(0);
  const temporizador = useRef<ReturnType<typeof setTimeout> | null>(null);

  const recargar = useCallback(async () => {
    try {
      const datos = await cargarDatos();
      setEstado({ estado: 'listo', datos });
      setVersion((v) => v + 1);
    } catch (error: unknown) {
      setEstado({
        estado: 'error',
        mensaje: error instanceof Error ? error.message : 'Error desconocido',
      });
    }
  }, []);

  // Agrupa ráfagas de eventos en una sola recarga.
  const programarRecarga = useCallback(() => {
    if (temporizador.current) {
      clearTimeout(temporizador.current);
    }
    temporizador.current = setTimeout(() => {
      void recargar();
    }, 400);
  }, [recargar]);

  // Carga inicial.
  useEffect(() => {
    void recargar();
  }, [recargar]);

  // Tiempo real: SSE (avisos del backend al registrar una observación) + respaldo por polling.
  useEffect(() => {
    const url = urlEventos();
    let fuente: EventSource | null = null;
    if (url) {
      fuente = new EventSource(url);
      fuente.onmessage = () => programarRecarga();
      // si la conexión se cae, EventSource reintenta solo; el polling cubre el resto.
    }
    const interval = setInterval(programarRecarga, REFRESCO_MS);
    return () => {
      fuente?.close();
      clearInterval(interval);
      if (temporizador.current) {
        clearTimeout(temporizador.current);
      }
    };
  }, [programarRecarga]);

  return (
    <DatosContext.Provider value={estado}>
      <VersionContext.Provider value={version}>{children}</VersionContext.Provider>
    </DatosContext.Provider>
  );
}

export function useEstadoDatos(): Estado {
  const estado = useContext(DatosContext);
  if (!estado) {
    throw new Error('useEstadoDatos debe usarse dentro de DatosProvider');
  }
  return estado;
}

/** Sube en cada recarga en vivo (SSE o polling). Útil para vistas que cargan sus propios datos. */
export function useVersionDatos(): number {
  return useContext(VersionContext);
}
