<template>
  <q-dialog
    :model-value="modelValue"
    position="right"
    full-height
    transition-show="slide-left"
    transition-hide="slide-right"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <q-card class="trace-drawer">
      <header class="trace-drawer__header">
        <q-btn
          flat
          round
          dense
          icon="arrow_back"
          aria-label="Close request trace"
          @click="closeDrawer"
        />
        <div class="trace-drawer__title">
          <h1>Request trace</h1>
          <span>{{ report?.route || report?.endpoint || 'Request details' }}</span>
        </div>
        <q-space />
        <q-btn
          flat
          round
          dense
          icon="content_copy"
          aria-label="Copy request ID"
          :disable="!requestId"
          @click="copyId"
        >
          <q-tooltip>Copy request ID</q-tooltip>
        </q-btn>
        <q-btn
          flat
          round
          dense
          icon="refresh"
          :loading="loading"
          aria-label="Refresh trace"
          @click="load"
        />
        <q-btn flat round dense icon="close" aria-label="Close trace panel" @click="closeDrawer" />
      </header>
      <div class="trace-drawer__body">
        <q-banner v-if="error" rounded class="bg-negative text-white q-mb-md">
          <template #avatar><q-icon name="error_outline" /></template>
          {{ error }}
          <template #action>
            <q-btn flat no-caps color="white" label="Close trace" @click="closeDrawer" />
          </template>
        </q-banner>

        <template v-if="report">
          <section class="app-card request-head">
            <div class="request-head__identity">
              <span class="request-head__method">{{ report.method }}</span>
              <div class="request-head__route-block">
                <strong>{{ report.route || report.endpoint || 'Unknown route' }}</strong>
                <code>{{ report.request_id }}</code>
              </div>
            </div>
            <div class="request-head__facts">
              <AppStatusChip
                :status="report.outcome === 'failed' ? 'failed' : 'success'"
                :label="`${report.status_code} · ${report.outcome}`"
              />
              <div>
                <span>Duration</span><strong>{{ duration(report.timing.request_ms) }}</strong>
              </div>
              <div>
                <span>Service calls</span><strong>{{ report.timing.service_calls }}</strong>
              </div>
              <div>
                <span>Started</span><strong>{{ formatDate(report.started_on) }}</strong>
              </div>
            </div>
          </section>

          <div class="trace-workspace">
            <main class="trace-workspace__main">
              <section class="app-card trace-panel">
                <header class="trace-panel__header">
                  <div>
                    <h2>Request timeline</h2>
                    <p>
                      Bars show when each operation ran and how long it took within the request.
                    </p>
                  </div>
                  <q-btn-toggle
                    v-model="traceView"
                    unelevated
                    no-caps
                    toggle-color="primary"
                    :options="[
                      { label: 'Flame graph', value: 'flame', icon: 'align_horizontal_left' },
                      { label: 'Span list', value: 'list', icon: 'view_list' },
                    ]"
                    aria-label="Choose trace view"
                  />
                </header>

                <div v-if="traceView === 'flame'" class="trace-layout">
                  <div class="trace-waterfall">
                    <div class="trace-waterfall__ruler">
                      <div class="trace-waterfall__label">Operation</div>
                      <div class="trace-waterfall__axis">
                        <span v-for="tick in ticks" :key="tick" :style="{ left: `${tick}%` }">{{
                          duration((report.timing.request_ms * tick) / 100)
                        }}</span>
                      </div>
                    </div>

                    <button
                      class="trace-row trace-row--root"
                      :class="{ 'trace-row--selected': selectedIndex === -1 }"
                      type="button"
                      @click="selectRoot"
                    >
                      <span class="trace-row__name"
                        ><q-icon name="north_east" />{{ report.method }}
                        {{ report.route || report.endpoint || 'Request' }}</span
                      >
                      <span class="trace-row__track">
                        <span
                          class="trace-row__bar trace-row__bar--root"
                          :style="{ left: '0%', width: '100%' }"
                        >
                          <span>{{ duration(report.timing.request_ms) }}</span>
                          <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">
                            <div class="trace-tooltip">
                              <strong>Total request</strong>
                              <span>Started · {{ formatAt(report.started_on, 0) }}</span>
                              <span
                                >Ended ·
                                {{ formatAt(report.started_on, report.timing.request_ms) }}</span
                              >
                              <span>Duration · {{ duration(report.timing.request_ms) }}</span>
                            </div>
                          </q-tooltip>
                        </span>
                      </span>
                    </button>

                    <button
                      v-for="(service, index) in report.services"
                      :key="`${service.call_order ?? index}-${service.service_name}`"
                      class="trace-row"
                      :class="[
                        { 'trace-row--selected': selectedIndex === index },
                        service.status === 'failed'
                          ? 'trace-row--failed'
                          : `trace-row--tone-${serviceTone(service.service_name)}`,
                      ]"
                      type="button"
                      @click="selectService(index)"
                    >
                      <span
                        class="trace-row__name"
                        :style="{ paddingLeft: `${12 + Math.min(service.depth, 4) * 16}px` }"
                      >
                        <q-icon
                          :name="
                            service.status === 'failed'
                              ? 'error_outline'
                              : 'subdirectory_arrow_right'
                          "
                        />
                        {{ service.service_name }}
                      </span>
                      <span class="trace-row__track">
                        <span class="trace-row__bar" :style="barStyle(service)">
                          <span>{{ duration(service.duration_ms) }}</span>
                          <q-tooltip anchor="top middle" self="bottom middle" :offset="[0, 8]">
                            <div class="trace-tooltip">
                              <strong>{{ service.service_name }}</strong>
                              <span
                                >Started ·
                                {{ formatAt(report.started_on, service.offset_ms) }}</span
                              >
                              <span
                                >Ended ·
                                {{
                                  formatAt(
                                    report.started_on,
                                    service.offset_ms + service.duration_ms,
                                  )
                                }}</span
                              >
                              <span>Total · {{ duration(service.duration_ms) }}</span>
                              <span>Own time · {{ duration(service.self_ms) }}</span>
                              <span>Status · {{ service.status }}</span>
                            </div>
                          </q-tooltip>
                        </span>
                      </span>
                    </button>

                    <AppEmptyState
                      v-if="!report.services.length"
                      icon="data_object"
                      title="No service spans recorded"
                      message="The request completed without tracked service calls."
                    />
                  </div>

                  <aside class="trace-legend">
                    <div class="trace-legend__heading">
                      <strong>Services</strong><span>Own time</span>
                    </div>
                    <div
                      v-for="entry in serviceLegend"
                      :key="entry.name"
                      class="trace-legend__item"
                    >
                      <span
                        class="trace-legend__dot"
                        :class="
                          entry.failed
                            ? 'trace-legend__dot--failed'
                            : `trace-legend__dot--tone-${serviceTone(entry.name)}`
                        "
                      />
                      <div class="trace-legend__name" :title="entry.name">
                        {{ entry.name
                        }}<small
                          >{{ entry.calls }} call{{ entry.calls === 1 ? '' : 's'
                          }}<template v-if="entry.failed">
                            · {{ entry.failed }} failed</template
                          ></small
                        >
                      </div>
                      <strong>{{ duration(entry.ownMs) }}</strong>
                      <span class="trace-legend__percent">{{ percent(entry.ownMs) }}</span>
                    </div>
                    <div class="trace-legend__footnote">
                      Own time excludes nested service calls. Parallel work can overlap.
                    </div>
                  </aside>
                </div>

                <div v-else class="trace-spans">
                  <q-table
                    flat
                    dense
                    :rows="spanRows"
                    :columns="spanColumns"
                    row-key="rowKey"
                    :pagination="{ rowsPerPage: 0 }"
                    hide-pagination
                    class="trace-spans__table"
                    @row-click="selectSpanRow"
                  >
                    <template #body-cell-service_name="props">
                      <q-td
                        :props="props"
                        :class="{ 'trace-spans__selected': selectedIndex === props.row.index }"
                      >
                        <span :style="{ paddingLeft: `${Math.min(props.row.depth, 4) * 16}px` }">{{
                          props.value
                        }}</span>
                      </q-td>
                    </template>
                    <template #body-cell-status="props">
                      <q-td :props="props"
                        ><AppStatusChip :status="props.value === 'failed' ? 'failed' : 'success'"
                      /></q-td>
                    </template>
                    <template #body-cell-offset_ms="props"
                      ><q-td :props="props">{{ duration(props.value) }}</q-td></template
                    >
                    <template #body-cell-duration_ms="props"
                      ><q-td :props="props">{{ duration(props.value) }}</q-td></template
                    >
                    <template #body-cell-self_ms="props"
                      ><q-td :props="props">{{ duration(props.value) }}</q-td></template
                    >
                  </q-table>
                </div>
              </section>
            </main>

            <aside class="trace-workspace__inspector">
              <section class="app-card span-detail">
                <button
                  class="inspector-section__toggle span-detail__header"
                  type="button"
                  :aria-expanded="inspectorSections.span"
                  aria-controls="trace-span-content"
                  @click="toggleInspectorSection('span')"
                >
                  <div>
                    <span class="eyebrow">{{
                      selectedService ? 'Selected span' : 'Request span'
                    }}</span>
                    <h2>
                      {{
                        selectedService?.service_name ||
                        `${report.method} ${report.route || 'request'}`
                      }}
                    </h2>
                  </div>
                  <AppStatusChip
                    :status="
                      selectedService
                        ? selectedService.status === 'failed'
                          ? 'failed'
                          : 'success'
                        : report.outcome === 'failed'
                          ? 'failed'
                          : 'success'
                    "
                    :label="selectedService?.status || report.outcome"
                  />
                  <q-icon
                    class="inspector-section__icon"
                    :class="{ 'inspector-section__icon--open': inspectorSections.span }"
                    name="expand_more"
                  />
                </button>
                <q-slide-transition>
                  <div id="trace-span-content" v-show="inspectorSections.span">
                    <div class="span-detail__facts">
                      <div>
                        <span>Start offset</span
                        ><strong>{{ duration(selectedService?.offset_ms || 0) }}</strong>
                      </div>
                      <div>
                        <span>Total duration</span
                        ><strong>{{
                          duration(selectedService?.duration_ms ?? report.timing.request_ms)
                        }}</strong>
                      </div>
                      <div>
                        <span>Own time</span
                        ><strong>{{
                          duration(selectedService?.self_ms ?? report.timing.request_ms)
                        }}</strong>
                      </div>
                      <div>
                        <span>Parent</span><strong>{{ parentName || 'Request handler' }}</strong>
                      </div>
                      <div>
                        <span>Endpoint</span><strong>{{ report.endpoint || '—' }}</strong>
                      </div>
                      <div>
                        <span>Response</span><strong>HTTP {{ report.status_code }}</strong>
                      </div>
                    </div>
                    <div v-if="selectedService?.error_type" class="span-detail__error">
                      {{ selectedService.error_type }}
                    </div>
                  </div>
                </q-slide-transition>
              </section>

              <section class="app-card timing-detail">
                <button
                  class="inspector-section__toggle timing-detail__header"
                  type="button"
                  :aria-expanded="inspectorSections.timing"
                  aria-controls="trace-timing-content"
                  @click="toggleInspectorSection('timing')"
                >
                  <div>
                    <span class="eyebrow">Request timing</span>
                    <h2>Where time went</h2>
                  </div>
                  <strong>{{ duration(report.timing.request_ms) }}</strong>
                  <q-icon
                    class="inspector-section__icon"
                    :class="{ 'inspector-section__icon--open': inspectorSections.timing }"
                    name="expand_more"
                  />
                </button>
                <q-slide-transition>
                  <div id="trace-timing-content" v-show="inspectorSections.timing">
                    <div class="timing-detail__row">
                      <span>Tracked service calls <small>aggregate</small></span>
                      <strong>{{ duration(report.timing.in_services_ms) }}</strong>
                    </div>
                    <q-linear-progress
                      rounded
                      size="7px"
                      color="primary"
                      :value="
                        Math.min(
                          report.timing.in_services_ms / Math.max(report.timing.request_ms, 1),
                          1,
                        )
                      "
                    />
                    <div class="timing-detail__row q-mt-sm">
                      <span>Outside tracked calls <small>estimated</small></span>
                      <strong>{{ duration(report.timing.outside_services_ms) }}</strong>
                    </div>
                    <q-linear-progress
                      rounded
                      size="7px"
                      color="warning"
                      :value="
                        Math.min(
                          report.timing.outside_services_ms / Math.max(report.timing.request_ms, 1),
                          1,
                        )
                      "
                    />
                    <div v-if="report.timing.slowest_service" class="timing-detail__slowest">
                      <span>Highest own time</span>
                      <strong>{{ report.timing.slowest_service }}</strong>
                      <small>{{ duration(report.timing.slowest_service_ms) }}</small>
                    </div>
                    <p class="timing-detail__note">
                      Calls can overlap, so aggregate service time may exceed request time. New logs
                      can take about one second to appear.
                    </p>
                  </div>
                </q-slide-transition>
              </section>

              <section class="app-card request-events">
                <button
                  class="inspector-section__toggle request-events__header"
                  type="button"
                  :aria-expanded="inspectorSections.events"
                  aria-controls="trace-events-content"
                  @click="toggleInspectorSection('events')"
                >
                  <div>
                    <h2>Request events</h2>
                    <p>Recorded exception context associated with this trace.</p>
                  </div>
                  <q-badge outline>{{ report.failure ? '1 event' : '0 events' }}</q-badge>
                  <q-icon
                    class="inspector-section__icon"
                    :class="{ 'inspector-section__icon--open': inspectorSections.events }"
                    name="expand_more"
                  />
                </button>
                <q-slide-transition>
                  <div id="trace-events-content" v-show="inspectorSections.events">
                    <div v-if="report.failure" class="request-events__item">
                      <div class="request-events__time">
                        <q-icon name="error_outline" color="negative" />{{
                          formatDate(report.started_on)
                        }}
                      </div>
                      <div class="request-events__body">
                        <div class="row items-center q-gutter-sm">
                          <strong>{{
                            report.failure.error_code ||
                            report.failure.exception_type ||
                            'Request error'
                          }}</strong><AppStatusChip
                            :status="report.failure.kind === 'server_error' ? 'failed' : 'warning'"
                            :label="report.failure.kind.replace('_', ' ')"
                          />
                        </div>
                        <p>{{ report.failure.message }}</p>
                      </div>
                      <q-btn
                        v-if="auth.can('exception_logs:read')"
                        flat
                        no-caps
                        color="primary"
                        label="Open exception"
                        :loading="exceptionLoading"
                        @click="openException"
                      />
                    </div>
                    <div v-else class="request-events__empty">
                      <q-icon name="task_alt" color="positive" />
                      <span>No exception was linked to this request.</span>
                    </div>
                  </div>
                </q-slide-transition>
              </section>
            </aside>
          </div>
        </template>

        <q-inner-loading :showing="loading"
          ><q-spinner-dots size="40px" color="primary"
        /></q-inner-loading>
      </div>
    </q-card>
  </q-dialog>

  <q-dialog v-model="exceptionOpen">
    <q-card class="trace-exception">
      <q-card-section class="row items-start"
        ><div class="col">
          <div class="text-h6">Exception context</div>
          <div class="text-caption text-app-muted">Redacted traceback and error metadata</div>
        </div>
        <q-btn flat round dense icon="close" aria-label="Close" @click="exceptionOpen = false"
      /></q-card-section>
      <q-separator />
      <q-card-section v-if="exception"
        ><div class="text-subtitle2">{{ exception.error_code || exception.exception_type }}</div>
        <p>{{ exception.message }}</p>
        <pre class="trace-exception__trace">{{
          exception.traceback || 'No traceback was recorded.'
        }}</pre>
      </q-card-section>
    </q-card>
  </q-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

