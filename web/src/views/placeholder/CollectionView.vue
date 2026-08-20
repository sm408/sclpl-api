<script setup lang="ts">
import { useRoute } from 'vue-router'
const route = useRoute()
</script>

<template>
  <div class="placeholder">
    <h1>Collection</h1>
    <p>Viewing collection {{ route.params.collectionId }}</p>
  </div>
</template>

<style scoped>
.placeholder {
  display: flex;
  flex-direction: column;
  gap: var(--density-space-3);
}
h1 { font-size: var(--density-font-xl); font-weight: 600; }
p { color: var(--text-secondary); }
</style>
