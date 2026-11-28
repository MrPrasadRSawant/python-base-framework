<template>
  <q-page class="app-page users-page">
    <AppPageHeader
      title="User Management"
      subtitle="Manage accounts and sign-in access for your team."
    >
      <template #actions>
        <q-btn
          v-if="canManage"
          color="primary"
          unelevated
          no-caps
          icon="person_add"
          label="Create user"
          @click="openCreate"
        />
      </template>
    </AppPageHeader>

    <AppTable
      ref="table"
      :resource="usersApi"
      :columns="columns"
      :filters="filters"
      sort-by="created_on"
      search-placeholder="Search username, name, or email"
      empty-icon="group_off"
      empty-title="No users found"
      empty-message="Try another search or filter."
    >
      <template #toolbar>
        <q-btn
          outline
          no-caps
          color="primary"
          icon="tune"
          label="Advanced filters"
          @click="advancedOpen = true"
        >
          <q-badge v-if="appliedConditions.length" color="primary" floating>{{
            appliedConditions.length
          }}</q-badge>
        </q-btn>
      </template>
      <template #body-cell-full_name="props">
        <q-td :props="props">
          <span class="text-weight-medium">{{ props.row.full_name }}</span>
          <span v-if="isSelf(props.row)" class="users-page__self">You</span>
        </q-td>
      </template>
      <template #body-cell-username="props">
        <q-td :props="props"
          ><span class="users-page__username">{{ props.row.username }}</span></q-td
        >
      </template>
      <template #body-cell-is_active="props">
        <q-td :props="props" class="users-page__status">
          <AppStatusChip :status="props.row.is_active ? 'active' : 'disabled'" />
          <AppStatusChip v-if="isLocked(props.row)" status="warning" label="Locked" />
        </q-td>
      </template>
      <template #body-cell-last_login_on="props">
        <q-td :props="props">{{ formatDate(props.row.last_login_on) }}</q-td>
      </template>
      <template #body-cell-created_on="props">
        <q-td :props="props">{{ formatDate(props.row.created_on) }}</q-td>
      </template>
      <template #body-cell-actions="props">
        <q-td :props="props" class="users-page__actions">
          <q-btn
            v-if="canAudit"
            flat
            round
            dense
            color="primary"
            icon="manage_history"
            :aria-label="`Activity history for ${props.row.full_name}`"
            @click.stop="openHistory(props.row)"
          >
            <q-tooltip>Activity history</q-tooltip>
          </q-btn>
          <q-btn
            v-if="canManage"
            flat
            dense
            no-caps
            color="primary"
            icon="admin_panel_settings"
            label="Roles"
            :aria-label="`Manage roles for ${props.row.full_name}`"
            :disable="isSelf(props.row)"
            @click.stop="openManageRoles(props.row)"
          />
          <q-btn
            v-if="canManage"
            flat
            round
            dense
            icon="more_vert"
            :aria-label="`Actions for ${props.row.full_name}`"
            :disable="isSelf(props.row)"
            @click.stop
          >
            <q-menu auto-close>
              <q-list dense class="users-page__action-menu">
                <q-item clickable @click="requestAction('active', props.row)">
                  <q-item-section avatar>
                    <q-icon :name="props.row.is_active ? 'person_off' : 'person'" />
                  </q-item-section>
                  <q-item-section>{{ props.row.is_active ? 'Disable' : 'Enable' }}</q-item-section>
                </q-item>
                <q-item clickable @click="requestAction('lock', props.row)">
                  <q-item-section avatar>
                    <q-icon :name="isLocked(props.row) ? 'lock_open' : 'lock'" />
                  </q-item-section>
                  <q-item-section>{{ isLocked(props.row) ? 'Unlock' : 'Lock' }}</q-item-section>
                </q-item>
              </q-list>
            </q-menu>
          </q-btn>
        </q-td>
      </template>
    </AppTable>

    <AppAdvancedFiltersDialog
      v-model="advancedOpen"
      description="Show users who match every condition below."
      :fields="USER_FILTER_FIELDS"
      :build-filters="buildUserFilters"
      :conditions="appliedConditions"
      :applied-count="appliedConditions.length"
      @apply="applyFilters"
    />

    <CreateUserDialog
      v-model="createOpen"
      :loading="creating"
      :error="createError"
      :roles="roles"
      :roles-loading="rolesLoading"
      :roles-error="rolesError"
      @submit="createUser"
    />
    <ManageUserRolesDialog
      v-model="rolesDialogOpen"
      :user="roleTarget"
      :user-detail="roleTargetDetail"
      :roles="roles"
      :loading="rolesDialogLoading"
      :saving="savingRoles"
      :error="rolesDialogError"
      @retry="loadManageRoles"
      @save="saveUserRoles"
    />
    <AppConfirmDialog
      v-model="confirmOpen"
      :title="actionCopy.title"
      :message="actionCopy.message"
      :confirm-label="actionCopy.label"
      :danger="actionCopy.danger"
      :loading="changingStatus"
      @confirm="confirmAction"
    />
  </q-page>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppConfirmDialog from '@/components/AppConfirmDialog.vue'
