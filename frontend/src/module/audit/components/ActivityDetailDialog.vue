<template>
  <q-dialog :model-value="modelValue" @update:model-value="emit('update:modelValue', $event)">
    <q-card class="activity-detail">
      <q-card-section class="activity-detail__header">
        <div class="activity-detail__icon" aria-hidden="true">
          <q-icon :name="look.icon" size="22px" />
        </div>
        <div class="activity-detail__title">
          <div class="text-h6">{{ look.label }}</div>
          <div v-if="row" class="text-caption text-app-muted">
            {{ formatDateTime(row.occurred_on) }}
          </div>
        </div>
        <AppStatusChip v-if="row" :status="row.status === 'failed' ? 'failed' : 'success'" />
        <q-btn flat round dense icon="close" aria-label="Close" @click="close" />
      </q-card-section>
      <q-separator />

      <q-card-section v-if="row" class="activity-detail__body">
        <h3 class="activity-detail__heading">Event information</h3>
        <div class="activity-detail__facts">
          <div>
            <small>Actor</small>
            <strong>{{ actorLabel(row, names) }}</strong>
            <code v-if="row.actor_id">{{ row.actor }}</code>
          </div>
          <div>
            <small>Record</small>
            <strong>{{ row.entity_type ? entityLabel(row.entity_type) : '—' }}</strong>
            <code v-if="row.entity_id">{{ row.entity_id }}</code>
          </div>
          <div>
            <small>Request route</small>
            <strong>{{ [row.method, row.route].filter(Boolean).join(' ') || '—' }}</strong>
          </div>
          <div>
            <small>IP address</small><strong>{{ row.ip_address || '—' }}</strong>
          </div>
          <div>
            <small>User agent</small>
            <strong class="activity-detail__agent">{{ row.user_agent || '—' }}</strong>
          </div>
          <div v-if="row.request_id">
            <small>Request ID</small>
            <code>{{ row.request_id }}</code>
          </div>
          <div>
            <small>Activity ID</small>
            <code>{{ row.id }}</code>
          </div>
        </div>

        <section v-if="changes.length" class="activity-detail__section">
          <h3 class="activity-detail__heading">Changes</h3>
          <div class="activity-detail__changes">
            <div v-for="change in changes" :key="change.field" class="activity-detail__change">
              <div class="activity-detail__field">
                {{ change.label }}
                <q-icon v-if="change.sensitive" name="lock" size="14px" class="q-ml-xs">
                  <q-tooltip>Sensitive value: only the fact that it changed is kept</q-tooltip>
                </q-icon>
              </div>
              <div class="activity-detail__values">
                <div>
                  <small>Before</small><span>{{ change.before }}</span>
                </div>
                <q-icon name="arrow_forward" size="16px" class="activity-detail__arrow" />
                <div>
                  <small>After</small><span>{{ change.after }}</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section v-if="details.length" class="activity-detail__section">
          <h3 class="activity-detail__heading">Details</h3>
          <div class="activity-detail__facts">
            <div v-for="item in details" :key="item.label">
              <small>{{ item.label }}</small><strong>{{ item.value }}</strong>
            </div>
          </div>
        </section>

        <div
          v-if="row.entity_id || row.actor_id || (row.request_id && canOpenRequest)"
          class="activity-detail__section"
        >
          <h3 class="activity-detail__heading">Investigate</h3>
          <div class="activity-detail__links">
            <q-btn
              v-if="row.entity_type && row.entity_id"
              outline
              no-caps
              color="primary"
              icon="history"
              label="Record history"
              @click="emit('record-history', row)"
            />
            <q-btn
              v-if="row.actor_id"
              outline
              no-caps
              color="primary"
              icon="person_search"
              label="All by this actor"
              @click="emit('actor-activity', row)"
            />
            <q-btn
              v-if="row.request_id && canOpenRequest"
              flat
              no-caps
              color="primary"
              icon="timeline"
              label="Open request lifecycle"
              @click="emit('open-request', row)"
            />
          </div>
        </div>
      </q-card-section>
    </q-card>
  </q-dialog>
