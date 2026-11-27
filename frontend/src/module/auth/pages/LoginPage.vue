<template>
  <div class="app-card login-card">
    <div class="login-card__eyebrow">YOUR WORKSPACE</div>
    <h2>Welcome back</h2>
    <p class="login-card__intro">Sign in to continue to your workspace.</p>

    <q-banner v-if="errorMessage" class="login-card__error q-mb-lg">
      <template #avatar><q-icon name="error_outline" /></template>
      {{ errorMessage }}
    </q-banner>

    <q-form greedy class="login-card__form" @submit.prevent="submit">
      <q-input
        v-model="identifier"
        type="text"
        label="Username or email"
        outlined
        autocomplete="username"
        :rules="[(v) => !!v?.trim() || 'Enter your username or email']"
        lazy-rules
      >
        <template #prepend><q-icon name="person_outline" size="20px" /></template>
      </q-input>

      <q-input
        v-model="password"
        :type="showPassword ? 'text' : 'password'"
        label="Password"
        outlined
        autocomplete="current-password"
        :rules="[(v) => !!v || 'Enter your password']"
        lazy-rules
      >
        <template #prepend><q-icon name="lock_outline" size="20px" /></template>
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

      <q-btn
        type="submit"
        color="primary"
        unelevated
        no-caps
        class="full-width login-card__submit"
        label="Sign in"
        :loading="loading"
      />
    </q-form>
    <div class="login-card__note">
      <q-icon name="verified_user" size="16px" />
      Protected access for authorized users
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { safeRedirect } from '../guards.js'
import { useAuthStore } from '../store.js'

const MESSAGES = {
  invalid_credentials: 'Incorrect username, email or password.',
  network_error: 'Cannot reach the server. Check your connection and try again.',
  timeout: 'The server took too long to answer. Try again.',
}

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const identifier = ref('')
const password = ref('')
const showPassword = ref(false)
const loading = ref(false)
const errorMessage = ref('')

async function submit() {
  loading.value = true
  errorMessage.value = ''
  try {
    await auth.login(identifier.value.trim(), password.value)
    await router.replace(safeRedirect(route.query.redirect))
  } catch (err) {
    password.value = ''
    errorMessage.value =
      err.code === 'rate_limited'
        ? `Too many attempts. Try again in ${err.retryAfter || 60} seconds.`
        : MESSAGES[err.code] || err.message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.login-card {
  padding: clamp(24px, 3vw, 40px);
}

.login-card__eyebrow {
  margin-bottom: var(--app-space-sm);
  color: var(--app-primary);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.login-card h2 {
  margin: 0;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.035em;
  line-height: 1.2;
}

.login-card__intro {
  margin: 8px 0 28px;
  color: var(--app-text-muted);
  font-size: 14px;
}

.login-card__form {
  display: grid;
  gap: 4px;
}

.login-card__submit {
  height: 48px;
  margin-top: 4px;
  font-weight: 600;
}

.login-card__error {
  border-radius: var(--app-radius-md);
  background: var(--app-surface-muted);
  color: var(--app-negative);
}

.login-card__note {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-top: var(--app-space-lg);
  color: var(--app-text-muted);
  font-size: 11px;
}
</style>
