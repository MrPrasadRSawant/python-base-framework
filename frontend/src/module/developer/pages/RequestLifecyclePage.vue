<template>
  <q-page class="app-page request-page">
    <AppPageHeader
      title="Request Lifecycle"
      subtitle="Trace incoming requests, response time, and the services that ran."
    >
      <template #actions>
        <q-btn-toggle
          v-model="view"
          unelevated
          no-caps
          toggle-color="primary"
          :options="viewOptions"
          aria-label="Filter request outcomes"
        />
      </template>
    </AppPageHeader>

    <div class="request-page__metrics">
      <article class="app-card request-metric">
        <span>Total requests</span><strong>{{ totalCount.toLocaleString() }}</strong
        ><small>Across all pages</small>
      </article>
      <article class="app-card request-metric">
        <span>Failed requests</span><strong>{{ failedCount }}</strong
        ><small>HTTP status 400 and above</small>
      </article>
      <article class="app-card request-metric">
        <span>Slow requests</span><strong>{{ slowCount }}</strong
        ><small>At least 1 second</small>
      </article>
      <article class="app-card request-metric">
        <span>Average response</span><strong>{{ formatDuration(averageDuration) }}</strong
        ><small>Across all matching requests</small>
      </article>
    </div>

    <AppTable
      ref="table"
      :resource="requestReportsApi"
      :columns="columns"
      table-class="request-page__table"
      :filters="filters"
      row-key="request_id"
      sort-by="started_on"
      search-placeholder="Search request ID, route, or endpoint"
      empty-icon="timeline"
      empty-title="No requests found"
      empty-message="Try a different search or outcome."
      @loaded="onLoaded"
      @row-click="openRequest"
    >
      <template #toolbar>
        <q-btn
          outline
          no-caps
          color="primary"
          icon="tune"
          label="Advanced filters"
          @click="filterDialogOpen = true"
        >
          <q-badge v-if="advancedFilters.length" color="primary" floating>
            {{ advancedFilters.length }}
          </q-badge>
        </q-btn>
      </template>
      <template #body-cell-started_on="props"
        ><q-td :props="props">{{ formatDate(props.value) }}</q-td></template
      >
      <template #body-cell-request_id="props"
        ><q-td :props="props">
          <div class="request-page__request-id">
            <code :title="props.value">{{ props.value }}</code>
            <q-btn
              flat
              round
              dense
              size="sm"
              icon="content_copy"
              aria-label="Copy request ID"
              @click.stop="copyRequestId(props.value)"
            >
              <q-tooltip>Copy request ID</q-tooltip>
            </q-btn>
          </div>
        </q-td></template
      >
      <template #body-cell-method="props"
        ><q-td :props="props">
          <q-badge
            class="request-method"
            :class="`request-method--${String(props.value).toLowerCase()}`"
          >
            {{ props.value }}
          </q-badge>
        </q-td></template
      >
      <template #body-cell-status_code="props"
        ><q-td :props="props">
          <q-badge class="request-status" :class="statusClass(props.value)">
            {{ props.value }}
          </q-badge>
        </q-td></template
      >
      <template #body-cell-duration_ms="props"
        ><q-td :props="props">
          <div
            class="request-duration"
            :title="`Average: ${formatDuration(averageDuration)} · Marker shows the average`"
          >
            <strong class="request-duration__value">{{ formatDuration(props.value) }}</strong>
            <span class="request-duration__track" aria-hidden="true">
              <span
                class="request-duration__fill"
                :class="durationClass(props.value)"
                :style="durationStyle(props.value)"
              />
              <span
                class="request-duration__average"
                :class="durationClass(props.value)"
                :style="averageStyle()"
              />
            </span>
          </div> </q-td
      ></template>
      <template #body-cell-slowest_service="props"
        ><q-td :props="props"
          >{{ props.value || '—'
          }}<span v-if="props.row.slowest_service_ms" class="text-app-muted">
            · {{ formatDuration(props.row.slowest_service_ms) }}</span
          ></q-td
        ></template
      >
      <template #body-cell-failure_reason="props"
        ><q-td :props="props" class="request-page__failure">{{
          props.value || '—'
        }}</q-td></template
      >
    </AppTable>
    <div class="request-page__table-hint text-caption text-app-muted">
      Select a request row to inspect its full lifecycle and service timing.
    </div>

    <RequestTraceDrawer
      :model-value="traceOpen"
      :request-id="selectedRequestId"
      @update:model-value="setTraceOpen"
    />

    <q-dialog v-model="filterDialogOpen">
      <q-card class="request-filter-dialog">
        <q-card-section class="row items-center no-wrap">
          <div>
            <div class="text-h6">Advanced filters</div>
            <div class="text-caption text-app-muted">
              Combine conditions to narrow request records.
            </div>
          </div>
          <q-space />
          <q-btn v-close-popup flat round dense icon="close" aria-label="Close filters" />
        </q-card-section>
        <q-separator />
        <q-card-section class="request-filter-dialog__fields">
          <q-select
            v-model="draft.method"
            outlined
            dense
            clearable
            label="HTTP method"
            :options="methods"
          />
          <q-select
            v-model="draft.status"
            outlined
            dense
            clearable
            label="HTTP status"
            :options="statusOptions"
            emit-value
            map-options
          />
          <q-input
            v-model.number="draft.minDuration"
            outlined
            dense
            type="number"
            min="0"
            label="Min response time (ms)"
          />
          <q-input
            v-model.number="draft.maxDuration"
            outlined
            dense
            type="number"
            min="0"
            label="Max response time (ms)"
          />
          <q-input
            v-model="draft.route"
            outlined
            dense
            clearable
            label="Route contains"
            class="request-filter-dialog__wide"
          >
            <template #prepend><q-icon name="route" /></template>
          </q-input>
          <q-input
            v-model="draft.startedAfter"
            outlined
            dense
            type="datetime-local"
            step="1"
            label="Received from"
          />
          <q-input
            v-model="draft.startedBefore"
            outlined
            dense
            type="datetime-local"
            step="1"
            label="Received to"
          />
        </q-card-section>
        <q-separator />
        <q-card-actions align="between" class="q-pa-md">
          <q-btn flat no-caps label="Clear all" @click="clearAdvancedFilters" />
          <div class="row q-gutter-sm">
            <q-btn v-close-popup flat no-caps label="Cancel" />
            <q-btn
              v-close-popup
              unelevated
              no-caps
              color="primary"
              label="Apply filters"
              @click="applyAdvancedFilters"
            />
          </div>
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppPageHeader from '@/components/AppPageHeader.vue'
import AppTable from '@/components/AppTable.vue'