</template>

<script setup>
/**
 * One activity row in full: who, from where, the before/after values of a data
 * change or the reason of a security event, and links to investigate further.
 */
import { computed } from 'vue'

import AppStatusChip from '@/components/AppStatusChip.vue'

import {
  actionLook,
  actorLabel,
  changeRows,
  detailRows,
  entityLabel,
  formatDateTime,
} from '../activity.js'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  row: { type: Object, default: null },
  names: { type: Object, default: () => ({}) }, // user id -> username
  canOpenRequest: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'record-history', 'actor-activity', 'open-request'])

const look = computed(() => actionLook(props.row?.action))
const changes = computed(() => changeRows(props.row?.changes))
const details = computed(() => detailRows(props.row?.details))

function close() {
  emit('update:modelValue', false)
}
</script>

<style scoped lang="scss">
.activity-detail {
  width: min(780px, calc(100vw - 32px));
  max-height: calc(100vh - 32px);
  overflow: auto;
  border-radius: var(--app-radius-lg);
}
.activity-detail__header {
  display: flex;
  align-items: flex-start;
  gap: var(--app-space-md);
}
.activity-detail__title {
  flex: 1;
  min-width: 0;
}
.activity-detail__title .text-h6 {
  line-height: 1.3;
}
.activity-detail__header :deep(.q-chip) {
  margin: 4px 0 0;
}
.activity-detail__icon {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: var(--app-radius-md);
  background: var(--app-surface-muted);
  color: var(--app-primary);
  flex: none;
}
.activity-detail__body {
  padding: var(--app-space-lg);
}
.activity-detail__section {
  margin-top: var(--app-space-lg);
  padding-top: var(--app-space-lg);
  border-top: 1px solid var(--app-border);
}
.activity-detail__facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--app-space-md);
}
.activity-detail__facts div {
  display: grid;
  gap: 4px;
  min-width: 0;
  align-content: start;
}
.activity-detail__facts small {
  color: var(--app-text-muted);
}
.activity-detail__facts strong,
.activity-detail__facts code {
  overflow-wrap: anywhere;
  font-size: 13px;
}
.activity-detail__facts code {
  color: var(--app-text-muted);
  font-size: 11px;
}
.activity-detail__agent {
  font-weight: 400;
}
.activity-detail__heading {
  margin: 0 0 var(--app-space-md);
  font-size: 14px;
  font-weight: 600;
}
.activity-detail__changes {
  display: grid;
  gap: var(--app-space-sm);
}
.activity-detail__change {
  padding: var(--app-space-md);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  background: var(--app-surface-muted);
}
.activity-detail__field {
  margin-bottom: var(--app-space-sm);
  font-size: 13px;
  font-weight: 600;
}
.activity-detail__values {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 16px minmax(0, 1fr);
  align-items: center;
  gap: var(--app-space-md);
}
.activity-detail__values > div {
  display: grid;
  gap: 4px;
  min-width: 0;
  overflow-wrap: anywhere;
  font-size: 13px;
}
.activity-detail__values small {
  color: var(--app-text-muted);
}
.activity-detail__arrow {
  color: var(--app-text-muted);
}
.activity-detail__links {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-sm);
}
@media (max-width: 600px) {
  .activity-detail {
    width: calc(100vw - 16px);
    max-height: calc(100dvh - 16px);
  }
  .activity-detail__header,
  .activity-detail__body {
    padding: var(--app-space-md);
  }
  .activity-detail__header {
    flex-wrap: wrap;
    gap: var(--app-space-sm);
  }
  .activity-detail__header :deep(.q-chip) {
    order: 3;
  }
  .activity-detail__facts {
    grid-template-columns: 1fr;
  }
  .activity-detail__values {
    grid-template-columns: 1fr;
    gap: var(--app-space-xs);
  }
  .activity-detail__arrow {
    transform: rotate(90deg);
  }
  .activity-detail__links .q-btn {
    width: 100%;
  }
}
</style>
