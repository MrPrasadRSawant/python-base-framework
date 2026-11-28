<template>
  <q-page class="app-page app-page--dense exception-page">
    <AppPageHeader
      compact
      title="Exception Analysis"
      subtitle="Inspect recorded errors and their affected requests."
    >
      <template #actions>
        <q-btn-toggle
          v-model="severity"
          unelevated
          no-caps
          toggle-color="primary"
          :options="severityOptions"
          aria-label="Filter exception severity"
        />
      </template>
    </AppPageHeader>

    <AppTable
      compact
      tall
      :page-size="20"
      :resource="exceptionsApi"
      :columns="columns"
      :filters="filters"
      sort-by="occurred_on"
      search-placeholder="Search error, type, path, or code"
      empty-icon="check_circle"
      empty-title="No exceptions found"
      empty-message="Try a different search or severity."
      @row-click="openException"
    >
      <template #body-cell-status_code="props">
        <q-td :props="props"
          ><AppStatusChip
            :status="props.value >= 500 ? 'failed' : 'warning'"
            :label="String(props.value || '—')"
        /></q-td>
      </template>
      <template #body-cell-error_code="props">
        <q-td :props="props"
          ><code>{{ props.value || props.row.exception_type || 'Unhandled error' }}</code></q-td
        >
      </template>
      <template #body-cell-message="props">
        <q-td :props="props" class="exception-page__message">{{ props.value }}</q-td>
      </template>
      <template #body-cell-occurred_on="props">
        <q-td :props="props">{{ formatDate(props.value) }}</q-td>
      </template>
    </AppTable>

    <q-dialog v-model="detailOpen">
      <q-card class="exception-detail">
        <q-card-section class="row items-start">
          <div class="col">
            <div class="text-h6">Exception details</div>
            <div class="text-caption text-app-muted">
              {{ detail?.exception_type || detail?.error_code || 'Recorded error' }}
            </div>
          </div>
          <q-btn flat round dense icon="close" aria-label="Close" @click="detailOpen = false" />
        </q-card-section>
        <q-separator />
        <q-card-section v-if="detail" class="exception-detail__body">
          <div class="exception-detail__facts">
            <div>
              <small>Occurred</small><strong>{{ formatDate(detail.occurred_on) }}</strong>
            </div>
            <div>
              <small>HTTP status</small><strong>{{ detail.status_code || '—' }}</strong>
            </div>
            <div>
              <small>Method and route</small
              ><strong>{{ detail.method || '—' }} {{ detail.route || detail.path || '' }}</strong>
            </div>
            <div>
              <small>Error code</small><strong>{{ detail.error_code || '—' }}</strong>
            </div>
          </div>
          <q-banner rounded class="exception-detail__message q-mt-md">{{
            detail.message
          }}</q-banner>
          <div v-if="detail.request_id" class="row items-center q-gutter-sm q-mt-md">
            <span class="text-caption text-app-muted">Request {{ detail.request_id }}</span>
            <q-btn
              v-if="auth.can('request_logs:read')"
              flat
              dense
              no-caps
              color="primary"
              label="Open request lifecycle"
              @click="openRequest(detail.request_id)"
            />
          </div>
          <section v-if="detail.traceback" class="q-mt-lg">
            <h3 class="text-subtitle2">Redacted traceback</h3>
            <pre class="exception-detail__trace">{{ detail.traceback }}</pre>
          </section>
        </q-card-section>
        <q-inner-loading :showing="detailLoading"
          ><q-spinner-dots size="36px" color="primary"
        /></q-inner-loading>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppPageHeader from '@/components/AppPageHeader.vue'
import AppStatusChip from '@/components/AppStatusChip.vue'
import AppTable from '@/components/AppTable.vue'
import { useAuthStore } from '@/module/auth'

import { exceptionsApi, getException } from '../api.js'

const router = useRouter()
const auth = useAuthStore()
const severity = ref('all')
const severityOptions = [
  { label: 'All events', value: 'all' },
  { label: 'Server errors', value: 'server' },
  { label: 'Client errors', value: 'client' },
]
const filters = computed(() =>
  severity.value === 'server'
    ? [{ field: 'status_code', op: 'gte', value: 500 }]
    : severity.value === 'client'
      ? [
          { field: 'status_code', op: 'gte', value: 400 },
          { field: 'status_code', op: 'lt', value: 500 },
        ]
      : [],
)
const columns = [
  { name: 'occurred_on', label: 'Occurred', field: 'occurred_on', sortable: true, align: 'left' },
  { name: 'status_code', label: 'Status', field: 'status_code', sortable: true, align: 'left' },
  {
    name: 'error_code',
    label: 'Error code / type',
    field: 'error_code',
    sortable: true,
    align: 'left',
  },
  { name: 'route', label: 'Route', field: 'route', align: 'left' },
  { name: 'message', label: 'Message', field: 'message', align: 'left' },
]
const dateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'medium',
})
function formatDate(value) {
  return value ? dateFormatter.format(new Date(value)) : '—'
}

const detailOpen = ref(false)
const detailLoading = ref(false)
const detail = ref(null)
async function openException(row) {
  detailOpen.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await getException(row.id)
  } finally {
    detailLoading.value = false
  }
}
function openRequest(id) {
  detailOpen.value = false
  router.push({ name: 'request-lifecycle', query: { requestId: id } })
}
</script>

<style scoped lang="scss">
.exception-page__message {
  max-width: 360px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.exception-detail {
  width: min(760px, calc(100vw - 32px));
  max-height: calc(100vh - 32px);
  overflow: auto;
  border-radius: var(--app-radius-lg);
}
.exception-detail__body {
  padding: var(--app-space-lg);
}
.exception-detail__message {
  background: var(--app-surface-muted);
  color: var(--app-text);
}
.exception-detail__facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--app-space-md);
}
.exception-detail__facts div {
  display: grid;
  gap: 4px;
  min-width: 0;
}
.exception-detail__facts small {
  color: var(--app-text-muted);
}
.exception-detail__facts strong {
  overflow-wrap: anywhere;
  font-size: 13px;
}
.exception-detail__trace {
  max-height: 320px;
  overflow: auto;
  padding: var(--app-space-md);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  background: var(--app-surface-muted);
  font-size: 11px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