import AppEmptyState from '@/components/AppEmptyState.vue'
import AppStatusChip from '@/components/AppStatusChip.vue'
import { useAuthStore } from '@/module/auth'

import { getException, requestReportsApi } from '../api.js'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  requestId: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])
const auth = useAuthStore()
const report = ref(null)
const loading = ref(false)
const error = ref('')
const traceView = ref('flame')
const selectedIndex = ref(-1)
const inspectorSections = ref({ span: true, timing: false, events: false })
const ticks = [0, 20, 40, 60, 80, 100]

const selectedService = computed(() => report.value?.services[selectedIndex.value] ?? null)
const parentName = computed(() => {
  const order = selectedService.value?.parent_call_order
  return order == null
    ? selectedService.value
      ? 'Request handler'
      : '—'
    : report.value.services.find((service) => service.call_order === order)?.service_name ||
        `Call #${order}`
})
const serviceLegend = computed(() => {
  const groups = new Map()
  for (const service of report.value?.services || []) {
    const entry = groups.get(service.service_name) || {
      name: service.service_name,
      calls: 0,
      ownMs: 0,
      failed: 0,
    }
    entry.calls += 1
    entry.ownMs += service.self_ms
    if (service.status === 'failed') entry.failed += 1
    groups.set(service.service_name, entry)
  }
  return [...groups.values()].sort((a, b) => b.ownMs - a.ownMs)
})
const spanRows = computed(() =>
  (report.value?.services || []).map((service, index) => ({
    ...service,
    index,
    rowKey: `${service.call_order ?? index}-${service.service_name}`,
  })),
)
const spanColumns = [
  { name: 'service_name', label: 'Span', field: 'service_name', align: 'left' },
  { name: 'status', label: 'Status', field: 'status', align: 'left' },
  { name: 'offset_ms', label: 'Start offset', field: 'offset_ms', align: 'right' },
  { name: 'duration_ms', label: 'Duration', field: 'duration_ms', align: 'right' },
  { name: 'self_ms', label: 'Own time', field: 'self_ms', align: 'right' },
]

