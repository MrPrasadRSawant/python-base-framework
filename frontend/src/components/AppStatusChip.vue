<template>
  <q-chip dense square outline class="app-status-chip" :class="`app-status-chip--${look.tone}`">
    <q-icon v-if="look.icon" :name="look.icon" size="14px" class="q-mr-xs" />
    {{ label || look.label }}
  </q-chip>
</template>

<script setup>
/**
 * Small colored status badge, consistent across modules.
 *
 *   <AppStatusChip status="active" />
 *   <AppStatusChip :status="row.is_active ? 'active' : 'disabled'" />
 *   <AppStatusChip status="system" label="Built-in" />
 */
import { computed } from 'vue'

const LOOKS = {
  active: { tone: 'positive', label: 'Active', icon: 'check_circle' },
  disabled: { tone: 'muted', label: 'Disabled', icon: 'block' },
  system: { tone: 'info', label: 'System', icon: 'lock' },
  success: { tone: 'positive', label: 'Success', icon: 'check' },
  failed: { tone: 'negative', label: 'Failed', icon: 'error' },
  warning: { tone: 'warning', label: 'Warning', icon: 'warning' },
  expired: { tone: 'warning', label: 'Expired', icon: 'schedule' },
}

const props = defineProps({
  status: { type: String, required: true }, // a key of LOOKS
  label: { type: String, default: '' },
})

const look = computed(() => LOOKS[props.status] || { tone: 'muted', label: props.status })
</script>

<style scoped lang="scss">
.app-status-chip {
  border-radius: var(--app-radius-sm);
  font-weight: 600;
}

.app-status-chip--positive {
  color: var(--app-positive);
}

.app-status-chip--negative {
  color: var(--app-negative);
}

.app-status-chip--warning {
  color: var(--app-warning);
}

.app-status-chip--info {
  color: var(--app-info);
}

.app-status-chip--muted {
  color: var(--app-text-muted);
}
</style>
