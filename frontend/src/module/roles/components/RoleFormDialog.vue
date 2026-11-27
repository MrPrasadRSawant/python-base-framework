<template>
  <AppFormDialog
    :model-value="modelValue"
    :title="role ? 'Edit role' : 'Create role'"
    :submit-label="role ? 'Save changes' : 'Create role'"
    width="560px"
    :loading="loading"
    :error="error"
    @update:model-value="emit('update:modelValue', $event)"
    @submit="submit"
  >
    <p class="role-form__intro">
      {{
        role
          ? 'Update the role details. Its code stays the same.'
          : 'Create a role, then assign its permissions.'
      }}
    </p>
    <q-input
      v-model="form.name"
      outlined
      label="Role name"
      maxlength="128"
      :rules="[(value) => !!value?.trim() || 'Enter a role name']"
      lazy-rules
    />
    <q-input
      v-model="form.code"
      outlined
      label="Role code"
      maxlength="64"
      :readonly="Boolean(role)"
      :hint="
        role
          ? 'The code cannot be changed.'
          : 'Lowercase letters, numbers, and underscores. Starts with a letter.'
      "
      :rules="[
        (value) =>
          /^[a-z][a-z0-9_]{1,63}$/.test(value || '') ||
          'Use 2–64 lowercase letters, numbers, or underscores; start with a letter',
      ]"
      lazy-rules
    />
    <q-input
      v-model="form.description"
      outlined
      type="textarea"
      autogrow
      label="Description"
      maxlength="512"
      hint="Optional. Explain who should receive this role."
    />
  </AppFormDialog>
</template>

<script setup>
import { reactive, watch } from 'vue'

import AppFormDialog from '@/components/AppFormDialog.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  role: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'submit'])

const form = reactive({ name: '', code: '', description: '' })

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    Object.assign(form, {
      name: props.role?.name || '',
      code: props.role?.code || '',
      description: props.role?.description || '',
    })
  },
)

function submit() {
  const details = { name: form.name.trim(), description: form.description.trim() || null }
  emit('submit', props.role ? details : { ...details, code: form.code.trim() })
}
</script>

<style scoped lang="scss">
.role-form__intro {
  margin: 0;
  color: var(--app-text-muted);
  font-size: 13px;
}
</style>
