/**
 * SettingsView — full application settings panel.
 *
 * Sections: Appearance, Editor, History, Startup, Commands, Licenses.
 * Server-side settings show a restart-required banner when changed.
 */

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { getGateway } from '@/gateway'
import type { ThemeName, DensityName } from '@/stores/theme'
import type {
  AppSettings,
  AppSettingsUpdate,
  CommandEntry,
  LicenseEntry,
} from '@/types/api'
import {
  Palette,
  Type,
  Clock,
  Rocket,
  Keyboard,
  Scale,
  AlertTriangle,
  Check,
} from 'lucide-vue-next'

const themeStore = useThemeStore()
const gateway = getGateway()

// ── State ──────────────────────────────────────────────────────────────

const activeSection = ref<'appearance' | 'editor' | 'history' | 'startup' | 'commands' | 'licenses'>('appearance')
const settings = ref<AppSettings | null>(null)
const commands = ref<CommandEntry[]>([])
const licenses = ref<LicenseEntry[]>([])
const licenseFilter = ref('')
const saved = ref(false)
const loading = ref(true)

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

const wordWrapOptions = [
  { value: 'off', label: 'Off' },
  { value: 'on', label: 'On' },
  { value: 'wordWrapColumn', label: 'Wrap at Column' },
]

const sections = [
  { id: 'appearance' as const, label: 'Appearance', icon: Palette },
  { id: 'editor' as const, label: 'Editor', icon: Type },
  { id: 'history' as const, label: 'History', icon: Clock },
  { id: 'startup' as const, label: 'Startup', icon: Rocket },
  { id: 'commands' as const, label: 'Keyboard Shortcuts', icon: Keyboard },
  { id: 'licenses' as const, label: 'Licenses', icon: Scale },
]

// ── Derived ────────────────────────────────────────────────────────────

const filteredLicenses = computed(() => {
  if (!licenseFilter.value) return licenses.value
  const q = licenseFilter.value.toLowerCase()
  return licenses.value.filter(
    (l) => l.name.toLowerCase().includes(q) || l.license.toLowerCase().includes(q),
  )
})

const commandsByCategory = computed(() => {
  const groups = new Map<string, CommandEntry[]>()
  for (const cmd of commands.value) {
    const cat = cmd.category || 'General'
    const group = groups.get(cat) ?? []
    group.push(cmd)
    groups.set(cat, group)
  }
  return groups
})

// ── Actions ────────────────────────────────────────────────────────────

async function loadSettings(): Promise<void> {
  loading.value = true
  try {
    const [s, c, l] = await Promise.all([
      gateway.settings.get(),
      gateway.commands.list().catch(() => ({ items: [], total: 0 })),
      gateway.licenses.list().catch(() => ({ items: [], total: 0 })),
    ])
    settings.value = s
    commands.value = c.items
    licenses.value = l.items
  } catch {
    // Settings unavailable
  } finally {
    loading.value = false
  }
}

async function saveServerSettings(updates: AppSettingsUpdate): Promise<void> {
  if (!settings.value) return
  try {
    settings.value = await gateway.settings.update(updates)
    saved.value = true
    setTimeout(() => { saved.value = false }, 2000)
  } catch {
    // Save failed
  }
}

function updateEditorSetting(key: string, value: unknown): void {
  if (!settings.value) return
  saveServerSettings({ editor: { ...settings.value.editor, [key]: value } })
}

function updateHistorySetting(key: string, value: unknown): void {
  if (!settings.value) return
  saveServerSettings({ history: { ...settings.value.history, [key]: value } })
}

function updateStartupSetting(key: string, value: unknown): void {
  if (!settings.value) return
  saveServerSettings({ startup: { ...settings.value.startup, [key]: value } })
}

function updateServerSetting(key: string, value: unknown): void {
  saveServerSettings({ [key]: value })
}

onMounted(loadSettings)
</script>

