<template>
  <q-page class="app-page app-page--dense activity-page">
    <AppPageHeader
      compact
      title="User Activity"
      subtitle="Audit trail of record changes, sign-ins, and refused attempts."
    >
      <template #actions>
        <div v-if="!disabled" class="activity-page__quick" aria-label="Filter activity type">
          <q-btn-toggle
            v-model="quick"
            unelevated
            no-caps
            toggle-color="primary"
            :options="QUICK_FILTERS.slice(0, 3)"
          />
          <q-btn
            flat
            round
            dense
            size="sm"
            icon="more_horiz"
            :class="{ 'activity-page__more--active': quick === 'refused' }"
            :aria-label="
              quick === 'refused' ? 'More filters: Refused selected' : 'More activity filters'
            "
          >
            <q-tooltip>More activity filters</q-tooltip>
            <q-menu auto-close>
              <q-list dense>
                <q-item
                  v-for="option in QUICK_FILTERS.slice(3)"
                  :key="option.value"
                  clickable
                  :active="quick === option.value"
                  active-class="text-primary"
                  @click="quick = option.value"
                >
                  <q-item-section>{{ option.label }}</q-item-section>
                </q-item>
              </q-list>
            </q-menu>
          </q-btn>
        </div>
      </template>
    </AppPageHeader>

    <section v-if="disabled" class="app-card">
      <AppEmptyState
        icon="toggle_off"
        title="Activity logging is turned off"
        message="Set ENABLE_USER_ACTIVITY_LOG=true on the server to record and view user activity."
      />
    </section>

    <template v-else>
      <q-banner v-if="contextLabel" rounded class="activity-page__context q-mb-md">
        <template #avatar><q-icon name="filter_alt" color="primary" /></template>
        {{ contextLabel }}
        <template #action>
          <q-btn flat no-caps color="primary" label="Show all activity" @click="clearContext" />
        </template>
      </q-banner>

      <AppTable
        ref="table"
        compact
        tall
        :page-size="20"
        :resource="activityApi"
        :columns="columns"
        :filters="filters"
        sort-by="occurred_on"
        search-placeholder="Search actor, action, record, route, or IP"
        empty-icon="manage_history"
        empty-title="No activity found"
        empty-message="Try another search, filter, or activity type."
        @loaded="onLoaded"
        @error="onTableError"
        @row-click="openDetail"
      >
        <template #toolbar>
          <q-btn
            outline
            no-caps
            dense
            size="sm"
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
        <template #body-cell-occurred_on="props">
          <q-td :props="props" class="activity-page__when">{{ formatDateTime(props.value) }}</q-td>
        </template>
        <template #body-cell-actor="props">
          <q-td :props="props">
            <span class="text-weight-medium">{{ actorLabel(props.row, names) }}</span>
          </q-td>
        </template>
        <template #body-cell-action="props">
          <q-td :props="props">
            <span class="activity-page__action">
              <q-icon :name="actionLook(props.value).icon" size="17px" />
              {{ actionLook(props.value).label }}
            </span>
          </q-td>
        </template>
        <template #body-cell-entity_type="props">
          <q-td :props="props">
            <template v-if="props.value">
              {{ entityLabel(props.value) }}
              <code v-if="props.row.entity_id" class="activity-page__id">{{
                shortId(props.row.entity_id)
              }}</code>
            </template>
            <span v-else class="text-app-muted">—</span>
          </q-td>
        </template>
        <template #body-cell-ip_address="props">
          <q-td :props="props"
            ><code>{{ props.value || '—' }}</code></q-td
          >
        </template>
        <template #body-cell-status="props">
          <q-td :props="props"
            ><AppStatusChip :status="props.value === 'failed' ? 'failed' : 'success'"
          /></q-td>
        </template>
      </AppTable>
      <p class="activity-page__hint">Select an activity row to view its full details.</p>
    </template>

    <AppAdvancedFiltersDialog
      v-model="advancedOpen"
      description="Show activity that matches every condition below."
      :fields="ACTIVITY_FILTER_FIELDS"
      :build-filters="buildActivityFilters"
      :conditions="appliedConditions"
      :applied-count="appliedConditions.length"
      @apply="applyFilters"
    />

    <ActivityDetailDialog
      v-model="detailOpen"
      :row="detail"
      :names="names"
      :can-open-request="auth.can('request_logs:read')"
      @record-history="showRecordHistory"
      @actor-activity="showActorActivity"
      @open-request="openRequest"
    />
  </q-page>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppAdvancedFiltersDialog from '@/components/AppAdvancedFiltersDialog.vue'
import AppEmptyState from '@/components/AppEmptyState.vue'
import AppPageHeader from '@/components/AppPageHeader.vue'
import AppStatusChip from '@/components/AppStatusChip.vue'
import AppTable from '@/components/AppTable.vue'
import { useNotify } from '@/composables/useNotify'
import { useAuthStore } from '@/module/auth'