import AppAdvancedFiltersDialog from '@/components/AppAdvancedFiltersDialog.vue'
import AppPageHeader from '@/components/AppPageHeader.vue'
import AppStatusChip from '@/components/AppStatusChip.vue'
import AppTable from '@/components/AppTable.vue'
import { useNotify } from '@/composables/useNotify'
import { ACTIVITY_PERMISSION } from '@/module/audit'
import { useAuthStore } from '@/module/auth'

import { listRoles, usersApi } from '../api.js'
import CreateUserDialog from '../components/CreateUserDialog.vue'
import ManageUserRolesDialog from '../components/ManageUserRolesDialog.vue'
import { buildUserFilters, USER_FILTER_FIELDS } from '../filters.js'

const auth = useAuthStore()
const router = useRouter()
const notify = useNotify()
const table = ref(null)
const advancedOpen = ref(false)
const appliedConditions = ref([])
const filters = computed(() => buildUserFilters(appliedConditions.value))
const canManage = computed(() => auth.can('users:manage'))
const canAudit = computed(() => auth.can(ACTIVITY_PERMISSION))
const columns = computed(() => [
  { name: 'full_name', label: 'Name', field: 'full_name', align: 'left', sortable: true },
  { name: 'username', label: 'Username', field: 'username', align: 'left', sortable: true },
  { name: 'email', label: 'Email', field: 'email', align: 'left', sortable: true },
  { name: 'is_active', label: 'Status', field: 'is_active', align: 'left' },
  {
    name: 'last_login_on',
    label: 'Last sign-in',
    field: 'last_login_on',
    align: 'left',
    sortable: true,
  },
  { name: 'created_on', label: 'Created', field: 'created_on', align: 'left', sortable: true },
  ...(canManage.value || canAudit.value
    ? [{ name: 'actions', label: '', field: 'id', align: 'right' }]
    : []),
])

const createOpen = ref(false)
const creating = ref(false)
const createError = ref('')
const roles = ref([])
const rolesLoading = ref(false)
const rolesLoaded = ref(false)
const rolesError = ref('')

const rolesDialogOpen = ref(false)
const rolesDialogLoading = ref(false)
const rolesDialogError = ref('')
const roleTarget = ref(null)
const roleTargetDetail = ref(null)
const savingRoles = ref(false)
let rolesRequestSeq = 0

const confirmOpen = ref(false)
const changingStatus = ref(false)
const pendingAction = ref(null)
const actionCopy = computed(() => {
  const action = pendingAction.value
  if (!action) return { title: '', message: '', label: 'Confirm', danger: false }
  const name = action.user.full_name
  if (action.type === 'active' && action.user.is_active) {
    return {
      title: 'Disable user?',
      message: `${name} will no longer be able to sign in. Existing access expires shortly.`,
      label: 'Disable',
      danger: true,
    }
  }
  if (action.type === 'active') {
    return {
      title: 'Enable user?',
      message: `${name} can sign in again unless the account is also locked.`,
      label: 'Enable',
      danger: false,
    }
  }
  if (!isLocked(action.user)) {
    return {
      title: 'Lock user?',
      message: `${name} will be blocked from signing in until an administrator unlocks the account.`,
      label: 'Lock',
      danger: true,
    }
  }
  return {
    title: 'Unlock user?',
    message: `Clear ${name}'s lockout. A disabled account remains disabled.`,
    label: 'Unlock',
    danger: false,
  }
})

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
})

