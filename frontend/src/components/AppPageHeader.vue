<template>
  <div
    class="app-page-header row items-end q-col-gutter-md"
    :class="{ 'app-page-header--compact': compact }"
  >
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
  compact: { type: Boolean, default: false },
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
.app-page-header--compact {
  align-items: flex-start;
  margin-bottom: var(--app-space-md);
}
.app-page-header--compact > .col {
  min-width: 0;
}
.app-page-header--compact > .col-auto {
  align-items: center;
  flex-wrap: nowrap;
}
.app-page-header--compact h1 {
  font-size: clamp(18px, 1.5vw, 21px);
}
.app-page-header--compact .text-body2 {
  font-size: 12px;
  line-height: 1.35;
}
.app-page-header--compact :deep(.q-btn-group .q-btn) {
  min-height: 30px;
  padding: 0 10px;
  font-size: 12px;
}
@media (max-width: 700px) {
  .app-page-header--compact {
    row-gap: var(--app-space-sm);
  }
  .app-page-header--compact > .col {
    flex: 1 0 100%;
  }
}
</style>
