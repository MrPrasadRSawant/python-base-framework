<template>
  <q-page class="app-page permission-page">
    <AppPageHeader
      title="Permission Management"
      subtitle="Review the permission catalog and control which capabilities each role grants."
    >
      <template #actions>
        <q-btn
          flat
          round
          dense
          icon="refresh"
          :loading="loading"
          aria-label="Reload permissions"
          @click="load"
        />
      </template>
    </AppPageHeader>

    <q-banner v-if="error" rounded class="bg-negative text-white q-mb-md">
      <template #avatar><q-icon name="error_outline" /></template>{{ error }}
      <template #action><q-btn flat no-caps color="white" label="Retry" @click="load" /></template>
    </q-banner>

    <div class="permission-page__layout">
      <aside class="app-card permission-page__roles">
        <div class="permission-page__roles-heading">
          <div>
            <h2>Roles</h2>
            <p>Select a role to review its access.</p>
          </div>
          <q-badge outline color="primary">{{ roles.length }}</q-badge>
        </div>
        <q-list separator>
          <q-item
            v-for="role in roles"
            :key="role.id"
            clickable
            :active="selectedRole?.id === role.id"
            active-class="permission-page__role-active"
            @click="selectRole(role)"
          >
            <q-item-section avatar
              ><q-icon :name="role.is_system ? 'shield' : 'admin_panel_settings'"
            /></q-item-section>
            <q-item-section>
              <q-item-label>{{ role.name }}</q-item-label>
              <q-item-label caption
                >{{ role.code }} ·
                {{ role.is_system ? 'System role' : 'Custom role' }}</q-item-label
              >
            </q-item-section>
          </q-item>
        </q-list>
        <q-inner-loading :showing="loading"
          ><q-spinner-dots size="32px" color="primary"
        /></q-inner-loading>
      </aside>

      <section class="app-card permission-page__catalog">
        <template v-if="selectedRole">
          <div class="permission-page__catalog-heading">
            <div class="row items-center q-gutter-sm">
              <div>
                <h2>{{ selectedRole.name }} access</h2>
                <p>{{ selectedRole.description || selectedRole.code }}</p>
              </div>
              <AppStatusChip
                :status="selectedRole.is_system ? 'system' : 'active'"
                :label="selectedRole.is_system ? 'System role' : 'Custom role'"
              />
            </div>
            <div class="row items-center q-gutter-sm">
              <q-input
                v-model="search"
                outlined
                dense
                clearable
                placeholder="Find a permission"
                aria-label="Find a permission"
              >
                <template #prepend><q-icon name="search" /></template>
              </q-input>
              <q-btn
                v-if="canManage"
                color="primary"
                unelevated
                no-caps
                icon="save"
                label="Save access"
                :disable="!hasChanges"
                :loading="saving"
                @click="save"
              />
            </div>
          </div>

          <q-banner v-if="!canManage" dense rounded class="permission-page__notice q-mt-md">
            You can review permission assignments. A role manager is required to make changes.
          </q-banner>
          <q-banner v-else dense rounded class="permission-page__notice q-mt-md">
            You can add or remove only permissions you already hold. The permission catalog is
            maintained with application releases.
          </q-banner>

          <div class="permission-page__summary">
            <span>{{ selectedPermissions.length }} assigned</span>
            <span>{{ editableCount }} can be changed by you</span>
          </div>

          <div v-if="visibleGroups.length" class="permission-page__groups">
            <section
              v-for="group in visibleGroups"
              :key="group.code"
              class="permission-page__group"
            >
              <header>
                <h3>{{ group.label }}</h3>
                <span>{{ group.assignedCount }}/{{ group.items.length }}</span>
              </header>
              <div
                v-for="permission in group.items"
                :key="permission.code"
                class="permission-page__item"
              >
                <q-checkbox
                  v-model="selectedPermissions"
                  :val="permission.code"
                  :disable="!editable || !grantableCodes.includes(permission.code)"
                  dense
                />
                <div class="col">
                  <code>{{ permission.code }}</code>
                  <p>{{ permission.description || 'No description provided.' }}</p>
                </div>
                <q-icon v-if="selectedRole.is_system" name="lock" color="grey-6" size="16px"
                  ><q-tooltip>System role permissions are read-only</q-tooltip></q-icon
                >
                <q-icon
                  v-else-if="
                    !grantableCodes.includes(permission.code) &&
                    !selectedPermissions.includes(permission.code)
                  "
                  name="lock"
                  color="grey-6"
                  size="16px"
                  ><q-tooltip
                    >You do not hold this permission, so it cannot be granted.</q-tooltip
                  ></q-icon
                >
              </div>
            </section>
          </div>
          <div v-else class="permission-page__empty">No permissions match this search.</div>
        </template>
        <AppEmptyState
          v-else
          icon="verified_user"
          title="Choose a role"
          message="Select a role to inspect its permissions."
        />
        <q-inner-loading :showing="roleLoading"
          ><q-spinner-dots size="32px" color="primary"
        /></q-inner-loading>
      </section>
    </div>
  </q-page>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import AppEmptyState from '@/components/AppEmptyState.vue'