import RequestTraceDrawer from '../components/RequestTraceDrawer.vue'
import { requestReportsApi } from '../api.js'

const route = useRoute()
const router = useRouter()
const view = ref('all')
const rows = ref([])
const totalCount = ref(0)
const traceOpen = ref(false)
const selectedRequestId = ref('')
const filterDialogOpen = ref(false)
const methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD']
const statusOptions = [
  { label: '2xx · Successful', value: 'success' },
  { label: '3xx · Redirect', value: 'redirect' },
  { label: '4xx · Client error', value: 'client_error' },
  { label: '5xx · Server error', value: 'server_error' },
]
const emptyDraft = () => ({
  method: null,
  status: null,
  minDuration: null,
  maxDuration: null,
  route: '',
  startedAfter: '',
  startedBefore: '',
})
const draft = ref(emptyDraft())
const advancedFilters = ref([])
const viewOptions = [
  { label: 'All requests', value: 'all' },
  { label: 'Failures', value: 'failed' },
  { label: 'Slow ≥ 1s', value: 'slow' },
]
const filters = computed(() => {
  const combined = [...advancedFilters.value]
  if (view.value === 'failed') combined.push({ field: 'status_code', op: 'gte', value: 400 })
  if (view.value === 'slow') combined.push({ field: 'duration_ms', op: 'gte', value: 1000 })
  return combined
})
const columns = [
  {
    name: 'started_on',
    label: 'Received',
    field: 'started_on',
    sortable: true,
    align: 'left',
    style: 'width: 12%',
  },
  {
    name: 'request_id',
    label: 'Request ID',
    field: 'request_id',
    align: 'left',
    style: 'width: 17%',
  },
  { name: 'method', label: 'Method', field: 'method', align: 'left', style: 'width: 6%' },
  { name: 'route', label: 'Route', field: 'route', align: 'left', style: 'width: 18%' },
  {
    name: 'status_code',
    label: 'HTTP',
    field: 'status_code',
    sortable: true,
    align: 'left',
    style: 'width: 6%',
  },
  {
    name: 'duration_ms',
    label: 'Response time',
    field: 'duration_ms',
    sortable: true,
    align: 'left',
    style: 'width: 10%',
  },
  {
    name: 'service_calls',
    label: 'Services',
    field: 'service_calls',
    align: 'right',
    style: 'width: 5%',
  },
  {
    name: 'slowest_service',
    label: 'Slowest service',
    field: 'slowest_service',
    align: 'left',
    style: 'width: 16%',
  },
  {
    name: 'failure_reason',
    label: 'Failure reason',
    field: 'failure_reason',
    align: 'left',
    style: 'width: 10%',
  },
]
const failedCount = computed(() => rows.value.filter((row) => row.status_code >= 400).length)
const slowCount = computed(() => rows.value.filter((row) => row.duration_ms >= 1000).length)
const averageDuration = ref(0)
function onLoaded(data) {
  rows.value = data.records
  totalCount.value = data.metadata.total_count ?? data.records.length
  averageDuration.value = data.metadata.average_duration_ms ?? 0
}
async function copyRequestId(requestId) {
  try {
    await navigator.clipboard.writeText(String(requestId))
  } catch {
    // Clipboard access may be unavailable outside secure browser contexts.
  }
}
function applyAdvancedFilters() {
  const next = []
  const add = (field, op, value) => next.push({ field, op, value })
  if (draft.value.method) add('method', 'eq', draft.value.method)
  const statusRanges = {
    success: ['gte', 200, 'lte', 299],
    redirect: ['gte', 300, 'lte', 399],
    client_error: ['gte', 400, 'lte', 499],
    server_error: ['gte', 500, 'lte', 599],
  }
  if (draft.value.status) {
    const [lowerOp, lower, upperOp, upper] = statusRanges[draft.value.status]
    add('status_code', lowerOp, lower)
    add('status_code', upperOp, upper)
  }
  if (draft.value.minDuration !== null && draft.value.minDuration !== '')
    add('duration_ms', 'gte', Number(draft.value.minDuration))
  if (draft.value.maxDuration !== null && draft.value.maxDuration !== '')
    add('duration_ms', 'lte', Number(draft.value.maxDuration))
  if (draft.value.route.trim()) add('route', 'contains', draft.value.route.trim())
  if (draft.value.startedAfter && draft.value.startedBefore) {
    add('started_on', 'between', [
      new Date(draft.value.startedAfter).toISOString(),
      new Date(draft.value.startedBefore).toISOString(),
    ])
  } else if (draft.value.startedAfter) {
    add('started_on', 'gte', new Date(draft.value.startedAfter).toISOString())
  } else if (draft.value.startedBefore) {
    add('started_on', 'lte', new Date(draft.value.startedBefore).toISOString())
  }
  advancedFilters.value = next
}
function clearAdvancedFilters() {
  draft.value = emptyDraft()
  advancedFilters.value = []
}
function statusClass(code) {
  if (code >= 500) return 'request-status--server-error'
  if (code >= 400) return 'request-status--client-error'
  if (code >= 300) return 'request-status--redirect'
  return 'request-status--success'
}
function durationStyle(value) {
  const max = Math.max(
    ...rows.value.map((row) => Number(row.duration_ms) || 0),
    averageDuration.value,
    1,
  )
  return { width: `${Math.max((Number(value) / max) * 100, 2)}%` }
}
function averageStyle() {
  const max = Math.max(
    ...rows.value.map((row) => Number(row.duration_ms) || 0),
    averageDuration.value,
    1,
  )
  return { left: `${(averageDuration.value / max) * 100}%` }
}
function durationClass(value) {
  if (value >= averageDuration.value * 1.5) return 'request-duration__fill--high'
  if (value > averageDuration.value) return 'request-duration__fill--above'
  return 'request-duration__fill--below'
}
function openRequest(row) {
  router.replace({
    name: 'request-lifecycle',
    query: { ...route.query, requestId: row.request_id },
  })
}
function setTraceOpen(open) {
  traceOpen.value = open
  if (open) return
  selectedRequestId.value = ''
  const query = { ...route.query }
  delete query.requestId
  router.replace({ name: 'request-lifecycle', query })
}
watch(
  () => route.query.requestId,
  (requestId) => {
    selectedRequestId.value = typeof requestId === 'string' ? requestId : ''
    traceOpen.value = Boolean(selectedRequestId.value)
  },
  { immediate: true },
)
const dateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'medium',
})
function formatDate(value) {
  return value ? dateFormatter.format(new Date(value)) : '—'
}
function formatDuration(value = 0) {
  return value < 1000 ? `${Number(value).toFixed(1)} ms` : `${(value / 1000).toFixed(2)} s`
}
</script>

