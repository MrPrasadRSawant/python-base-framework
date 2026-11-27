<template>
  <q-dialog :model-value="modelValue" @update:model-value="emit('update:modelValue', $event)">
    <q-card class="advanced-filters">
      <div class="advanced-filters__heading">
        <div class="advanced-filters__identity">
          <div class="advanced-filters__icon" aria-hidden="true">
            <q-icon name="tune" size="22px" />
          </div>
          <div>
            <h2>{{ title }}</h2>
            <p>{{ description }}</p>
          </div>
        </div>
        <div class="advanced-filters__heading-actions">
          <span class="advanced-filters__match">Match all</span>
          <q-btn flat round dense icon="close" aria-label="Close advanced filters" @click="close" />
        </div>
      </div>

      <div v-if="error" class="advanced-filters__error" role="alert">
        <q-icon name="error_outline" size="18px" />
        {{ error }}
      </div>

      <div class="advanced-filters__body">
        <div class="advanced-filters__section-heading">
          <span>Conditions</span>
          <span class="advanced-filters__count"
            >{{ conditionsDraft.length }} of {{ MAX_FILTER_CONDITIONS }}</span
          >
        </div>

        <div v-if="conditionsDraft.length" class="advanced-filters__rules">
          <div
            v-for="(condition, index) in conditionsDraft"
            :key="condition.id"
            class="advanced-filters__rule"
            role="group"
            :aria-label="`Condition ${index + 1}`"
          >
            <div class="advanced-filters__rule-heading">
              <span class="advanced-filters__number">{{ String(index + 1).padStart(2, '0') }}</span>
              <span class="advanced-filters__rule-title">Condition {{ index + 1 }}</span>
              <q-btn
                flat
                round
                dense
                icon="delete_outline"
                :aria-label="`Remove condition ${index + 1}`"
                @click="removeCondition(index)"
              >
                <q-tooltip>Remove condition</q-tooltip>
              </q-btn>
            </div>
            <div class="advanced-filters__fields">
              <q-select
                v-model="condition.field"
                dense
                outlined
                emit-value
                map-options
                :options="fields"
                label="Field"
                @update:model-value="resetCondition(condition)"
              />
              <q-select
                v-model="condition.op"
                dense
                outlined
                emit-value
                map-options
                :options="operatorsFor(condition.field, fields)"
                label="Condition"
              />
              <q-select
                v-if="fieldType(condition.field) === 'boolean'"
                v-model="condition.value"
                dense
                outlined
                emit-value
                map-options
                :options="fieldFor(condition.field)?.options || []"
                label="Value"
              />
              <q-input
                v-else-if="condition.op !== 'is_null' && condition.op !== 'is_not_null'"
                v-model="condition.value"
                dense
                outlined
                :type="isDateField(condition.field) ? 'date' : 'text'"
                :label="isDateField(condition.field) ? 'Date' : 'Value'"
                maxlength="255"
                @keyup.enter="apply"
              />
              <div v-else class="advanced-filters__no-value">
                <q-icon name="check_circle_outline" size="18px" />
                No value needed
              </div>
            </div>
          </div>
        </div>
        <div v-else class="advanced-filters__empty">
          <q-icon name="filter_alt_off" size="20px" />
          <span>No conditions yet. Add one to refine the list.</span>
        </div>

        <q-btn
          outline
          no-caps
          color="primary"
          icon="add"
          label="Add condition"
          class="advanced-filters__add"
          :disable="conditionsDraft.length >= MAX_FILTER_CONDITIONS"
          @click="addCondition"
        />
      </div>

      <div class="advanced-filters__footer">
        <span class="advanced-filters__footer-note"
          >Changes take effect when you apply filters.</span
        >
        <div class="advanced-filters__actions">
          <q-btn
            flat
            no-caps
            label="Clear filters"
            :disable="!conditionsDraft.length && !appliedCount"
            @click="clear"
          />
          <q-btn flat no-caps label="Cancel" @click="close" />
          <q-btn color="primary" unelevated no-caps label="Apply filters" @click="apply" />
        </div>
      </div>
    </q-card>
  </q-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'

import { MAX_FILTER_CONDITIONS, newCondition, operatorsFor } from './advancedFilters.js'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: 'Advanced filters' },
  description: { type: String, default: 'Show records that match every condition below.' },
  fields: { type: Array, required: true },
  buildFilters: { type: Function, required: true },
  conditions: { type: Array, default: () => [] },
  appliedCount: { type: Number, default: 0 },
})
const emit = defineEmits(['update:modelValue', 'apply'])

let nextId = 0
const conditionsDraft = ref([])
const error = ref('')

watch(
  () => props.modelValue,
  (isOpen) => {
    if (!isOpen) return
    conditionsDraft.value = (
      props.conditions.length ? props.conditions : [newCondition(props.fields)]
    ).map((item) => ({ ...item, id: ++nextId }))
    error.value = ''
  },
  { immediate: true },
)

function close() {
  emit('update:modelValue', false)
}

function fieldFor(fieldName) {
  return props.fields.find((item) => item.value === fieldName)
}