import AppPageHeader from '@/components/AppPageHeader.vue'
import AppStatusChip from '@/components/AppStatusChip.vue'
import { useNotify } from '@/composables/useNotify'
import { useAuthStore } from '@/module/auth'
import { listPermissions, rolesApi } from '@/module/roles'
import { http } from '@/api'

const auth = useAuthStore()
const notify = useNotify()
const canManage = computed(() => auth.can('roles:manage'))
const grantableCodes = computed(() => [...auth.permissions])
const roles = ref([])
const catalog = ref([])
const selectedRole = ref(null)
const selectedPermissions = ref([])
const originalPermissions = ref([])
const search = ref('')
const loading = ref(false)
const roleLoading = ref(false)
const saving = ref(false)
const error = ref('')
const editable = computed(() => canManage.value && !selectedRole.value?.is_system)
const hasChanges = computed(
  () =>
    [...selectedPermissions.value].sort().join('|') !==
    [...originalPermissions.value].sort().join('|'),
)
const editableCount = computed(
  () => catalog.value.filter((item) => grantableCodes.value.includes(item.code)).length,
)
const visibleGroups = computed(() => {
  const query = search.value.trim().toLowerCase()
  const groups = new Map()
  for (const item of catalog.value) {
    if (query && !`${item.code} ${item.description || ''}`.toLowerCase().includes(query)) continue
    const [code] = item.code.split(':')
    if (!groups.has(code))
      groups.set(code, {
        code,
        label: code.replaceAll('_', ' ').replace(/\b\w/g, (char) => char.toUpperCase()),
        items: [],
      })
    groups.get(code).items.push(item)
  }
  return [...groups.values()].map((group) => ({
    ...group,
    assignedCount: group.items.filter((item) => selectedPermissions.value.includes(item.code))
      .length,
  }))
})

async function loadRoles() {
  const result = []
  let offset = 0
  let more = true
  while (more) {
    const { data } = await http.get('/roles', { params: { limit: 100, offset } })
    result.push(...data.records)
    more = data.metadata.has_more && data.records.length > 0
    offset = data.metadata.next_offset ?? offset + data.records.length
  }
  return result
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [roleRows, permissions] = await Promise.all([loadRoles(), listPermissions()])
    roles.value = roleRows
    catalog.value = permissions
    if (selectedRole.value)
      await selectRole(roleRows.find((role) => role.id === selectedRole.value.id) || roleRows[0])
    else if (roleRows.length) await selectRole(roleRows[0])
  } catch (err) {
    error.value = err.message || 'Unable to load roles and permissions.'
  } finally {
    loading.value = false
  }
}

async function selectRole(role) {
  if (!role) {
    selectedRole.value = null
    return
  }
  roleLoading.value = true
  error.value = ''
  try {
    const detail = await rolesApi.get(role.id)
    selectedRole.value = detail
    selectedPermissions.value = [...detail.permissions]
    originalPermissions.value = [...detail.permissions]
  } catch (err) {
    error.value = err.message || 'Unable to load this role.'
  } finally {
    roleLoading.value = false
  }
}

