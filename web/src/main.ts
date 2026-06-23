import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import { initGateway } from './gateway'

async function bootstrap(): Promise<void> {
  // Initialize the gateway based on environment configuration.
  // Must complete before any component calls getGateway().
  await initGateway()

  const app = createApp(App)

  app.use(createPinia())
  app.use(router)

  app.mount('#app')
}

bootstrap()
