/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base del backend IntegrAI para datos VIVOS (GET /api/datos). Sin definir -> CSV estáticos. */
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