<template>
  <div class="settings-view">
    <!-- Sidebar navigation -->
    <nav class="settings-nav" aria-label="Settings sections">
      <button
        v-for="section in sections"
        :key="section.id"
        class="nav-item"
        :class="{ active: activeSection === section.id }"
        @click="activeSection = section.id"
      >
        <component :is="section.icon" :size="16" />
        <span>{{ section.label }}</span>
      </button>
    </nav>

    <!-- Content area -->
    <div class="settings-content">
      <div v-if="loading" class="settings-loading">Loading settings...</div>

      <template v-else-if="settings">
        <!-- Restart banner -->
        <div v-if="settings.restartRequired" class="restart-banner" role="alert">
          <AlertTriangle :size="16" />
          <span>Some settings require a server restart to take effect.</span>
        </div>

        <!-- Save confirmation -->
        <Transition name="fade">
          <div v-if="saved" class="save-toast" role="status">
            <Check :size="14" />
            <span>Settings saved</span>
          </div>
        </Transition>

        <!-- Appearance -->
        <section v-if="activeSection === 'appearance'" class="settings-section">
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

        <!-- Editor -->
        <section v-if="activeSection === 'editor'" class="settings-section">
          <h2>Editor</h2>

          <div class="setting-row">
            <label class="setting-label" for="tab-size">Tab Size</label>
            <div class="setting-control">
              <select
                id="tab-size"
                :value="settings.editor.tabSize"
                class="setting-select"
                @change="updateEditorSetting('tabSize', Number(($event.target as HTMLSelectElement).value))"
              >
                <option :value="2">2 spaces</option>
                <option :value="4">4 spaces</option>
                <option :value="8">8 spaces</option>
              </select>
            </div>
          </div>

          <div class="setting-row">
            <label class="setting-label" for="word-wrap">Word Wrap</label>
            <div class="setting-control">
              <select
                id="word-wrap"
                :value="settings.editor.wordWrap"
                class="setting-select"
                @change="updateEditorSetting('wordWrap', ($event.target as HTMLSelectElement).value)"
              >
                <option v-for="opt in wordWrapOptions" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </option>
              </select>
            </div>
          </div>

          <div class="setting-row">
            <label class="setting-label" for="minimap-toggle">Minimap</label>
            <div class="setting-control">
              <button
                id="minimap-toggle"
                class="setting-toggle"
                :class="{ active: settings.editor.minimap }"
                role="switch"
                :aria-checked="settings.editor.minimap"
                @click="updateEditorSetting('minimap', !settings.editor.minimap)"
              >
                <span class="toggle-track">
                  <span class="toggle-thumb" />
                </span>
                <span>{{ settings.editor.minimap ? 'On' : 'Off' }}</span>
              </button>
            </div>
          </div>

          <div class="setting-row">
            <label class="setting-label" for="font-size">Font Size</label>
            <div class="setting-control">
              <input
                id="font-size"
                type="number"
                :value="settings.editor.fontSize"
                min="10"
                max="24"
                class="setting-input-sm"
                @change="updateEditorSetting('fontSize', Number(($event.target as HTMLInputElement).value))"
              />
              <span class="setting-unit">px</span>
            </div>
          </div>
        </section>

        <!-- History -->
        <section v-if="activeSection === 'history'" class="settings-section">
          <h2>History</h2>

          <div class="setting-row">
            <label class="setting-label" for="max-entries">Max History Entries</label>
            <div class="setting-control">
              <input
                id="max-entries"
                type="number"
                :value="settings.history.maxEntries"
                min="10"
                max="10000"
                class="setting-input-sm"
                @change="updateHistorySetting('maxEntries', Number(($event.target as HTMLInputElement).value))"
              />
            </div>
          </div>

          <div class="setting-row">
            <label class="setting-label" for="auto-clear">Auto-clear After (days)</label>
            <div class="setting-control">
              <input
                id="auto-clear"
                type="number"
                :value="settings.history.autoClearDays"
                min="0"
                max="365"
                class="setting-input-sm"
                @change="updateHistorySetting('autoClearDays', Number(($event.target as HTMLInputElement).value))"
              />
              <span class="setting-hint">0 = never auto-clear</span>
            </div>
          </div>

          <div class="setting-row">
            <label class="setting-label">Max History (Server)</label>
            <div class="setting-control">
              <input
                type="number"
                :value="settings.maxHistoryEntries"
                min="10"
                max="10000"
                class="setting-input-sm"
                @change="updateServerSetting('maxHistoryEntries', Number(($event.target as HTMLInputElement).value))"
              />
              <span class="restart-badge">restart</span>
            </div>
          </div>
        </section>

        <!-- Startup -->
        <section v-if="activeSection === 'startup'" class="settings-section">
          <h2>Startup</h2>

          <div class="setting-row">
            <label class="setting-label" for="reopen-tabs">Reopen Last Tabs</label>
            <div class="setting-control">
              <button
                id="reopen-tabs"
                class="setting-toggle"
                :class="{ active: settings.startup.reopenLastTabs }"
                role="switch"
                :aria-checked="settings.startup.reopenLastTabs"
                @click="updateStartupSetting('reopenLastTabs', !settings.startup.reopenLastTabs)"
              >
                <span class="toggle-track">
                  <span class="toggle-thumb" />
                </span>
                <span>{{ settings.startup.reopenLastTabs ? 'On' : 'Off' }}</span>
              </button>
            </div>
          </div>

          <div class="setting-row">
            <label class="setting-label">Default Timeout</label>
            <div class="setting-control">
              <input
                type="number"
                :value="settings.defaultTimeout"
                min="1"
                max="300"
                class="setting-input-sm"
                @change="updateServerSetting('defaultTimeout', Number(($event.target as HTMLInputElement).value))"
              />
              <span class="setting-unit">sec</span>
              <span class="restart-badge">restart</span>
            </div>
          </div>

          <div class="setting-row">
            <label class="setting-label" for="follow-redirects">Follow Redirects</label>
            <div class="setting-control">
              <button
                id="follow-redirects"
                class="setting-toggle"
                :class="{ active: settings.followRedirects }"
                role="switch"
                :aria-checked="settings.followRedirects"
                @click="updateServerSetting('followRedirects', !settings.followRedirects)"
              >
                <span class="toggle-track">
                  <span class="toggle-thumb" />
                </span>
                <span>{{ settings.followRedirects ? 'On' : 'Off' }}</span>
              </button>
              <span class="restart-badge">restart</span>
            </div>
          </div>
        </section>

        <!-- Keyboard Shortcuts -->
        <section v-if="activeSection === 'commands'" class="settings-section">
          <h2>Keyboard Shortcuts</h2>
          <p class="section-desc">All registered commands and their keyboard shortcuts.</p>

          <div v-for="[category, cmds] in commandsByCategory" :key="category" class="shortcut-group">
            <h3 class="shortcut-category">{{ category }}</h3>
            <div v-for="cmd in cmds" :key="cmd.id" class="shortcut-row">
              <span class="shortcut-label">{{ cmd.label }}</span>
              <kbd v-if="cmd.shortcut" class="shortcut-key">{{ cmd.shortcut }}</kbd>
              <span v-else class="shortcut-none">--</span>
            </div>
          </div>
        </section>

        <!-- Licenses -->
        <section v-if="activeSection === 'licenses'" class="settings-section">
          <h2>Licenses</h2>
          <p class="section-desc">Third-party dependency licenses.</p>

          <div class="license-filter">
            <input
              v-model="licenseFilter"
              type="text"
              placeholder="Filter licenses..."
              class="license-search"
            />
            <span class="license-count">{{ filteredLicenses.length }} of {{ licenses.length }}</span>
          </div>

          <div class="license-table-wrap">
            <table class="license-table">
              <thead>
                <tr>
                  <th>Package</th>
                  <th>Version</th>
                  <th>License</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="entry in filteredLicenses" :key="`${entry.source}-${entry.name}`">
                  <td class="license-name">{{ entry.name }}</td>
                  <td class="license-version">{{ entry.version }}</td>
                  <td class="license-type">{{ entry.license }}</td>
                  <td>
                    <span class="license-badge" :class="entry.source">{{ entry.source }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>
    </div>
  </div>
</template>

<style scoped>
.settings-view {
  display: flex;
  gap: var(--density-space-4);
  height: 100%;
  min-height: 0;
}

/* ── Navigation ───────────────────────────────────────────────────── */

.settings-nav {
  display: flex;
  flex-direction: column;
  gap: var(--density-space-1);
  min-width: 180px;
  flex-shrink: 0;
  padding: var(--density-space-2) 0;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--density-space-2);
  padding: var(--density-space-2) var(--density-space-3);
  border: none;
  border-radius: var(--density-radius-md);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--density-font-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
  text-align: left;
}

