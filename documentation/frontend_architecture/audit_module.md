# Audit module

`src/module/audit` contributes the **User Activity** page (`/audit/activity`, route name
`user-activity`) under the **Security & audit** menu group. The route and menu entry
require `user_activity_logs:read` (held by `admin`), exported as `ACTIVITY_PERMISSION`.
The backend enforces it on every call.

| File | Role |
|---|---|
| `index.js` | route, menu entry, `ACTIVITY_PERMISSION` |
| `api.js` | `activityApi` (`createResource('/user-activity-logs')`), `usernamesFor()` |
| `activity.js` | pure display rules: action labels and icons, quick and URL filters, actor and record labels, before/after rows |
| `filters.js` | advanced filter fields (action, status, actor type/id, record type/id, IP, route, date) |
| `pages/UserActivityPage.vue` | quick filter, table, context banner |
| `components/ActivityDetailDialog.vue` | one row: facts, Field / Before / After table, details, investigation links |

## Page

- **Quick filter**: All activity, Data changes, and Sign-ins sit beside the page title;
  Refused (`status = failed`) is in the three-dot menu.
- **Table**: `AppTable` over `POST /user-activity-logs/search`, with quick search and the shared
  `AppAdvancedFiltersDialog`. Action, status, and actor type use controlled choices. Columns: When,
  Who, Action, Record, IP address, Status (`AppStatusChip`). Table and summary errors use the app's
  toast notification; table errors also offer Retry in the table.
- **Who**: user ids are resolved to usernames through `POST /users/search` (deleted users included)
  when the viewer has `users:read`; otherwise the short id is shown.
- **Row click** opens the detail dialog with event, actor, record, request and network details,
  responsive before/after change cards, and **Record history**, **All by this actor**, and
  **Open request lifecycle** (with `request_logs:read`, via `?requestId=`).
- **Feature off**: if the API returns 404 (`ENABLE_USER_ACTIVITY_LOG=false`), the page shows an
  empty state explaining the switch.

## Deep links

Other modules link through the route name and query only, never through the module's files:

```js
router.push({ name: 'user-activity', query: { entityType: 'users', entityId: user.id } })
router.push({ name: 'user-activity', query: { actorId: userId } })
```

The page turns the query into filters and shows a banner with **Show all activity** to clear it.
The Users page has a **History** row button and the Roles page an **Activity history** menu item,
both shown only with `user_activity_logs:read`.

## Tests

`src/module/audit/__tests__/activity.test.js` covers quick, URL and advanced filters, labels,
value formatting, redacted values and event details.