function serviceTone(name) {
  let hash = 0
  for (const char of name) hash = (hash * 31 + char.charCodeAt(0)) | 0
  return Math.abs(hash) % 5
}
function barStyle(service) {
  const total = Math.max(report.value?.timing.request_ms || 0, 1)
  const left = Math.min(Math.max((service.offset_ms / total) * 100, 0), 99)
  const width = Math.max(Math.min((service.duration_ms / total) * 100, 100 - left), 0.7)
  return { left: `${left}%`, width: `${width}%` }
}
function percent(value) {
  const total = report.value?.timing.request_ms || 0
  return total ? `${((value / total) * 100).toFixed(1)}%` : '—'
}
function selectRoot() {
  selectedIndex.value = -1
}
function selectService(index) {
  selectedIndex.value = index
}
function selectSpanRow(_, row) {
  selectedIndex.value = row.index
}
function toggleInspectorSection(section) {
  inspectorSections.value[section] = !inspectorSections.value[section]
}

async function load() {
  if (!props.requestId) return
  inspectorSections.value = { span: true, timing: false, events: false }
  loading.value = true
  error.value = ''
  report.value = null
  try {
    report.value = await requestReportsApi.get(props.requestId)
    selectedIndex.value = Math.max(
      report.value.services.findIndex((service) => service.is_slowest),
      0,
    )
    if (!report.value.services.length) selectedIndex.value = -1
  } catch (err) {
    error.value = err.message || 'Unable to load this request report.'
  } finally {
    loading.value = false
  }
}
function closeDrawer() {
  emit('update:modelValue', false)
}

