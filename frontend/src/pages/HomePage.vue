<template>
  <q-page class="app-page home-page">
    <AppPageHeader
      :title="`Welcome back, ${firstName}`"
      subtitle="A clear view of your access and platform status."
    />

    <div class="home-grid">
      <section class="app-card home-panel home-access" aria-labelledby="access-heading">
        <div class="home-panel__header">
          <div class="home-panel__icon"><q-icon name="admin_panel_settings" size="22px" /></div>
          <div>
            <h2 id="access-heading">Your access</h2>
            <p>Roles and permissions available to your account</p>
          </div>
        </div>

        <div class="home-access__group">
          <div class="home-access__label">Assigned roles</div>
          <div v-if="auth.roles.length" class="home-access__items">
            <q-chip
              v-for="role in auth.roles"
              :key="role"
              square
              color="primary"
              text-color="white"
            >
              {{ role }}
            </q-chip>
          </div>
          <p v-else class="home-access__empty">No roles assigned yet.</p>
        </div>

        <div class="home-access__group">
          <div class="home-access__label">Permissions</div>
          <div v-if="auth.user?.permissions?.length" class="home-access__items">
            <q-chip
              v-for="permission in auth.user.permissions"
              :key="permission"
              square
              outline
              class="home-access__permission"
            >
              {{ permission }}
            </q-chip>
          </div>
          <p v-else class="home-access__empty">Ask an administrator for access to more features.</p>
        </div>
      </section>

      <div class="home-side">
        <section class="app-card home-panel" aria-labelledby="status-heading">
          <div class="home-panel__header">
            <div class="home-panel__icon"><q-icon name="monitor_heart" size="22px" /></div>
            <div>
              <h2 id="status-heading">System health</h2>
              <p>Live service availability</p>
            </div>
          </div>

          <div class="home-status__row">
            <div class="home-status__service"><q-icon name="dns" size="18px" /> API service</div>
            <q-skeleton v-if="healthLoading" type="QChip" width="86px" />
            <AppStatusChip
              v-else
              :status="health?.status === 'ok' ? 'success' : 'failed'"
              :label="health?.status === 'ok' ? 'Healthy' : 'Unavailable'"
            />
          </div>
          <div class="home-status__row">
            <div class="home-status__service"><q-icon name="storage" size="18px" /> Database</div>
            <q-skeleton v-if="healthLoading" type="QChip" width="86px" />
            <AppStatusChip
              v-else
              :status="health?.database === 'ok' ? 'success' : 'failed'"
              :label="health?.database === 'ok' ? 'Healthy' : 'Unavailable'"
            />
          </div>
        </section>

        <section class="app-card home-panel" aria-labelledby="account-heading">
          <div class="home-panel__header">
            <div class="home-panel__icon"><q-icon name="account_circle" size="22px" /></div>
            <div>
              <h2 id="account-heading">Account</h2>
              <p>Your signed-in profile</p>
            </div>
          </div>
          <dl class="home-account">
            <div>
              <dt>Name</dt>
              <dd>{{ auth.user?.full_name || '—' }}</dd>
            </div>
            <div>
              <dt>Email</dt>
              <dd>{{ auth.user?.email || '—' }}</dd>
            </div>
          </dl>
        </section>
      </div>
    </div>
  </q-page>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import { http } from '@/api'
import AppPageHeader from '@/components/AppPageHeader.vue'
import AppStatusChip from '@/components/AppStatusChip.vue'
import { useAuthStore } from '@/module/auth'

const auth = useAuthStore()
const firstName = computed(() => auth.user?.full_name?.trim().split(/\s+/)[0] || 'there')
const health = ref(null)
const healthLoading = ref(true)

onMounted(async () => {
  try {
    const { data } = await http.get('/health', { skipAuth: true })
    health.value = data
  } catch {
    health.value = null
  } finally {
    healthLoading.value = false
  }
})
</script>

<style scoped lang="scss">
.home-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(300px, 1fr);
  align-items: start;
  gap: var(--app-space-lg);
}

.home-side {
  display: grid;
  gap: var(--app-space-lg);
}

.home-panel {
  min-width: 0;
  padding: var(--app-space-lg);
}

.home-panel__header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: var(--app-space-lg);
}

.home-panel__icon {
  display: grid;
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
  place-items: center;
  border-radius: var(--app-radius-md);
  background: var(--app-surface-muted);
  color: var(--app-primary);
}

.home-panel h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  line-height: 1.4;
}

.home-panel__header p {
  margin: 2px 0 0;
  color: var(--app-text-muted);
  font-size: 12px;
}

.home-access__group + .home-access__group {
  margin-top: var(--app-space-lg);
  padding-top: var(--app-space-lg);
  border-top: 1px solid var(--app-border);
}

.home-access__label {
  margin-bottom: var(--app-space-sm);
  color: var(--app-text-muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.home-access__items {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.home-access__items .q-chip {
  margin: 0;
}

.home-access__permission {
  color: var(--app-primary);
}

.home-access__empty {
  margin: 0;
  color: var(--app-text-muted);
  font-size: 13px;
}

.home-status__row,
.home-account > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--app-space-sm);
  padding: 11px 0;
  border-top: 1px solid var(--app-border);
}

.home-status__service {
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 13px;
  font-weight: 500;
}

.home-status__service .q-icon {
  color: var(--app-text-muted);
}

.home-account {
  margin: 0;
}

.home-account dt {
  color: var(--app-text-muted);
  font-size: 12px;
}

.home-account dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
  font-size: 13px;
  font-weight: 500;
  text-align: right;
}

@media (max-width: 1080px) {
  .home-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .home-side {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 700px) {
  .home-side {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
