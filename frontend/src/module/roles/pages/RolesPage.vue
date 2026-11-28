<template>
  <q-page class="app-page roles-page">
    <AppPageHeader title="Role Management" subtitle="Organize access with roles and permissions.">
      <template #actions>
        <q-btn
          v-if="canManage"
          color="primary"
          unelevated
          no-caps
          icon="add"
          label="Create role"
          @click="openRoleForm()"
        />
      </template>
    </AppPageHeader>

    <AppTable
      ref="table"
      :resource="rolesApi"
      :columns="columns"
      :filters="filters"
      sort-by="created_on"
      search-placeholder="Quick search by code, name, or description"
      empty-icon="admin_panel_settings"
      empty-title="No roles found"
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
      <template #body-cell-name="props">
        <q-td :props="props"
          ><span class="text-weight-medium">{{ props.row.name }}</span></q-td
        >
      </template>
      <template #body-cell-code="props">
        <q-td :props="props"
          ><code class="roles-page__code">{{ props.row.code }}</code></q-td
        >
      </template>
      <template #body-cell-description="props">
        <q-td :props="props" class="roles-page__description">
          <span :title="props.row.description || ''">{{ props.row.description || '—' }}</span>
        </q-td>
      </template>
      <template #body-cell-is_system="props">
        <q-td :props="props">
          <AppStatusChip
            :status="props.row.is_system ? 'system' : 'custom'"
            :label="props.row.is_system ? 'System' : 'Custom'"
          />
        </q-td>
      </template>
      <template #body-cell-created_on="props">
        <q-td :props="props">{{ formatDate(props.row.created_on) }}</q-td>
      </template>
      <template #body-cell-actions="props">
        <q-td :props="props">
          <q-btn
            flat
            round
            dense
            icon="more_vert"
            :aria-label="`Actions for ${props.row.name}`"
            :loading="openingPermissionsId === props.row.id"
            @click.stop
          >
            <q-menu auto-close>
              <q-list dense class="roles-page__action-menu">
                <q-item clickable @click="openPermissions(props.row)">
                  <q-item-section avatar><q-icon name="verified_user" /></q-item-section>
                  <q-item-section>{{
                    canManage && !props.row.is_system ? 'Manage permissions' : 'View permissions'
                  }}</q-item-section>
                </q-item>
                <q-item v-if="canAudit" clickable @click="openHistory(props.row)">
                  <q-item-section avatar><q-icon name="manage_history" /></q-item-section>
                  <q-item-section>Activity history</q-item-section>
                </q-item>
                <q-item v-if="canManage" clickable @click="openRoleForm(props.row)">
                  <q-item-section avatar><q-icon name="edit" /></q-item-section>
                  <q-item-section>Edit details</q-item-section>
                </q-item>
                <q-separator v-if="canManage && !props.row.is_system" />
                <q-item
                  v-if="canManage && !props.row.is_system"
                  clickable
                  class="text-negative"
                  @click="requestDelete(props.row)"
                >
                  <q-item-section avatar><q-icon name="delete_outline" /></q-item-section>
                  <q-item-section>Delete role</q-item-section>
                </q-item>
              </q-list>
            </q-menu>
          </q-btn>
        </q-td>
      </template>
    </AppTable>

    <AppAdvancedFiltersDialog
      v-model="advancedOpen"
      description="Show roles that match every condition below."
      :fields="ROLE_FILTER_FIELDS"
      :build-filters="buildRoleFilters"
      :conditions="appliedConditions"
      :applied-count="appliedConditions.length"
      @apply="applyFilters"
    />

    <RoleFormDialog
      v-model="roleFormOpen"
      :role="editingRole"
      :loading="savingRole"
      :error="roleFormError"
      @submit="saveRole"
    />

    <RolePermissionsDialog
      v-model="permissionsOpen"
      :role="roleDetail"
      :catalog="permissionCatalog"
      :can-manage="canManage"
      :grantable-codes="grantableCodes"
      :saving="savingPermissions"
      @save="savePermissions"
    />

    <AppConfirmDialog
      v-model="confirmOpen"
      title="Delete role?"
      :message="deleteMessage"
      confirm-label="Delete role"
      danger
      :loading="deletingRole"
      @confirm="confirmDelete"
    />
  </q-page>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppAdvancedFiltersDialog from '@/components/AppAdvancedFiltersDialog.vue'
import AppConfirmDialog from '@/components/AppConfirmDialog.vue'
import AppPageHeader from '@/components/AppPageHeader.vue'
import AppStatusChip from '@/components/AppStatusChip.vue'
import AppTable from '@/components/AppTable.vue'
import { useNotify } from '@/composables/useNotify'
import { ACTIVITY_PERMISSION } from '@/module/audit'
import { useAuthStore } from '@/module/auth'

