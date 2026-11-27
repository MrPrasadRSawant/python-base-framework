<template>
  <q-dialog :model-value="modelValue" persistent @update:model-value="close">
    <q-card class="app-dialog">
      <q-card-section class="row items-center no-wrap q-gutter-md">
        <q-avatar
          :icon="danger ? 'warning' : 'help_outline'"
          :color="danger ? 'negative' : 'primary'"
          text-color="white"
        />
        <div>
          <div class="text-h6">{{ title }}</div>
          <div class="text-body2 text-app-muted">{{ message }}</div>
        </div>
      </q-card-section>
      <q-card-actions align="right" class="q-pa-md">
        <q-btn flat no-caps label="Cancel" :disable="loading" @click="close(false)" />
        <q-btn
          unelevated
          no-caps
          :color="danger ? 'negative' : 'primary'"
          :label="confirmLabel"
          :loading="loading"
          @click="emit('confirm')"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup>
/**
 * Yes / no confirmation. The parent closes it after the action succeeds.
 *
 *   <AppConfirmDialog v-model="confirmOpen" danger title="Delete user?"
 *     message="They will be signed out." confirm-label="Delete"
 *     :loading="deleting" @confirm="deleteUser" />
 */
defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, required: true },
  message: { type: String, default: '' },
  confirmLabel: { type: String, default: 'Confirm' },
  danger: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'confirm'])

function close(value = false) {
  emit('update:modelValue', value)
}
</script>

<style scoped lang="scss">
.app-dialog {
  width: 440px;
  max-width: 92vw;
  border-radius: var(--app-radius-lg);
}
</style>
