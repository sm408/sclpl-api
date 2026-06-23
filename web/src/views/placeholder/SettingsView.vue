<script setup lang="ts">
import { useThemeStore } from '@/stores/theme'
import type { ThemeName, DensityName } from '@/stores/theme'

const themeStore = useThemeStore()

const themes: { value: ThemeName; label: string }[] = [
  { value: 'dark', label: 'Dark' },
  { value: 'light', label: 'Light' },
  { value: 'high-contrast', label: 'High Contrast' },
  { value: 'system', label: 'System' },
]

const densities: { value: DensityName; label: string }[] = [
  { value: 'comfortable', label: 'Comfortable' },
  { value: 'compact', label: 'Compact' },
]
</script>

<template>
  <div class="settings">
    <h1>Settings</h1>

    <section class="settings-section">
      <h2>Appearance</h2>

      <div class="setting-row">
        <label class="setting-label" id="theme-label">Theme</label>
        <div class="setting-control" role="radiogroup" aria-labelledby="theme-label">
          <button
            v-for="t in themes"
            :key="t.value"
            class="setting-option"
            :class="{ active: themeStore.theme === t.value }"
            role="radio"
            :aria-checked="themeStore.theme === t.value"
            @click="themeStore.setTheme(t.value)"
          >
            {{ t.label }}
          </button>
        </div>
      </div>

      <div class="setting-row">
        <label class="setting-label" id="density-label">Density</label>
        <div class="setting-control" role="radiogroup" aria-labelledby="density-label">
          <button
            v-for="d in densities"
            :key="d.value"
            class="setting-option"
            :class="{ active: themeStore.density === d.value }"
            role="radio"
            :aria-checked="themeStore.density === d.value"
            @click="themeStore.setDensity(d.value)"
          >
            {{ d.label }}
          </button>
        </div>
      </div>

      <div class="setting-row">
        <label class="setting-label" for="motion-toggle">Reduced Motion</label>
        <div class="setting-control">
          <button
            id="motion-toggle"
            class="setting-toggle"
            :class="{ active: themeStore.reducedMotion }"
            role="switch"
            :aria-checked="themeStore.reducedMotion"
            @click="themeStore.setReducedMotion(!themeStore.reducedMotion)"
          >
            <span class="toggle-track">
              <span class="toggle-thumb" />
            </span>
            <span>{{ themeStore.reducedMotion ? 'On' : 'Off' }}</span>
          </button>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.settings {
  display: flex;
  flex-direction: column;
  gap: var(--density-space-5);
  max-width: 640px;
}

h1 { font-size: var(--density-font-xl); font-weight: 600; }
h2 { font-size: var(--density-font-lg); font-weight: 600; color: var(--text-secondary); }

.settings-section {
  display: flex;
  flex-direction: column;
  gap: var(--density-space-4);
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--density-space-4);
}

.setting-label {
  font-size: var(--density-font-md);
  color: var(--text-primary);
  min-width: 120px;
}

.setting-control {
  display: flex;
  gap: var(--density-space-1);
}

.setting-option {
  padding: var(--density-space-2) var(--density-space-3);
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-md);
  background: var(--surface-raised);
  color: var(--text-secondary);
  font-size: var(--density-font-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.setting-option:hover {
  border-color: var(--accent-primary);
  color: var(--text-primary);
}

.setting-option.active {
  background: var(--accent-primary-muted);
  border-color: var(--accent-primary);
  color: var(--accent-primary);
}

.setting-toggle {
  display: flex;
  align-items: center;
  gap: var(--density-space-2);
  padding: 0;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: var(--density-font-sm);
  cursor: pointer;
}

.toggle-track {
  position: relative;
  width: 36px;
  height: 20px;
  border-radius: var(--density-radius-full);
  background: var(--surface-border);
  transition: background var(--transition-fast);
}

.setting-toggle.active .toggle-track {
  background: var(--accent-primary);
}

.toggle-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: white;
  transition: transform var(--transition-fast);
}

.setting-toggle.active .toggle-thumb {
  transform: translateX(16px);
}
</style>
