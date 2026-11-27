<template>
  <div class="fullscreen flex flex-center not-found">
    <AppEmptyState
      icon="travel_explore"
      title="Page not found"
      message="The page you are looking for does not exist or was moved."
    >
      <q-btn color="primary" unelevated no-caps label="Go home" to="/" />
    </AppEmptyState>
  </div>
</template>

<script setup>
import AppEmptyState from '@/components/AppEmptyState.vue'
</script>

<style scoped lang="scss">
.not-found {
  background: var(--app-bg);
}
</style>
