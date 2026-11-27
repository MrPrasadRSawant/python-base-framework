<template>
  <q-btn v-if="auth.user" flat no-caps dense class="user-menu">
    <q-avatar size="32px" color="primary" text-color="white" class="text-weight-bold">
      {{ initials }}
    </q-avatar>
    <span class="q-ml-sm gt-xs">{{ auth.user.full_name }}</span>
    <q-icon name="expand_more" size="18px" />

    <q-menu anchor="bottom right" self="top right" :offset="[0, 8]">
      <q-list class="user-menu__list">
        <q-item>
          <q-item-section>
            <q-item-label class="text-weight-medium">{{ auth.user.full_name }}</q-item-label>
            <q-item-label caption>@{{ auth.user.username }} · {{ auth.user.email }}</q-item-label>
            <div v-if="auth.roles.length" class="q-mt-xs">
              <q-badge
                v-for="role in auth.roles"
                :key="role"
                color="primary"
                outline
                class="q-mr-xs"
                :label="role"
              />
            </div>
          </q-item-section>
        </q-item>
        <q-separator />
        <q-item v-close-popup clickable :disable="signingOut" @click="signOut">
          <q-item-section avatar><q-icon name="logout" /></q-item-section>
          <q-item-section>Sign out</q-item-section>
        </q-item>
      </q-list>
    </q-menu>
  </q-btn>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '../store.js'

const auth = useAuthStore()
const router = useRouter()
const signingOut = ref(false)

const initials = computed(() =>
  (auth.user?.full_name || auth.user?.email || '?')
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join(''),
)

async function signOut() {
  signingOut.value = true
  try {
    await auth.logout()
  } finally {
    signingOut.value = false
    router.replace({ name: 'login' })
  }
}
</script>

<style scoped lang="scss">
.user-menu__list {
  min-width: 240px;
}

.user-menu {
  color: var(--app-text);
}
</style>