function fieldType(fieldName) {
  return fieldFor(fieldName)?.type
}

function isDateField(fieldName) {
  return ['date', 'nullable-date'].includes(fieldType(fieldName))
}

function resetCondition(condition) {
  condition.op = operatorsFor(condition.field, props.fields)[0].value
  condition.value =
    fieldType(condition.field) === 'boolean' ? fieldFor(condition.field).options[0].value : ''
  error.value = ''
}

function addCondition() {
  conditionsDraft.value.push({ ...newCondition(props.fields), id: ++nextId })
  error.value = ''
}

function removeCondition(index) {
  conditionsDraft.value.splice(index, 1)
  error.value = ''
}

function apply() {
  try {
    props.buildFilters(conditionsDraft.value)
    emit(
      'apply',
      conditionsDraft.value.map(({ field, op, value }) => ({ field, op, value })),
    )
    error.value = ''
  } catch (cause) {
    error.value = cause.message
  }
}

function clear() {
  conditionsDraft.value = []
  error.value = ''
  emit('apply', [])
}
</script>

<style scoped lang="scss">
.advanced-filters {
  display: flex;
  flex-direction: column;
  width: 860px;
  max-width: calc(100vw - 32px);
  max-height: min(780px, calc(100vh - 32px));
  border-radius: var(--app-radius-lg);
  background: var(--app-surface-muted);
}

.advanced-filters__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--app-space-md);
  flex: none;
  padding: var(--app-space-md) var(--app-space-lg);
  border-bottom: 1px solid var(--app-border);
  background: var(--app-surface);
}

.advanced-filters__identity,
.advanced-filters__heading-actions,
.advanced-filters__rule-heading,
.advanced-filters__actions {
  display: flex;
  align-items: center;
  gap: var(--app-space-sm);
}

.advanced-filters__icon {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  flex: none;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  background: var(--app-surface);
  color: var(--app-primary);
}

.advanced-filters h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.35;
}

.advanced-filters p {
  margin: 2px 0 0;
  color: var(--app-text-muted);
  font-size: 13px;
}

.advanced-filters__match,
.advanced-filters__count {
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
  color: var(--app-text-muted);
  padding: 4px var(--app-space-sm);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.advanced-filters__body {
  min-height: 0;
  overflow-y: auto;
  padding: var(--app-space-md) var(--app-space-lg) var(--app-space-lg);
}

.advanced-filters__section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--app-space-sm);
  font-size: 13px;
  font-weight: 700;
}

.advanced-filters__rules {
  display: grid;
  gap: var(--app-space-sm);
}

.advanced-filters__rule {
  padding: var(--app-space-md);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  background: var(--app-surface);
}

.advanced-filters__rule-heading {
  margin-bottom: var(--app-space-sm);
  color: var(--app-text-muted);
}

.advanced-filters__rule-heading .q-btn {
  margin-left: auto;
}

.advanced-filters__number {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border-radius: var(--app-radius-sm);
  background: var(--app-surface-muted);
  color: var(--app-primary);
  font-size: 12px;
  font-weight: 700;
}

.advanced-filters__rule-title {
  font-size: 12px;
  font-weight: 600;
}

.advanced-filters__fields {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1.25fr);
  gap: var(--app-space-md);
}

.advanced-filters__fields > * {
  min-width: 0;
}

.advanced-filters__no-value,
.advanced-filters__empty {
  display: flex;
  align-items: center;
  gap: var(--app-space-sm);
  color: var(--app-text-muted);
  font-size: 13px;
}

.advanced-filters__no-value {
  min-height: 40px;
  padding: 0 var(--app-space-md);
  border: 1px dashed var(--app-border);
  border-radius: var(--app-radius-sm);
}

.advanced-filters__empty {
  padding: var(--app-space-md);
  border: 1px dashed var(--app-border);
  border-radius: var(--app-radius-md);
  background: var(--app-surface);
}

.advanced-filters__add {
  margin-top: var(--app-space-md);
}

.advanced-filters__error {
  display: flex;
  align-items: center;
  gap: var(--app-space-sm);
  flex: none;
  padding: var(--app-space-sm) var(--app-space-lg);
  border-bottom: 1px solid var(--app-border);
  color: var(--app-negative);
  font-size: 13px;
}

.advanced-filters__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--app-space-md);
  flex-wrap: wrap;
  flex: none;
  padding: var(--app-space-md) var(--app-space-lg);
  border-top: 1px solid var(--app-border);
  background: var(--app-surface);
}

.advanced-filters__footer-note {
  color: var(--app-text-muted);
  font-size: 12px;
}

@media (max-width: 680px) {
  .advanced-filters__heading,
  .advanced-filters__body,
  .advanced-filters__footer {
    padding-right: var(--app-space-md);
    padding-left: var(--app-space-md);
  }

  .advanced-filters__match,
  .advanced-filters__footer-note {
    display: none;
  }

  .advanced-filters__fields {
    grid-template-columns: minmax(0, 1fr);
    gap: var(--app-space-sm);
  }

  .advanced-filters__actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