.nav-item:hover {
  background: var(--surface-raised);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--accent-primary-muted);
  color: var(--accent-primary);
}

/* ── Content ──────────────────────────────────────────────────────── */

.settings-content {
  flex: 1;
  overflow-y: auto;
  min-width: 0;
}

.settings-loading {
  color: var(--text-tertiary);
  font-size: var(--density-font-sm);
  padding: var(--density-space-4);
}

.settings-section {
  display: flex;
  flex-direction: column;
  gap: var(--density-space-4);
  max-width: 640px;
}

h2 {
  font-size: var(--density-font-xl);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

h3 {
  font-size: var(--density-font-md);
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0;
}

.section-desc {
  color: var(--text-tertiary);
  font-size: var(--density-font-sm);
  margin: 0;
}

/* ── Setting rows ─────────────────────────────────────────────────── */

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--density-space-4);
  padding: var(--density-space-2) 0;
}

.setting-label {
  font-size: var(--density-font-md);
  color: var(--text-primary);
  min-width: 160px;
}

.setting-control {
  display: flex;
  align-items: center;
  gap: var(--density-space-2);
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

.setting-select {
  padding: var(--density-space-2) var(--density-space-3);
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-md);
  background: var(--surface-raised);
  color: var(--text-primary);
  font-size: var(--density-font-sm);
  cursor: pointer;
}