function formatDate(value) {
  return value ? dateFormatter.format(new Date(value)) : 'Never'
}

function isSelf(user) {
  return user.id === auth.user?.id
}

function isLocked(user) {
  return Boolean(user.is_locked || (user.locked_until && new Date(user.locked_until) > new Date()))
}

function openHistory(user) {
  router.push({ name: 'user-activity', query: { entityType: 'users', entityId: user.id } })
}

function applyFilters(conditions) {
  appliedConditions.value = conditions
  advancedOpen.value = false
}

async function openCreate() {
  createError.value = ''
  createOpen.value = true
  if (rolesLoaded.value || rolesLoading.value) return
  if (!auth.can('roles:read')) {
    rolesError.value = 'You cannot view roles. The user will be created without roles.'
    return
  }
  rolesLoading.value = true
  rolesError.value = ''
  try {
    roles.value = await listRoles()
    rolesLoaded.value = true
  } catch (error) {
    rolesError.value = `Roles could not be loaded: ${error.message}`
  } finally {
    rolesLoading.value = false
  }
}

async function createUser(payload) {
  creating.value = true
  createError.value = ''
  try {
    await usersApi.create(payload)
    createOpen.value = false
    notify.success('User created')
    await table.value?.reload({ resetPage: true })
  } catch (error) {
    createError.value = error.message
  } finally {
    creating.value = false
  }
}

async function openManageRoles(user) {
  if (isSelf(user)) return
  roleTarget.value = user
  roleTargetDetail.value = null
  rolesDialogError.value = ''
  rolesDialogOpen.value = true
  await loadManageRoles()
}

async function loadManageRoles() {
  if (!roleTarget.value) return
  const seq = ++rolesRequestSeq
  rolesDialogLoading.value = true
  rolesDialogError.value = ''
  try {
    const [detail, availableRoles] = await Promise.all([
      usersApi.get(roleTarget.value.id),
      listRoles(),
    ])
    if (seq !== rolesRequestSeq) return
    roleTargetDetail.value = detail
    roles.value = availableRoles
    rolesLoaded.value = true
    rolesError.value = ''
  } catch (error) {
    if (seq === rolesRequestSeq) rolesDialogError.value = error.message
  } finally {
    if (seq === rolesRequestSeq) rolesDialogLoading.value = false
  }
}

async function saveUserRoles(codes) {
  if (!roleTargetDetail.value) return
  savingRoles.value = true
  rolesDialogError.value = ''
  try {
    roleTargetDetail.value = await usersApi.setRoles(roleTargetDetail.value.id, codes)
    rolesDialogOpen.value = false
    notify.success('User roles updated')
    await table.value?.reload()
  } catch (error) {
    rolesDialogError.value = error.message
  } finally {
    savingRoles.value = false
  }
}

function requestAction(type, user) {
  if (isSelf(user)) return
  pendingAction.value = { type, user }
  confirmOpen.value = true
}

async function confirmAction() {
  const action = pendingAction.value
  if (!action) return
  changingStatus.value = true
  try {
    if (action.type === 'active') {
      await usersApi.update(action.user.id, { is_active: !action.user.is_active })
    } else {
      await usersApi.setLocked(action.user.id, !isLocked(action.user))
    }
    confirmOpen.value = false
    const pastTense = { Disable: 'disabled', Enable: 'enabled', Lock: 'locked', Unlock: 'unlocked' }
    notify.success(`User ${pastTense[actionCopy.value.label]}`)
    await table.value?.reload()
  } catch (error) {
    notify.error(error)
  } finally {
    changingStatus.value = false
  }
}
</script>

<style scoped lang="scss">
.users-page__self {
  margin-left: var(--app-space-sm);
  color: var(--app-text-muted);
  font-size: 11px;
}

.users-page__username {
  color: var(--app-text-muted);
  font-size: 13px;
}

.users-page__status :deep(.q-chip) {
  margin: 0 var(--app-space-xs) 0 0;
}

.users-page__actions {
  white-space: nowrap;
}

.users-page__action-menu {
  min-width: 160px;
}

.users-page__action-menu :deep(.q-item__section--avatar) {
  min-width: 32px;
}
</style>