const exceptionOpen = ref(false)
const exceptionLoading = ref(false)
const exception = ref(null)
async function openException() {
  if (!report.value?.failure) return
  exceptionLoading.value = true
  try {
    exception.value = await getException(report.value.failure.exception_log_id)
    exceptionOpen.value = true
  } catch (err) {
    error.value = err.message || 'Unable to load exception details.'
  } finally {
    exceptionLoading.value = false
  }
}

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'medium',
})
const timestampFormatter = new Intl.DateTimeFormat(undefined, {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  fractionalSecondDigits: 3,
  timeZoneName: 'short',
})
function formatDate(value) {
  return value ? dateFormatter.format(new Date(value)) : '—'
}
function formatAt(requestStartedOn, offsetMs) {
  return timestampFormatter.format(new Date(new Date(requestStartedOn).getTime() + offsetMs))
}
function duration(value = 0) {
  return value < 1000 ? `${Number(value).toFixed(1)} ms` : `${(value / 1000).toFixed(2)} s`
}
async function copyId() {
  try {
    await navigator.clipboard.writeText(String(props.requestId))
  } catch {
    error.value = 'Could not copy the request ID to the clipboard.'
  }
}
watch(
  () => [props.modelValue, props.requestId],
  ([isOpen, requestId]) => {
    if (isOpen && requestId) load()
  },
  { immediate: true },
)
</script>

