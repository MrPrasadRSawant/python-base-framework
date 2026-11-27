<template>
  <q-dialog :model-value="modelValue" persistent @update:model-value="close">
    <q-card class="app-form-dialog" :style="{ width }">
      <q-form greedy @submit.prevent="emit('submit')">
        <q-card-section class="row items-center">
          <div class="text-h6">{{ title }}</div>
          <q-space />
          <q-btn flat round dense icon="close" :disable="loading" @click="close(false)" />
        </q-card-section>

        <q-separator />

        <q-card-section class="app-form-dialog__body q-gutter-md">
          <q-banner v-if="error" dense rounded class="bg-negative text-white">
            <template #avatar><q-icon name="error_outline" /></template>
            {{ error }}
          </q-banner>
          <slot />
        </q-card-section>

        <q-separator />

        <q-card-actions align="right" class="q-pa-md">
          <q-btn flat no-caps label="Cancel" :disable="loading" @click="close(false)" />
          <q-btn
            type="submit"
            unelevated
            no-caps
            color="primary"
            :label="submitLabel"
            :loading="loading"
          />
        </q-card-actions>
      </q-form>
    </q-card>
  </q-dialog>
</template>

<script setup>
/**
 * Create / edit form in a dialog. Fields go in the default slot; Quasar field
 * `rules` run before `submit` is emitted. The parent saves, then closes it.
 *
 *   <AppFormDialog v-model="open" title="Add user" :loading="saving"
 *     :error="formError" @submit="save">
 *     <q-input v-model="form.email" label="Email" outlined :rules="[required]" />
 *   </AppFormDialog>
 */
defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, required: true },
  submitLabel: { type: String, default: 'Save' },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' }, // shown above the fields
  width: { type: String, default: '520px' },
})
const emit = defineEmits(['update:modelValue', 'submit'])

function close(value = false) {
  emit('update:modelValue', value)
}
</script>

<style scoped lang="scss">
.app-form-dialog {
  max-width: 94vw;
  border-radius: var(--app-radius-lg);
}
.app-form-dialog__body {
  max-height: 70vh;
  overflow-y: auto;
}
</style>
