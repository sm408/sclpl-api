<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <main class="not-found">
    <h1>404</h1>
    <p>Page not found</p>
    <button @click="router.push('/')">Go Home</button>
  </main>
</template>

<style scoped>
.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  font-family: system-ui, -apple-system, sans-serif;
}
button {
  margin-top: 1rem;
  padding: 0.5rem 1.5rem;
  border: 1px solid #d1d5db;
  border-radius: 0.375rem;
  background: white;
  cursor: pointer;
}
button:hover {
  background: #f3f4f6;
}
</style>
