import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import { cargarDatos, type Datos } from './cargar';

type Estado =
  | { estado: 'cargando' }
  | { estado: 'error'; mensaje: string }
  | { estado: 'listo'; datos: Datos };

const DatosContext = createContext<Estado | null>(null);

export function DatosProvider({ children }: { children: ReactNode }) {
  const [estado, setEstado] = useState<Estado>({ estado: 'cargando' });

  useEffect(() => {
    let activo = true;
    cargarDatos()
      .then((datos) => {
        if (activo) {
          setEstado({ estado: 'listo', datos });
        }
      })
      .catch((error: unknown) => {
        if (activo) {
          const mensaje =
            error instanceof Error ? error.message : 'Error desconocido';
          setEstado({ estado: 'error', mensaje });
        }
      });
    return () => {
      activo = false;
    };
  }, []);

  return <DatosContext.Provider value={estado}>{children}</DatosContext.Provider>;
}

export function useEstadoDatos(): Estado {
  const estado = useContext(DatosContext);
  if (!estado) {
    throw new Error('useEstadoDatos debe usarse dentro de DatosProvider');
  }
  return estado;
}