import { listPermissions, rolesApi } from '../api.js'
import RoleFormDialog from '../components/RoleFormDialog.vue'
import RolePermissionsDialog from '../components/RolePermissionsDialog.vue'
import { buildRoleFilters, ROLE_FILTER_FIELDS } from '../filters.js'

const auth = useAuthStore()
const router = useRouter()
const notify = useNotify()
const table = ref(null)
const canManage = computed(() => auth.can('roles:manage'))
const canAudit = computed(() => auth.can(ACTIVITY_PERMISSION))

function openHistory(role) {
  router.push({ name: 'user-activity', query: { entityType: 'roles', entityId: role.id } })
}
const grantableCodes = computed(() => [...auth.permissions])

const advancedOpen = ref(false)
const appliedConditions = ref([])
const filters = computed(() => buildRoleFilters(appliedConditions.value))

const columns = [
  { name: 'name', label: 'Role', field: 'name', align: 'left', sortable: true },
  { name: 'code', label: 'Code', field: 'code', align: 'left', sortable: true },
  { name: 'description', label: 'Description', field: 'description', align: 'left' },
  { name: 'is_system', label: 'Type', field: 'is_system', align: 'left' },
  { name: 'created_on', label: 'Created', field: 'created_on', align: 'left', sortable: true },
  { name: 'actions', label: '', field: 'id', align: 'right' },
]

const dateFormatter = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' })
function formatDate(value) {
  return value ? dateFormatter.format(new Date(value)) : '—'
}

function applyFilters(conditions) {
  appliedConditions.value = conditions
  advancedOpen.value = false
}

const roleFormOpen = ref(false)
const editingRole = ref(null)
const savingRole = ref(false)
const roleFormError = ref('')

function openRoleForm(role = null) {
  editingRole.value = role
  roleFormError.value = ''
  roleFormOpen.value = true
}

async function saveRole(payload) {
  savingRole.value = true
  roleFormError.value = ''
  try {
    const role = editingRole.value
      ? await rolesApi.update(editingRole.value.id, payload)
      : await rolesApi.create(payload)
    roleFormOpen.value = false
    notify.success(editingRole.value ? 'Role updated' : 'Role created')
    await table.value?.reload({ resetPage: true })
    if (!editingRole.value) await openPermissions(role)
  } catch (error) {
    roleFormError.value = error.message
  } finally {
    savingRole.value = false
  }
}

const permissionsOpen = ref(false)
const roleDetail = ref(null)
const permissionCatalog = ref([])
const openingPermissionsId = ref(null)
const savingPermissions = ref(false)

async function openPermissions(role) {
  openingPermissionsId.value = role.id
  try {
    const [detail, catalog] = await Promise.all([
      rolesApi.get(role.id),
      permissionCatalog.value.length ? Promise.resolve(permissionCatalog.value) : listPermissions(),
    ])
    roleDetail.value = detail
    permissionCatalog.value = catalog
    permissionsOpen.value = true
  } catch (error) {
    notify.error(error)
  } finally {
    openingPermissionsId.value = null
  }
}

async function savePermissions(codes) {
  if (!roleDetail.value) return
  savingPermissions.value = true
  try {
    roleDetail.value = await rolesApi.setPermissions(roleDetail.value.id, codes)
    permissionsOpen.value = false
    notify.success('Role permissions updated')
  } catch (error) {
    notify.error(error)
  } finally {
    savingPermissions.value = false
  }
}

const confirmOpen = ref(false)
const deletingRole = ref(false)
const pendingDelete = ref(null)
const deleteMessage = computed(() =>
  pendingDelete.value
    ? `Deleting ${pendingDelete.value.name} removes this role from every assigned user. They will lose its access when their token refreshes.`
    : '',
)

function requestDelete(role) {
  pendingDelete.value = role
  confirmOpen.value = true
}

async function confirmDelete() {
  if (!pendingDelete.value) return
  deletingRole.value = true
  try {
    await rolesApi.remove(pendingDelete.value.id)
    confirmOpen.value = false
    notify.success('Role deleted')
    await table.value?.reload({ resetPage: true })
  } catch (error) {
    notify.error(error)
  } finally {
    deletingRole.value = false
  }
}
</script>

<style scoped lang="scss">
.roles-page__code {
  color: var(--app-text-muted);
  font-size: 12px;
}

.roles-page__description {
  max-width: 320px;
}

.roles-page__description span {
  display: block;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.roles-page__action-menu {
  min-width: 210px;
}

.roles-page__action-menu :deep(.q-item__section--avatar) {
  min-width: 32px;
}
</style>