.setting-input-sm {
  width: 80px;
  padding: var(--density-space-2) var(--density-space-3);
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-md);
  background: var(--surface-raised);
  color: var(--text-primary);
  font-size: var(--density-font-sm);
  font-family: var(--font-mono);
}

.setting-unit {
  font-size: var(--density-font-xs);
  color: var(--text-tertiary);
}

.setting-hint {
  font-size: var(--density-font-xs);
  color: var(--text-tertiary);
}

.restart-badge {
  font-size: var(--density-font-xs);
  padding: 1px var(--density-space-1);
  border-radius: var(--density-radius-full);
  background: var(--color-warning-bg, #fef3c7);
  color: var(--color-warning-text, #92400e);
  font-weight: 500;
}

/* ── Toggle ───────────────────────────────────────────────────────── */

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

/* ── Restart banner ───────────────────────────────────────────────── */

.restart-banner {
  display: flex;
  align-items: center;
  gap: var(--density-space-2);
  padding: var(--density-space-2) var(--density-space-3);
  border-radius: var(--density-radius-md);
  background: var(--color-warning-bg, #fef3c7);
  color: var(--color-warning-text, #92400e);
  font-size: var(--density-font-sm);
  margin-bottom: var(--density-space-3);
}

/* ── Save toast ───────────────────────────────────────────────────── */

.save-toast {
  position: fixed;
  bottom: var(--density-space-4);
  right: var(--density-space-4);
  display: flex;
  align-items: center;
  gap: var(--density-space-2);
  padding: var(--density-space-2) var(--density-space-3);
  border-radius: var(--density-radius-md);
  background: var(--color-success, #16a34a);
  color: white;
  font-size: var(--density-font-sm);
  z-index: 100;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--transition-fast);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* ── Shortcuts ────────────────────────────────────────────────────── */

.shortcut-group {
  display: flex;
  flex-direction: column;
  gap: var(--density-space-1);
  margin-bottom: var(--density-space-4);
}

.shortcut-category {
  padding-bottom: var(--density-space-1);
  border-bottom: 1px solid var(--surface-border);
}

.shortcut-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--density-space-1) 0;
}

.shortcut-label {
  font-size: var(--density-font-sm);
  color: var(--text-primary);
}

.shortcut-key {
  font-size: var(--density-font-xs);
  font-family: var(--font-mono);
  padding: 1px var(--density-space-2);
  background: var(--surface-raised);
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-sm);
  color: var(--text-secondary);
}

.shortcut-none {
  font-size: var(--density-font-xs);
  color: var(--text-tertiary);
}

/* ── Licenses ─────────────────────────────────────────────────────── */

.license-filter {
  display: flex;
  align-items: center;
  gap: var(--density-space-3);
}

.license-search {
  flex: 1;
  max-width: 300px;
  padding: var(--density-space-2) var(--density-space-3);
  border: 1px solid var(--surface-border);
  border-radius: var(--density-radius-md);
  background: var(--surface-raised);
  color: var(--text-primary);
  font-size: var(--density-font-sm);
}

.license-count {
  font-size: var(--density-font-xs);
  color: var(--text-tertiary);
}

.license-table-wrap {
  overflow-x: auto;
  margin-top: var(--density-space-2);
}

.license-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--density-font-sm);
}

.license-table th {
  text-align: left;
  padding: var(--density-space-2) var(--density-space-3);
  border-bottom: 2px solid var(--surface-border);
  color: var(--text-secondary);
  font-weight: 600;
}

.license-table td {
  padding: var(--density-space-2) var(--density-space-3);
  border-bottom: 1px solid var(--surface-border);
  color: var(--text-primary);
}

.license-name {
  font-family: var(--font-mono);
  font-weight: 500;
}

.license-version {
  font-family: var(--font-mono);
  color: var(--text-tertiary);
}

.license-type {
  color: var(--text-secondary);
}

.license-badge {
  font-size: var(--density-font-xs);
  padding: 1px var(--density-space-1);
  border-radius: var(--density-radius-full);
  font-weight: 500;
}

.license-badge.npm {
  background: #fef3c7;
  color: #92400e;
}

.license-badge.python {
  background: #dbeafe;
  color: #1e40af;
}
</style>
