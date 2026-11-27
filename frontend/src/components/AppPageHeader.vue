<template>
  <div class="app-page-header row items-end q-col-gutter-md">
    <div class="col">
      <q-breadcrumbs v-if="breadcrumbs.length" class="text-caption text-app-muted q-mb-xs">
        <q-breadcrumbs-el
          v-for="crumb in breadcrumbs"
          :key="crumb.label"
          :label="crumb.label"
          :to="crumb.to"
        />
      </q-breadcrumbs>
      <h1>{{ title }}</h1>
      <div v-if="subtitle" class="text-body2 text-app-muted q-mt-xs">{{ subtitle }}</div>
    </div>
    <div v-if="$slots.actions" class="col-auto row q-gutter-sm">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
/**
 * Title bar at the top of every page.
 *
 *   <AppPageHeader title="Users" subtitle="Accounts and access">
 *     <template #actions><q-btn color="primary" label="Add user" /></template>
 *   </AppPageHeader>
 */
defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  breadcrumbs: { type: Array, default: () => [] }, // [{label, to?}]
})
</script>

<style scoped lang="scss">
.app-page-header {
  margin-bottom: var(--app-space-lg);
}

.app-page-header h1 {
  margin: 0;
  font-size: clamp(23px, 2vw, 28px);
  font-weight: 700;
  letter-spacing: -0.035em;
  line-height: 1.25;
}
</style>