import {
  actionLook,
  actorLabel,
  contextFilters,
  entityLabel,
  formatDateTime,
  QUICK_FILTERS,
  quickFilter,
  shortId,
} from '../activity.js'
import { activityApi, usernamesFor } from '../api.js'
import ActivityDetailDialog from '../components/ActivityDetailDialog.vue'
import { ACTIVITY_FILTER_FIELDS, buildActivityFilters } from '../filters.js'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const notify = useNotify()
const table = ref(null)

const quick = ref('all')
const advancedOpen = ref(false)
const appliedConditions = ref([])
const context = computed(() => ({
  entityType: route.query.entityType,
  entityId: route.query.entityId,
  actorId: route.query.actorId,
}))
const filters = computed(() => [
  ...quickFilter(quick.value),
  ...contextFilters(context.value),
  ...buildActivityFilters(appliedConditions.value),
])

const contextLabel = computed(() => {
  const { entityType, entityId, actorId } = context.value
  if (entityType && entityId) {
    return `History of ${entityLabel(entityType)} ${entityId}`
  }
  if (actorId) {
    return `Activity by ${names.value[actorId] || actorId}`
  }
  return ''
})

const columns = [
  { name: 'occurred_on', label: 'When', field: 'occurred_on', sortable: true, align: 'left' },
  { name: 'actor', label: 'Who', field: 'actor', sortable: true, align: 'left' },
  { name: 'action', label: 'Action', field: 'action', sortable: true, align: 'left' },
  { name: 'entity_type', label: 'Record', field: 'entity_type', sortable: true, align: 'left' },
  { name: 'ip_address', label: 'IP address', field: 'ip_address', align: 'left' },
  { name: 'status', label: 'Status', field: 'status', sortable: true, align: 'left' },
]

// ---- usernames for user ids (needs users:read; otherwise ids are shown)
const names = ref({})
async function resolveNames(ids) {
  const missing = [...new Set(ids)].filter((id) => id && !(id in names.value))
  if (!missing.length || !auth.can('users:read')) return
  try {
    names.value = { ...names.value, ...(await usernamesFor(missing)) }
  } catch {
    // Names are a convenience: the ids stay visible.
  }
}

function onLoaded(data) {
  resolveNames(data.records.filter((r) => r.actor_type === 'user').map((r) => r.actor_id))
}

function onTableError(error) {
  if (error?.status === 404) {
    disabled.value = true
    return
  }
  notify.error(error)
}

const disabled = ref(false)

function applyFilters(conditions) {
  appliedConditions.value = conditions
  advancedOpen.value = false
}

// ---- detail + navigation
const detailOpen = ref(false)
const detail = ref(null)
function openDetail(row) {
  detail.value = row
  detailOpen.value = true
}
function showRecordHistory(row) {
  detailOpen.value = false
  router.push({ query: { entityType: row.entity_type, entityId: row.entity_id } })
}
function showActorActivity(row) {
  detailOpen.value = false
  router.push({ query: { actorId: row.actor_id } })
}
function clearContext() {
  router.push({ query: {} })
}
function openRequest(row) {
  detailOpen.value = false
  router.push({ name: 'request-lifecycle', query: { requestId: row.request_id } })
}

onMounted(() => {
  if (context.value.actorId) resolveNames([context.value.actorId])
})
</script>

<style scoped lang="scss">
.activity-page__quick {
  display: flex;
  align-items: center;
  gap: var(--app-space-xs);
  max-width: 100%;
}
.activity-page__quick :deep(.q-btn-group) {
  white-space: nowrap;
}
.activity-page__more--active {
  background: color-mix(in srgb, var(--app-primary) 12%, transparent);
  color: var(--app-primary);
}
.activity-page__context {
  border: 1px solid var(--app-border);
  background: var(--app-surface);
  color: var(--app-text);
  overflow-wrap: anywhere;
}
.activity-page__when {
  white-space: nowrap;
}
.activity-page__action {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}
.activity-page__id {
  margin-left: 4px;
  color: var(--app-text-muted);
  font-size: 11px;
}
.activity-page__hint {
  margin: var(--app-space-sm) 0 0;
  color: var(--app-text-muted);
  font-size: 12px;
}
.activity-page :deep(.app-table__toolbar) {
  flex-wrap: wrap;
}
.activity-page :deep(.app-table__search) {
  flex: 0 1 240px;
}
.activity-page :deep(.q-table tbody tr) {
  cursor: pointer;
}
.activity-page :deep(.q-table tbody tr:hover) {
  background: var(--app-surface-muted);
}
@media (max-width: 480px) {
  .activity-page__quick :deep(.q-btn-group .q-btn) {
    padding: 0 7px;
    font-size: 11px;
  }
  .activity-page :deep(.app-table__search) {
    flex: 1 1 100%;
  }
}
</style>
