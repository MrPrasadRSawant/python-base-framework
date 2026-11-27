<template>
  <q-page class="app-page flex flex-center">
    <AppEmptyState
      icon="lock"
      title="You don't have access to this page"
      message="Ask an administrator for the permission you need."
    >
      <q-btn color="primary" unelevated no-caps label="Go home" :to="{ name: 'home' }" />
    </AppEmptyState>
  </q-page>
</template>

<script setup>
import AppEmptyState from '@/components/AppEmptyState.vue'
</script>