async function save() {
  if (!selectedRole.value || !editable.value || !hasChanges.value) return
  saving.value = true
  error.value = ''
  try {
    selectedRole.value = await rolesApi.setPermissions(
      selectedRole.value.id,
      selectedPermissions.value,
    )
    selectedPermissions.value = [...selectedRole.value.permissions]
    originalPermissions.value = [...selectedRole.value.permissions]
    const index = roles.value.findIndex((role) => role.id === selectedRole.value.id)
    if (index >= 0)
      roles.value[index] = { ...roles.value[index], permissions: selectedRole.value.permissions }
    notify.success('Role permissions updated')
  } catch (err) {
    error.value = err.message || 'Unable to save role permissions.'
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped lang="scss">
.permission-page__layout {
  display: grid;
  grid-template-columns: minmax(230px, 0.65fr) minmax(0, 1.7fr);
  align-items: start;
  gap: var(--app-space-md);
}
.permission-page__roles,
.permission-page__catalog {
  position: relative;
  min-height: 250px;
  overflow: hidden;
}
.permission-page__roles-heading,
.permission-page__catalog-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--app-space-md);
  padding: var(--app-space-lg);
}
.permission-page__roles-heading {
  border-bottom: 1px solid var(--app-border);
}
.permission-page__roles-heading h2,
.permission-page__catalog-heading h2 {
  margin: 0;
  font-size: 15px;
}
.permission-page__roles-heading p,
.permission-page__catalog-heading p {
  margin: 5px 0 0;
  color: var(--app-text-muted);
  font-size: 12px;
}
.permission-page__role-active {
  background: var(--app-surface-muted);
  color: var(--app-primary);
}
.permission-page__notice {
  background: var(--app-surface-muted);
  color: var(--app-text);
}
.permission-page__catalog-heading {
  flex-wrap: wrap;
  border-bottom: 1px solid var(--app-border);
}
.permission-page__summary {
  display: flex;
  justify-content: space-between;
  padding: var(--app-space-md) var(--app-space-lg) 0;
  color: var(--app-text-muted);
  font-size: 12px;
}
.permission-page__groups {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: start;
  gap: var(--app-space-md);
  padding: var(--app-space-md) var(--app-space-lg) var(--app-space-lg);
}
.permission-page__group {
  overflow: hidden;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
}
.permission-page__group header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--app-space-sm) var(--app-space-md);
  background: var(--app-surface-muted);
}
.permission-page__group header h3 {
  margin: 0;
  font-size: 13px;
  font-weight: 650;
}
.permission-page__group header span {
  color: var(--app-text-muted);
  font-size: 11px;
}
.permission-page__item {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  padding: var(--app-space-sm) var(--app-space-md);
}
.permission-page__item + .permission-page__item {
  border-top: 1px solid var(--app-border);
}
.permission-page__item code {
  font-size: 12px;
}
.permission-page__item p {
  margin: 3px 0 0;
  color: var(--app-text-muted);
  font-size: 11px;
}
.permission-page__empty {
  padding: var(--app-space-xl);
  text-align: center;
  color: var(--app-text-muted);
}
@media (max-width: 900px) {
  .permission-page__layout {
    grid-template-columns: 1fr;
  }
  .permission-page__roles :deep(.q-list) {
    display: flex;
    overflow-x: auto;
  }
  .permission-page__roles :deep(.q-item) {
    min-width: 200px;
  }
}
@media (max-width: 650px) {
  .permission-page__groups {
    grid-template-columns: 1fr;
    padding-right: var(--app-space-md);
    padding-left: var(--app-space-md);
  }
  .permission-page__catalog-heading {
    align-items: flex-start;
    flex-direction: column;
  }
  .permission-page__catalog-heading > .row:last-child {
    width: 100%;
  }
  .permission-page__catalog-heading .q-input {
    flex: 1;
  }
}
</style>
