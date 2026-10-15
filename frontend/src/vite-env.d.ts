/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base del backend IntegrAI para datos VIVOS (GET /api/datos). Sin definir -> CSV estáticos. */
  readonly VITE_API_BASE?: string;
  /** Fuente de revisión de profesoras. Solo "api" activa el backend; cualquier otro valor usa demo. */
  readonly VITE_REVISION?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
