/**
 * Theme store — manages appearance preferences.
 *
 * Controls theme (dark / light / high-contrast / system),
 * density (compact / comfortable), and reduced-motion override.
 * Persists to localStorage and applies data-attributes on <html>.
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'

export type ThemeName = 'dark' | 'light' | 'high-contrast' | 'system'
export type DensityName = 'compact' | 'comfortable'

const STORAGE_KEY_THEME = 'sclplapi:theme'
const STORAGE_KEY_DENSITY = 'sclplapi:density'
const STORAGE_KEY_MOTION = 'sclplapi:motion'

function resolveSystemTheme(): 'dark' | 'light' {
  if (typeof window === 'undefined') return 'dark'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function readStorage(key: string, fallback: string): string {
  try {
    return localStorage.getItem(key) ?? fallback
  } catch {
    return fallback
  }
}

export const useThemeStore = defineStore('theme', () => {
  // ── State ──────────────────────────────────────────────────────────────

  const theme = ref<ThemeName>(
    readStorage(STORAGE_KEY_THEME, 'dark') as ThemeName,
  )
  const density = ref<DensityName>(
    readStorage(STORAGE_KEY_DENSITY, 'comfortable') as DensityName,
  )
  const reducedMotion = ref<boolean>(
    readStorage(STORAGE_KEY_MOTION, 'false') === 'true',
  )

  // ── Derived ────────────────────────────────────────────────────────────

  /** The resolved theme name (never 'system'). */
  function resolvedTheme(): 'dark' | 'light' {
    return theme.value === 'system' ? resolveSystemTheme() : theme.value
  }

  // ── Actions ────────────────────────────────────────────────────────────

  function setTheme(t: ThemeName): void {
    theme.value = t
    applyTheme()
    persist()
  }

  function setDensity(d: DensityName): void {
    density.value = d
    applyDensity()
    persist()
  }

  function setReducedMotion(on: boolean): void {
    reducedMotion.value = on
    applyMotion()
    persist()
  }

  function cycleTheme(): void {
    const order: ThemeName[] = ['dark', 'light', 'high-contrast']
    const resolved = resolvedTheme()
    const idx = order.indexOf(resolved)
    setTheme(order[(idx + 1) % order.length]!)
  }

  // ── DOM application ────────────────────────────────────────────────────

  function applyTheme(): void {
    if (typeof document === 'undefined') return
    document.documentElement.setAttribute('data-theme', resolvedTheme())
  }

  function applyDensity(): void {
    if (typeof document === 'undefined') return
    document.documentElement.setAttribute('data-density', density.value)
  }

  function applyMotion(): void {
    if (typeof document === 'undefined') return
    if (reducedMotion.value) {
      document.documentElement.setAttribute('data-motion', 'reduced')
    } else {
      document.documentElement.removeAttribute('data-motion')
    }
  }

  function applyAll(): void {
    applyTheme()
    applyDensity()
    applyMotion()
  }

  function persist(): void {
    try {
      localStorage.setItem(STORAGE_KEY_THEME, theme.value)
      localStorage.setItem(STORAGE_KEY_DENSITY, density.value)
      localStorage.setItem(STORAGE_KEY_MOTION, String(reducedMotion.value))
    } catch {
      // localStorage may be unavailable
    }
  }

  // ── System theme listener ──────────────────────────────────────────────

  let cleanup: (() => void) | null = null

  function watchSystemTheme(): void {
    if (typeof window === 'undefined') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = (): void => {
      if (theme.value === 'system') applyTheme()
    }
    mq.addEventListener('change', handler)
    cleanup = () => mq.removeEventListener('change', handler)
  }

  // ── Init ───────────────────────────────────────────────────────────────

  function init(): void {
    applyAll()
    watchSystemTheme()
  }

  return {
    // State
    theme,
    density,
    reducedMotion,
    // Derived
    resolvedTheme,
    // Actions
    setTheme,
    setDensity,
    setReducedMotion,
    cycleTheme,
    init,
    // Cleanup
    dispose(): void {
      cleanup?.()
    },
  }
})
