/**
 * Application entry point.
 *
 * Initializes the gateway, creates the Vue app with Pinia and Vue Router,
 * registers PrimeVue (unstyled), and mounts the application.
 */

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import { VueQueryPlugin } from '@tanstack/vue-query'
import App from './App.vue'
import { router } from './router'
import { initGateway } from './gateway'

async function bootstrap(): Promise<void> {
  // Initialize the gateway based on environment configuration.
  // Must complete before any component calls getGateway().
  await initGateway()

  const app = createApp(App)

  const pinia = createPinia()
  app.use(pinia)

  // TanStack Vue Query for server state management
  app.use(VueQueryPlugin)

  // PrimeVue with unstyled mode (we use our own design tokens)
  app.use(PrimeVue, {
    unstyled: true,
  })

  app.use(router)

  app.mount('#app')
}

bootstrap()