<style scoped lang="scss">
.request-page__metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--app-space-md);
  margin-bottom: var(--app-space-md);
}
.request-metric {
  display: grid;
  gap: 6px;
  padding: var(--app-space-md) var(--app-space-lg);
}
.request-metric span,
.request-metric small {
  color: var(--app-text-muted);
  font-size: 12px;
}
.request-metric strong {
  font-size: 27px;
  line-height: 1;
}
.request-page__failure {
  max-width: 260px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.request-page__table :deep(.q-table) {
  width: 100%;
  table-layout: fixed;
}
.request-page__table :deep(tbody td) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.request-page__request-id {
  display: flex;
  align-items: center;
  gap: var(--app-space-xs);
  max-width: 230px;
}
.request-page__request-id code {
  overflow: hidden;
  color: var(--app-text-muted);
  font-size: 11px;
  text-overflow: ellipsis;
}
.request-filter-dialog {
  width: min(620px, calc(100vw - 32px));
  max-width: 620px;
}
.request-filter-dialog__fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--app-space-md);
  padding: var(--app-space-lg);
}
.request-filter-dialog__wide {
  grid-column: 1 / -1;
}
.request-method,
.request-status {
  border: 1px solid currentColor;
  border-radius: var(--app-radius-sm);
  font-weight: 600;
}
.request-method--get {
  color: var(--app-info);
  background: color-mix(in srgb, var(--app-info) 10%, transparent);
}
.request-method--post {
  color: var(--app-positive);
  background: color-mix(in srgb, var(--app-positive) 10%, transparent);
}
.request-method--put,
.request-method--patch {
  color: var(--app-warning);
  background: color-mix(in srgb, var(--app-warning) 10%, transparent);
}
.request-method--delete {
  color: var(--app-negative);
  background: color-mix(in srgb, var(--app-negative) 10%, transparent);
}
.request-method--options,
.request-method--head {
  color: var(--app-text-muted);
  background: var(--app-surface-muted);
}
.request-status--success {
  color: var(--app-positive);
  background: color-mix(in srgb, var(--app-positive) 12%, transparent);
}
.request-duration__fill--below {
  color: var(--app-positive);
  background: color-mix(in srgb, var(--app-positive) 42%, transparent);
}
.request-status--redirect {
  color: var(--app-info);
  background: color-mix(in srgb, var(--app-info) 12%, transparent);
}
.request-status--client-error {
  color: var(--app-warning);
  background: color-mix(in srgb, var(--app-warning) 12%, transparent);
}
.request-duration__fill--above {
  color: var(--app-warning);
  background: color-mix(in srgb, var(--app-warning) 42%, transparent);
}
.request-status--server-error {
  color: var(--app-negative);
  background: color-mix(in srgb, var(--app-negative) 12%, transparent);
}
.request-duration__fill--high {
  color: var(--app-negative);
  background: color-mix(in srgb, var(--app-negative) 42%, transparent);
}
.request-duration {
  display: flex;
  align-items: center;
  gap: var(--app-space-sm);
  min-width: 190px;
}
.request-duration__value {
  min-width: 62px;
  color: var(--app-text);
  font-size: 12px;
  font-weight: 650;
  white-space: nowrap;
}
.request-duration__track {
  position: relative;
  display: block;
  width: 112px;
  height: 10px;
  overflow: hidden;
  border: 1px solid var(--app-border);
  border-radius: 999px;
  background: var(--app-surface-muted);
  box-sizing: border-box;
}
.request-duration__fill {
  position: absolute;
  inset: 0 auto 0 0;
  border-radius: inherit;
  opacity: 1;
}
.request-duration__average {
  position: absolute;
  z-index: 1;
  inset: 0 auto 0 0;
  border-left: 2px solid currentColor;
  filter: brightness(0.72);
}
.request-page__table-hint {
  padding: 9px var(--app-space-sm);
}
@media (max-width: 800px) {
  .request-page__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 480px) {
  .request-page__metrics {
    grid-template-columns: 1fr 1fr;
  }
  .request-metric {
    padding: var(--app-space-md);
  }
}
@media (max-width: 600px) {
  .request-filter-dialog__fields {
    grid-template-columns: 1fr;
  }
  .request-filter-dialog__wide {
    grid-column: auto;
  }
}
</style>
