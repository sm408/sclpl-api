import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import { initGateway } from './gateway'

const app = createApp(App)

app.use(createPinia())
app.use(router)

// Initialize the gateway based on environment configuration
initGateway()

app.mount('#app')
