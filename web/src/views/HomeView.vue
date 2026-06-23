<script setup lang="ts">
import { useQuery } from '@tanstack/vue-query'
import { getGateway } from '@/gateway'
import type { HealthResponse } from '@/types/api'

const gateway = getGateway()

const { data: health, isLoading, error } = useQuery<HealthResponse>({
  queryKey: ['health'],
  queryFn: () => gateway.health.check(),
  retry: 2,
  staleTime: 30_000,
})
</script>

<template>
  <main class="home">
    <h1>SCLPLAPI Studio</h1>
    <p>Local-first API workflow studio</p>
    <div v-if="isLoading" class="status">Connecting...</div>
    <div v-else-if="error" class="status error">Backend unavailable</div>
    <div v-else-if="health" class="status ok">
      Connected &mdash; v{{ health.version }}
    </div>
  </main>
</template>

<style scoped>
.home {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  font-family: system-ui, -apple-system, sans-serif;
}
.status {
  margin-top: 1rem;
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
}
.status.ok {
  background: #dcfce7;
  color: #166534;
}
.status.error {
  background: #fee2e2;
  color: #991b1b;
}
</style>
