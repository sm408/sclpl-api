/**
 * Root application component.
 *
 * Loads the design tokens and renders the AppShell.
 */

<script setup lang="ts">
import '@/assets/tokens.css'
import AppShell from '@/components/shell/AppShell.vue'
</script>

<template>
  <AppShell />
</template>