<style scoped lang="scss">
.trace-drawer {
  display: flex;
  flex-direction: column;
  width: min(92vw, 1480px);
  max-width: 100vw;
  height: 100vh;
  max-height: 100vh;
  overflow: hidden;
  border-radius: var(--app-radius-lg) 0 0 var(--app-radius-lg);
  background: var(--app-bg);
}
.trace-drawer__header {
  display: flex;
  flex: none;
  align-items: center;
  gap: var(--app-space-sm);
  padding: var(--app-space-sm) var(--app-space-md);
  border-bottom: 1px solid var(--app-border);
  background: var(--app-surface);
}
.trace-drawer__title {
  display: grid;
  min-width: 0;
  gap: 2px;
}
.trace-drawer__title h1 {
  margin: 0;
  font-size: 14px;
  font-weight: 650;
}
.trace-drawer__title span {
  overflow: hidden;
  color: var(--app-text-muted);
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
}
.trace-drawer__body {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: var(--app-space-lg);
}
.trace-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(300px, 350px);
  align-items: start;
  gap: var(--app-space-md);
  min-width: 0;
}
.trace-workspace__main,
.trace-workspace__inspector {
  min-width: 0;
}
.trace-workspace__inspector {
  display: grid;
  align-content: start;
  gap: var(--app-space-md);
}
.request-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--app-space-lg);
  padding: var(--app-space-md) var(--app-space-lg);
  margin-bottom: var(--app-space-md);
}
.request-head__identity,
.request-head__facts {
  display: flex;
  align-items: center;
  gap: var(--app-space-md);
  min-width: 0;
}
.request-head__method {
  flex: none;
  padding: 7px 9px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  color: var(--app-primary);
  font-size: 12px;
  font-weight: 700;
}
.request-head__route-block {
  display: grid;
  gap: 4px;
  min-width: 0;
}
.request-head__route-block strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
}
.request-head__route-block code {
  overflow: hidden;
  color: var(--app-text-muted);
  text-overflow: ellipsis;
  font-size: 10px;
}
.request-head__facts > div {
  display: grid;
  gap: 3px;
  padding-left: var(--app-space-md);
  border-left: 1px solid var(--app-border);
  white-space: nowrap;
}
.request-head__facts span {
  color: var(--app-text-muted);
  font-size: 10px;
}
.request-head__facts strong {
  font-size: 12px;
}
.trace-panel {
  overflow: hidden;
  margin-bottom: var(--app-space-md);
}
.trace-panel__header,
.request-events > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--app-space-md);
  padding: var(--app-space-md) var(--app-space-lg);
  border-bottom: 1px solid var(--app-border);
}
.trace-panel__header h2,
.request-events h2,
.span-detail h2 {
  margin: 0;
  font-size: 14px;
  font-weight: 650;
}
.trace-panel__header p,
.request-events header p {
  margin: 4px 0 0;
  color: var(--app-text-muted);
  font-size: 11px;
}
.trace-panel {
  box-sizing: border-box;
  min-width: 0;
  max-width: 100%;
}
.trace-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(210px, 245px);
  min-width: 0;
  max-width: 100%;
  min-height: 240px;
}
.trace-waterfall {
  min-width: 0;
  padding: var(--app-space-md) 0;
}
.trace-waterfall__ruler,
.trace-row {
  display: grid;
  grid-template-columns: minmax(170px, 27%) minmax(0, 1fr);
  align-items: center;
}
.trace-waterfall__ruler {
  min-height: 34px;
  padding: 0 var(--app-space-md);
  color: var(--app-text-muted);
  font-size: 10px;
}
.trace-waterfall__label {
  font-weight: 600;
}
.trace-waterfall__axis {
  position: relative;
  height: 26px;
  border-bottom: 1px solid var(--app-border);
  background: repeating-linear-gradient(
    to right,
    transparent 0 calc(20% - 1px),
    var(--app-border) calc(20% - 1px) 20%
  );
}
.trace-waterfall__axis span {
  position: absolute;
  bottom: 4px;
  transform: translateX(-50%);
  white-space: nowrap;
}
.trace-waterfall__axis span:first-child {
  transform: none;
}
.trace-waterfall__axis span:last-child {
  transform: translateX(-100%);
}
.trace-row {
  position: relative;
  width: 100%;
  min-height: 35px;
  padding: 2px var(--app-space-md);
  border: 0;
  border-bottom: 1px solid var(--app-border);
  background: transparent;
  color: var(--app-text);
  text-align: left;
  cursor: pointer;
}
.trace-row:hover,
.trace-row--selected {
  background: var(--app-surface-muted);
}
.trace-row__name {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  overflow: hidden;
  color: var(--app-text-muted);
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
}
.trace-row__name .q-icon {
  flex: none;
  font-size: 13px;
}
.trace-row__track {
  position: relative;
  display: block;
  height: 27px;
  background: repeating-linear-gradient(
    to right,
    transparent 0 calc(20% - 1px),
    var(--app-border) calc(20% - 1px) 20%
  );
}
.trace-row__bar {
  position: absolute;
  top: 5px;
  bottom: 5px;
  display: flex;
  align-items: center;
  min-width: 4px;
  overflow: hidden;
  padding: 0 6px;
  border-left: 3px solid var(--app-primary);
  border-radius: 2px;
  background: color-mix(in srgb, var(--app-primary) 16%, var(--app-surface));
  color: var(--app-text);
  font-size: 10px;
  white-space: nowrap;
}
.trace-row__bar span {
  overflow: hidden;
  text-overflow: ellipsis;
}
.trace-tooltip {
  display: grid;
  gap: 4px;
  min-width: 190px;
  padding: 2px;
  font-size: 11px;
}
.trace-tooltip strong {
  margin-bottom: 2px;
  font-size: 12px;
}
.trace-row__bar--root {
  border-left-color: var(--app-text-muted);
  background: var(--app-surface-muted);
}
.trace-row--tone-1 .trace-row__bar {
  border-left-color: var(--app-info);
  background: color-mix(in srgb, var(--app-info) 16%, var(--app-surface));
}
.trace-row--tone-2 .trace-row__bar {
  border-left-color: var(--app-accent);
  background: color-mix(in srgb, var(--app-accent) 18%, var(--app-surface));
}
.trace-row--tone-3 .trace-row__bar {
  border-left-color: var(--app-positive);
  background: color-mix(in srgb, var(--app-positive) 16%, var(--app-surface));
}
.trace-row--tone-4 .trace-row__bar {
  border-left-color: var(--app-warning);
  background: color-mix(in srgb, var(--app-warning) 18%, var(--app-surface));
}
.trace-row--failed .trace-row__bar {
  border-left-color: var(--app-negative);
  background: color-mix(in srgb, var(--app-negative) 16%, var(--app-surface));
}
.trace-row--failed .trace-row__name {
  color: var(--app-negative);
}
.trace-legend {
  box-sizing: border-box;
  min-width: 0;
  padding: var(--app-space-md);
  border-left: 1px solid var(--app-border);
  background: var(--app-surface-muted);
}
.trace-legend__heading,
.trace-legend__item {
  display: grid;
  grid-template-columns: 9px minmax(0, 1fr) auto 42px;
  align-items: center;
  gap: 7px;
}
.trace-legend__heading {
  grid-template-columns: 9px minmax(0, 1fr) auto 42px;
  min-height: 26px;
  color: var(--app-text-muted);
  font-size: 10px;
}
.trace-legend__heading strong {
  grid-column: 2;
}
.trace-legend__heading span {
  grid-column: 4;
  text-align: right;
}
.trace-legend__item {
  min-height: 39px;
  border-top: 1px solid var(--app-border);
  font-size: 10px;
}
.trace-legend__dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  background: var(--app-primary);
}
.trace-legend__dot--tone-1 {
  background: var(--app-info);
}
.trace-legend__dot--tone-2 {
  background: var(--app-accent);
}
.trace-legend__dot--tone-3 {
  background: var(--app-positive);
}
.trace-legend__dot--tone-4 {
  background: var(--app-warning);
}
.trace-legend__dot--failed {
  background: var(--app-negative);
}
.trace-legend__name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.trace-legend__name small {
  display: block;
  margin-top: 2px;
  color: var(--app-text-muted);
  font-size: 9px;
}
.trace-legend__percent {
  color: var(--app-text-muted);
  text-align: right;
}
.trace-legend__footnote {
  margin-top: var(--app-space-md);
  color: var(--app-text-muted);
  font-size: 9px;
  line-height: 1.45;
}
.trace-spans {
  padding: var(--app-space-sm) var(--app-space-md);
}
.trace-spans__table {
  background: transparent;
}
.trace-spans__table :deep(tbody tr) {
  cursor: pointer;
}
.trace-spans__table :deep(tbody tr:hover) {
  background: var(--app-surface-muted);
}
.trace-spans__selected {
  color: var(--app-primary);
  font-weight: 650;
}
.span-detail {
  padding: 0;
}
.inspector-section__toggle {
  width: 100%;
  box-sizing: border-box;
  padding: 12px 14px;
  color: inherit;
  font: inherit;
  text-align: left;
  background: transparent;
  border: 0;
  cursor: pointer;
}
.inspector-section__icon {
  flex: none;
  color: var(--app-text-muted);
  transition: transform 160ms ease;
}
.inspector-section__icon--open {
  transform: rotate(180deg);
}
.span-detail__header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid var(--app-border);
}
.span-detail__header > div {
  min-width: 0;
}
.span-detail__header h2 {
  margin: 3px 0 0;
  overflow: hidden;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.eyebrow {
  color: var(--app-text-muted);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.span-detail__facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  padding: 14px 14px 12px;
}
.span-detail__facts div {
  display: grid;
  align-content: start;
  gap: 4px;
  min-width: 0;
}
.span-detail__facts span {
  color: var(--app-text-muted);
  font-size: 10px;
}
.span-detail__facts strong {
  overflow-wrap: anywhere;
  font-size: 11px;
  font-weight: 600;
}
.span-detail__error {
  padding: 0 14px 14px;
  color: var(--app-negative);
  font-size: 11px;
}
.request-events {
  padding: 0;
  overflow: hidden;
}
.request-events__header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid var(--app-border);
}
.request-events__header > div {
  min-width: 0;
}
.request-events__header h2 {
  margin: 0;
  font-size: 12px;
}
.request-events__header p {
  margin: 3px 0 0;
  overflow: hidden;
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.request-events__item {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-items: start;
  gap: var(--app-space-sm);
  padding: var(--app-space-md);
}
.request-events__time {
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--app-text-muted);
  font-size: 10px;
  white-space: nowrap;
}
.request-events__body strong {
  font-size: 12px;
}
.request-events__body p {
  margin: 5px 0 0;
  font-size: 11px;
}
.request-events__empty {
  display: flex;
  align-items: center;
  gap: var(--app-space-sm);
  padding: var(--app-space-md);
  color: var(--app-text-muted);
  font-size: 11px;
}
.timing-detail {
  padding: 0;
}
.timing-detail__header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid var(--app-border);
}
.timing-detail__header > div {
  min-width: 0;
}
.timing-detail__header h2 {
  margin: 3px 0 0;
  font-size: 13px;
}
.timing-detail__header > strong {
  font-size: 13px;
}
.timing-detail__header .inspector-section__icon {
  margin-left: 0;
}
#trace-timing-content {
  padding: 14px;
}
.timing-detail__row {
  display: flex;
  justify-content: space-between;
  gap: var(--app-space-sm);
  margin-bottom: 5px;
  font-size: 10px;
}
.timing-detail__row span {
  color: var(--app-text-muted);
}
.timing-detail__row small {
  display: block;
  font-size: 9px;
}
.timing-detail__slowest {
  display: grid;
  gap: 3px;
  padding-top: var(--app-space-sm);
  margin-top: var(--app-space-sm);
  border-top: 1px solid var(--app-border);
  font-size: 10px;
}
.timing-detail__slowest span,
.timing-detail__slowest small {
  color: var(--app-text-muted);
}
.timing-detail__slowest strong {
  overflow-wrap: anywhere;
  font-size: 11px;
}
.timing-detail__note {
  margin: var(--app-space-sm) 0 0;
  color: var(--app-text-muted);
  font-size: 9px;
  line-height: 1.4;
}
.trace-exception {
  width: min(760px, calc(100vw - 32px));
  max-height: calc(100vh - 32px);
  overflow: auto;
  border-radius: var(--app-radius-lg);
}
.trace-exception__trace {
  max-height: 360px;
  overflow: auto;
  padding: var(--app-space-md);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  background: var(--app-surface-muted);
  font-size: 11px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
@media (max-width: 1050px) {
  .trace-workspace {
    grid-template-columns: minmax(0, 1fr);
  }
  .trace-workspace__inspector {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: start;
  }
  .request-events {
    grid-column: 1 / -1;
  }
  .request-head {
    align-items: flex-start;
    flex-direction: column;
  }
  .request-head__facts {
    width: 100%;
    justify-content: space-between;
  }
  .trace-layout {
    grid-template-columns: minmax(0, 1fr);
  }
  .trace-legend {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0 var(--app-space-md);
    border-top: 1px solid var(--app-border);
    border-left: 0;
  }
  .trace-legend__heading,
  .trace-legend__footnote {
    grid-column: 1 / -1;
  }
  .span-detail__facts {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 650px) {
  .trace-drawer {
    width: 100vw;
    border-radius: 0;
  }
  .trace-drawer__body {
    padding: var(--app-space-md);
  }
  .trace-workspace__inspector {
    grid-template-columns: minmax(0, 1fr);
  }
  .request-events {
    grid-column: auto;
  }
  .request-head__facts {
    flex-wrap: wrap;
    justify-content: flex-start;
  }
  .request-head__facts > div {
    padding-left: 8px;
  }
  .trace-panel__header {
    align-items: flex-start;
    flex-direction: column;
  }
  .trace-waterfall__ruler,
  .trace-row {
    grid-template-columns: minmax(110px, 38%) minmax(0, 1fr);
  }
  .trace-row__name {
    font-size: 9px;
  }
  .trace-waterfall__axis span {
    font-size: 8px;
  }
  .trace-legend {
    grid-template-columns: 1fr;
  }
  .trace-legend__heading,
  .trace-legend__footnote {
    grid-column: auto;
  }
  .span-detail__facts {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .request-events__item {
    grid-template-columns: 1fr;
  }
}
</style>
