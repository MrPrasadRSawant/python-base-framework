<template>
  <div class="app-table app-card">
    <div class="app-table__toolbar row items-center q-gutter-sm">
      <q-input
        v-if="searchable"
        v-model="searchText"
        dense
        outlined
        clearable
        debounce="350"
        :placeholder="searchPlaceholder"
        class="app-table__search"
      >
        <template #prepend><q-icon name="search" /></template>
      </q-input>
      <slot name="toolbar" />
      <q-space />
      <q-btn flat round dense icon="refresh" :loading="loading" @click="reload">
        <q-tooltip>Refresh</q-tooltip>
      </q-btn>
    </div>

    <q-banner v-if="error" dense class="bg-negative text-white">
      <template #avatar><q-icon name="error_outline" /></template>
      {{ error.message }}
      <template #action>
        <q-btn flat dense no-caps color="white" label="Retry" @click="reload" />
      </template>
    </q-banner>

    <q-table
      v-model:pagination="pagination"
      flat
      binary-state-sort
      :rows="rows"
      :columns="columns"
      :row-key="rowKey"
      :loading="loading"
      :rows-per-page-options="[10, 20, 50, 100]"
      class="app-table__table"
      @request="onRequest"
      @row-click="(evt, row) => emit('row-click', row)"
    >
      <template v-for="name in tableSlots" #[name]="slotProps" :key="name">
        <slot :name="name" v-bind="slotProps || {}" />
      </template>
      <template v-if="!$slots['no-data']" #no-data>
        <AppEmptyState :icon="emptyIcon" :title="emptyTitle" :message="emptyMessage" />
      </template>
    </q-table>
  </div>
</template>

<script setup>
/**
 * Server-side table for any backend resource with POST /<resource>/search:
 * paging, sorting and text search are done by the API.
 *
 *   <AppTable ref="table" :resource="usersApi" :columns="columns"
 *     search-placeholder="Search name or email"
 *     :filters="[{ field: 'is_active', value: true }]">
 *     <template #body-cell-is_active="props">
 *       <q-td :props="props"><AppStatusChip :status="props.value ? 'active' : 'disabled'" /></q-td>
 *     </template>
 *   </AppTable>
 *   table.value.reload()   // after a create / update / delete
 *
 * Columns are QTable columns. `sortable: true` columns sort on the backend by
 * `column.sortField` (default: `column.name`), which must be in the resource's
 * sort fields (see its Swagger search endpoint). Every q-table slot passes through.
 */
import { computed, onMounted, ref, useSlots, watch } from 'vue'

import AppEmptyState from './AppEmptyState.vue'

const props = defineProps({
  resource: { type: Object, required: true }, // createResource(...) or {search(body)}
  columns: { type: Array, required: true },
  rowKey: { type: String, default: 'id' },
  filters: { type: Array, default: () => [] }, // SearchRequest filters, always applied
  searchable: { type: Boolean, default: true },
  searchPlaceholder: { type: String, default: 'Search' },
  pageSize: { type: Number, default: 20 },
  sortBy: { type: String, default: null }, // initial sort column name
  descending: { type: Boolean, default: true },
  emptyIcon: { type: String, default: 'inbox' },
  emptyTitle: { type: String, default: 'No records found' },
  emptyMessage: { type: String, default: '' },
})
const emit = defineEmits(['row-click', 'loaded'])
const slots = useSlots()

const rows = ref([])
const loading = ref(false)
const error = ref(null)
const searchText = ref('')
const pagination = ref({
  page: 1,
  rowsPerPage: props.pageSize,
  sortBy: props.sortBy,
  descending: props.descending,
  rowsNumber: 0,
})

const tableSlots = computed(() => Object.keys(slots).filter((name) => name !== 'toolbar'))

function sortFieldOf(columnName) {
  const column = props.columns.find((c) => c.name === columnName)
  return column?.sortField || columnName
}

let requestSeq = 0

async function onRequest({ pagination: next }) {
  const { page, rowsPerPage, sortBy, descending } = next
  const seq = ++requestSeq
  loading.value = true
  error.value = null
  try {
    const data = await props.resource.search({
      search: searchText.value?.trim() || null,
      filters: props.filters,
      sort: sortBy ? [{ field: sortFieldOf(sortBy), direction: descending ? 'desc' : 'asc' }] : [],
      limit: rowsPerPage,
      offset: (page - 1) * rowsPerPage,
      include_total: true,
    })
    if (seq !== requestSeq) return // a newer request is on its way
    rows.value = data.records
    pagination.value = { ...next, rowsNumber: data.metadata.total_count ?? data.records.length }
    emit('loaded', data)
  } catch (err) {
    if (seq === requestSeq) error.value = err
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

function reload({ resetPage = false } = {}) {
  const next = resetPage ? { ...pagination.value, page: 1 } : pagination.value
  return onRequest({ pagination: next })
}

watch(searchText, () => reload({ resetPage: true }))
watch(
  () => JSON.stringify(props.filters),
  () => reload({ resetPage: true }),
)
onMounted(() => reload())

defineExpose({ reload })
</script>

<style scoped lang="scss">
.app-table {
  overflow: hidden;
}
.app-table__toolbar {
  padding: var(--app-space-md);
  border-bottom: 1px solid var(--app-border);
}
.app-table__search {
  width: 320px;
  max-width: 100%;
}
.app-table__table {
  background: transparent;

  :deep(thead tr th) {
    background: var(--app-surface-muted);
    color: var(--app-text-muted);
    font-weight: 600;
  }
}
</style>
