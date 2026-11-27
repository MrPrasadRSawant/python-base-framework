<template>
  <AppFormDialog
    :model-value="modelValue"
    title="Create user"
    submit-label="Create user"
    width="560px"
    :loading="loading"
    :error="error"
    @update:model-value="emit('update:modelValue', $event)"
    @submit="submit"
  >
    <p class="create-user__intro">Add a person to the workspace and assign their initial access.</p>
    <q-input
      v-model="form.full_name"
      outlined
      label="Full name"
      autocomplete="name"
      maxlength="255"
      :rules="[(value) => !!value?.trim() || 'Enter a name']"
      lazy-rules
    />
    <q-input
      v-model="form.username"
      outlined
      label="Username"
      autocomplete="off"
      maxlength="64"
      hint="Unique sign-in name. It can differ from the email address."
      :rules="[
        (value) =>
          /^[A-Za-z][A-Za-z0-9_]{1,63}$/.test(value?.trim() || '') ||
          'Use 2–64 letters, numbers, or underscores; start with a letter',
      ]"
      lazy-rules
    />
    <q-input
      v-model="form.email"
      outlined
      type="email"
      label="Work email"
      autocomplete="email"
      maxlength="255"
      :rules="[
        (value) => !!value?.trim() || 'Enter an email',
        (value) => /.+@.+\..+/.test(value) || 'Enter a valid email',
      ]"
      lazy-rules
    />
    <q-input
      v-model="form.password"
      outlined
      :type="showPassword ? 'text' : 'password'"
      label="Password"
      autocomplete="new-password"
      :rules="[
        (value) => value.length >= 12 || 'Use at least 12 characters',
        (value) => value.length <= 128 || 'Use at most 128 characters',
      ]"
      lazy-rules
    >
      <template #append>
        <q-btn
          flat
          round
          dense
          :icon="showPassword ? 'visibility_off' : 'visibility'"
          :aria-label="showPassword ? 'Hide password' : 'Show password'"
          @click="showPassword = !showPassword"
        />
      </template>
    </q-input>
    <q-select
      v-model="form.roles"
      outlined
      multiple
      use-chips
      emit-value
      map-options
      label="Roles"
      :options="roleOptions"
      :loading="rolesLoading"
      :disable="rolesLoading || !roleOptions.length"
      hint="Optional. A user without roles can sign in but has no module access."
    />
    <p v-if="rolesError" class="create-user__roles-error">{{ rolesError }}</p>
  </AppFormDialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'

import AppFormDialog from '@/components/AppFormDialog.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  roles: { type: Array, default: () => [] },
  rolesLoading: { type: Boolean, default: false },
  rolesError: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'submit'])

const form = reactive({ full_name: '', username: '', email: '', password: '', roles: [] })
const showPassword = ref(false)
const roleOptions = computed(() =>
  props.roles.map((role) => ({ label: role.name, value: role.code })),
)

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    Object.assign(form, { full_name: '', username: '', email: '', password: '', roles: [] })
    showPassword.value = false
  },
)

function submit() {
  emit('submit', {
    full_name: form.full_name.trim(),
    username: form.username.trim(),
    email: form.email.trim().toLowerCase(),
    password: form.password,
    roles: [...form.roles],
  })
}
</script>

<style scoped lang="scss">
.create-user__intro {
  margin: 0;
  color: var(--app-text-muted);
  font-size: 13px;
}

.create-user__roles-error {
  margin: 0;
  color: var(--app-warning);
  font-size: 12px;
}
</style>
