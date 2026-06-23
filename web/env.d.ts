/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, unknown>
  export default component
}

/** Gateway mode set at build time or via env variable. */
interface ImportMetaEnv {
  /** 'http' (default) or 'mock' */
  readonly VITE_GATEWAY_MODE: 'http' | 'mock'
  /** Base URL for the API server (defaults to same-origin) */
  readonly VITE_API_BASE_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
