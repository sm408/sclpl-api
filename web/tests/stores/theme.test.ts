/**
 * Theme store tests.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useThemeStore } from '@/stores/theme'

describe('ThemeStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    // Reset localStorage
    localStorage.clear()
    // Reset data attributes
    document.documentElement.removeAttribute('data-theme')
    document.documentElement.removeAttribute('data-density')
    document.documentElement.removeAttribute('data-motion')
  })

  it('defaults to dark theme', () => {
    const store = useThemeStore()
    expect(store.theme).toBe('dark')
  })

  it('defaults to comfortable density', () => {
    const store = useThemeStore()
    expect(store.density).toBe('comfortable')
  })

  it('defaults to no reduced motion', () => {
    const store = useThemeStore()
    expect(store.reducedMotion).toBe(false)
  })

  it('sets theme and applies to document', () => {
    const store = useThemeStore()
    store.setTheme('light')
    expect(store.theme).toBe('light')
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
  })

  it('sets density and applies to document', () => {
    const store = useThemeStore()
    store.setDensity('compact')
    expect(store.density).toBe('compact')
    expect(document.documentElement.getAttribute('data-density')).toBe('compact')
  })

  it('sets reduced motion and applies to document', () => {
    const store = useThemeStore()
    store.setReducedMotion(true)
    expect(store.reducedMotion).toBe(true)
    expect(document.documentElement.getAttribute('data-motion')).toBe('reduced')
  })

  it('removes data-motion when reduced motion is disabled', () => {
    const store = useThemeStore()
    store.setReducedMotion(true)
    store.setReducedMotion(false)
    expect(document.documentElement.hasAttribute('data-motion')).toBe(false)
  })

  it('cycles through themes', () => {
    const store = useThemeStore()
    store.setTheme('dark')
    store.cycleTheme()
    expect(store.theme).toBe('light')
    store.cycleTheme()
    expect(store.theme).toBe('high-contrast')
    store.cycleTheme()
    expect(store.theme).toBe('dark')
  })

  it('resolves system theme to dark when media query matches', () => {
    // Mock matchMedia
    vi.spyOn(window, 'matchMedia').mockReturnValue({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    } as unknown as MediaQueryList)

    const store = useThemeStore()
    store.setTheme('system')
    expect(store.resolvedTheme()).toBe('dark')
  })

  it('resolves system theme to light when media query does not match', () => {
    vi.spyOn(window, 'matchMedia').mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    } as unknown as MediaQueryList)

    const store = useThemeStore()
    store.setTheme('system')
    expect(store.resolvedTheme()).toBe('light')
  })

  it('persists theme to localStorage', () => {
    const store = useThemeStore()
    store.setTheme('light')
    expect(localStorage.getItem('sclplapi:theme')).toBe('light')
  })

  it('persists density to localStorage', () => {
    const store = useThemeStore()
    store.setDensity('compact')
    expect(localStorage.getItem('sclplapi:density')).toBe('compact')
  })

  it('reads persisted theme from localStorage', () => {
    localStorage.setItem('sclplapi:theme', 'light')
    const store = useThemeStore()
    expect(store.theme).toBe('light')
  })

  it('reads persisted density from localStorage', () => {
    localStorage.setItem('sclplapi:density', 'compact')
    const store = useThemeStore()
    expect(store.density).toBe('compact')
  })

  it('init applies all settings', () => {
    const store = useThemeStore()
    store.setTheme('light')
    store.setDensity('compact')
    store.setReducedMotion(true)

    // Reset document
    document.documentElement.removeAttribute('data-theme')
    document.documentElement.removeAttribute('data-density')
    document.documentElement.removeAttribute('data-motion')

    store.init()

    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
    expect(document.documentElement.getAttribute('data-density')).toBe('compact')
    expect(document.documentElement.getAttribute('data-motion')).toBe('reduced')
  })
})
