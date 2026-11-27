<template>
  <div class="app-empty column items-center text-center">
    <q-icon :name="icon" size="48px" class="app-empty__icon" />
    <div class="text-subtitle1 q-mt-sm">{{ title }}</div>
    <div v-if="message" class="text-body2 text-app-muted">{{ message }}</div>
    <div v-if="$slots.default" class="q-mt-md"><slot /></div>
  </div>
</template>

<script setup>
/** Placeholder for "nothing here": empty tables, no results, no access. */
defineProps({
  icon: { type: String, default: 'inbox' },
  title: { type: String, default: 'Nothing here yet' },
  message: { type: String, default: '' },
})
</script>

<style scoped lang="scss">
.app-empty {
  padding: var(--app-space-xl) var(--app-space-md);
  width: 100%;
}
.app-empty__icon {
  color: var(--app-text-muted);
}
</style>
