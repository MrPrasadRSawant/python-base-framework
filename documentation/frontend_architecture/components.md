# Generic Components (`src/components`)

Shared, business-free building blocks. Styled only with tokens.

| Component | Use | Key props / events |
|---|---|---|
| `BrandLogo` | Shared product mark and name | `compact`, `inverse` |
| `AppPageHeader` | Title bar of every page | `title`, `subtitle`, `breadcrumbs`; slot `actions` |
| `AppTable` | Server-side table for any resource with `/search` | `resource`, `columns`, `filters`, `searchable`, `sortBy`, `descending`, `pageSize`; `@row-click`; `reload()`; all `q-table` slots |
| `AppFormDialog` | Create / edit forms | `v-model`, `title`, `loading`, `error`, `submitLabel`, `width`; `@submit` (after field rules pass) |
| `AppConfirmDialog` | Yes/no confirmation | `v-model`, `title`, `message`, `confirmLabel`, `danger`, `loading`; `@confirm` |
| `AppStatusChip` | Status badge | `status`: `active` `disabled` `system` `success` `failed` `warning` `expired`; `label` |
| `AppEmptyState` | Empty / no-access / not-found | `icon`, `title`, `message`; default slot for actions |

Composable: `useNotify()` → `success(msg)`, `info(msg)`, `error(errOrMsg)` (an `ApiError` shows its message and request id).

## AppTable

- **Paging, sort and search** run on the backend: `{search, filters, sort, limit, offset, include_total}` is sent to `resource.search()`.
- **Sortable columns** sort by `column.sortField` (default `column.name`). The field must be in the resource's sort fields, which Swagger lists on its search endpoint.
- Changing `filters` or the search text resets to page 1. Out-of-order responses are ignored.

```vue
<AppTable ref="table" :resource="usersApi" :columns="columns" search-placeholder="Search name or email">
  <template #body-cell-is_active="props">
    <q-td :props="props"><AppStatusChip :status="props.value ? 'active' : 'disabled'" /></q-td>
  </template>
</AppTable>
```

## Page skeleton

```vue
<q-page class="app-page">
  <AppPageHeader title="Users" subtitle="Accounts and access">
    <template #actions><q-btn v-if="can('users:manage')" color="primary" unelevated no-caps label="Add user" /></template>
  </AppPageHeader>
  <AppTable ... />
</q-page>
```
