<template>
  <div class="brand-logo" :class="{ 'brand-logo--inverse': inverse }">
    <img class="brand-logo__mark" :src="brandMark" alt="" width="40" height="40" />
    <div class="brand-logo__copy">
      <span class="brand-logo__name">{{ appName }}</span>
      <span v-if="!compact" class="brand-logo__tagline">Enterprise foundation</span>
    </div>
  </div>
</template>

<script setup>
import { appName, brandMark } from '@/brand'

defineProps({
  compact: { type: Boolean, default: false },
  inverse: { type: Boolean, default: false },
})
</script>

<style scoped lang="scss">
.brand-logo {
  display: inline-flex;
  align-items: center;
  gap: 11px;
  color: var(--app-text);
  line-height: 1.1;
}

.brand-logo--inverse {
  color: var(--app-sidebar-text);
}

.brand-logo__mark {
  display: block;
  flex: 0 0 40px;
  border-radius: var(--app-radius-md);
}

.brand-logo--inverse .brand-logo__mark {
  border: 1px solid var(--app-sidebar-border);
}

.brand-logo__copy {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.brand-logo__name {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.025em;
}

.brand-logo__tagline {
  color: var(--app-text-muted);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.085em;
  text-transform: uppercase;
}

.brand-logo--inverse .brand-logo__tagline {
  color: var(--app-sidebar-muted);
}
</style>
