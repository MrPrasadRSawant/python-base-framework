<template>
  <q-page class="app-page exception-page">
    <AppPageHeader
      title="Exception Analysis"
      subtitle="Understand error volume, recurring failures, and their affected requests."
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

    <div class="exception-page__metrics">
      <article class="app-card exception-metric">
        <span>Events on this page</span><strong>{{ rows.length }}</strong>
        <small>Latest recorded exceptions</small>
      </article>
      <article class="app-card exception-metric">
        <span>Server errors</span><strong>{{ serverErrors }}</strong>
        <small>HTTP status 500 and above</small>
      </article>
      <article class="app-card exception-metric">
        <span>Client errors</span><strong>{{ clientErrors }}</strong>
        <small>HTTP status 400 to 499</small>
      </article>
      <article class="app-card exception-metric">
        <span>Distinct error types</span><strong>{{ typeCount }}</strong>
        <small>Across the current page</small>
      </article>
    </div>

    <section class="app-card exception-page__patterns">
      <div>
        <h2>Recurring error codes</h2>
        <p>Most frequent codes in the current result page</p>
      </div>
      <div v-if="topCodes.length" class="exception-page__bars">
        <div v-for="entry in topCodes" :key="entry.code" class="exception-page__bar-row">
          <code>{{ entry.code }}</code>
          <q-linear-progress
            rounded
            size="8px"
            color="negative"
            :value="entry.count / maxCodeCount"
          />
          <strong>{{ entry.count }}</strong>
        </div>
      </div>
      <div v-else class="text-app-muted q-mt-md">No error codes in this result page.</div>
    </section>

    <AppTable
      ref="table"
      :resource="exceptionsApi"
      :columns="columns"
      :filters="filters"
      sort-by="occurred_on"
      search-placeholder="Search error, type, path, or code"
      empty-icon="check_circle"
      empty-title="No exceptions found"
      empty-message="Try a different search or severity."
      @loaded="onLoaded"
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
const table = ref(null)
const rows = ref([])
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
const serverErrors = computed(() => rows.value.filter((row) => row.status_code >= 500).length)
const clientErrors = computed(
  () => rows.value.filter((row) => row.status_code >= 400 && row.status_code < 500).length,
)
const typeCount = computed(
  () => new Set(rows.value.map((row) => row.exception_type).filter(Boolean)).size,
)
const topCodes = computed(() => {
  const counts = new Map()
  for (const row of rows.value) {
    const code = row.error_code || row.exception_type || 'Unclassified'
    counts.set(code, (counts.get(code) || 0) + 1)
  }
  return [...counts]
    .map(([code, count]) => ({ code, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 5)
})
const maxCodeCount = computed(() => Math.max(1, ...topCodes.value.map((item) => item.count)))

function onLoaded(data) {
  rows.value = data.records
}
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
.exception-page__metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--app-space-md);
  margin-bottom: var(--app-space-md);
}
.exception-metric {
  display: grid;
  gap: 6px;
  padding: var(--app-space-md) var(--app-space-lg);
}
.exception-metric span,
.exception-metric small {
  color: var(--app-text-muted);
  font-size: 12px;
}
.exception-metric strong {
  font-size: 27px;
  line-height: 1;
}
.exception-page__patterns {
  display: grid;
  grid-template-columns: minmax(180px, 0.7fr) minmax(320px, 1.5fr);
  gap: var(--app-space-lg);
  padding: var(--app-space-lg);
  margin-bottom: var(--app-space-md);
}
.exception-page__patterns h2 {
  margin: 0;
  font-size: 15px;
}
.exception-page__patterns p {
  margin: 5px 0 0;
  color: var(--app-text-muted);
  font-size: 12px;
}
.exception-page__bars {
  display: grid;
  gap: 9px;
}
.exception-page__bar-row {
  display: grid;
  grid-template-columns: minmax(100px, 1fr) minmax(80px, 3fr) 32px;
  align-items: center;
  gap: var(--app-space-sm);
  font-size: 12px;
}
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
@media (max-width: 800px) {
  .exception-page__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .exception-page__patterns {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 480px) {
  .exception-page__metrics {
    grid-template-columns: 1fr 1fr;
  }
  .exception-metric {
    padding: var(--app-space-md);
  }
}
</style>
