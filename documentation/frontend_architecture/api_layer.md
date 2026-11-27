# API Layer (`src/api`)

## `http` (api/http.js)

The single axios instance. Base URL `QCLI_API_BASE_URL` (default `/api/v1`), `withCredentials: true`, 15 s timeout.

| Behaviour | Detail |
|---|---|
| Auth header | `Authorization: Bearer <token>` from the auth store |
| Expired token | On 401 `token_expired` / `invalid_token` / `not_authenticated`: refresh once, retry once |
| One refresh at a time | Parallel 401s share one refresh. A Web Lock (`app-auth-refresh`) makes other tabs wait, so a refresh token is never reused (reuse would end the session) |
| Session over | Refresh fails → auth store cleared → redirect to `/login?redirect=…` |
| Errors | Every rejection is an `ApiError` |

Per-request options: `skipAuth` (no token), `skipAuthRefresh` (no refresh + retry). Login, refresh and logout use both.

## `ApiError` (api/errors.js)

| Field | From |
|---|---|
| `status` | HTTP status (`0` = no response) |
| `code` | `error.code` (`network_error`, `timeout` when no response) |
| `message` | `error.message` |
| `details` | `error.details` |
| `requestId` | `metadata.request_id` / `X-Request-ID` |
| `retryAfter` | `Retry-After` on 429 |
| `fieldErrors` | 422 details as `{field: message}` |

## `createResource(path)` (api/crud.js)

For backend resources that follow the standard pattern:

```js
// module/users/api.js
import { createResource, http } from '@/api'
export const usersApi = {
  ...createResource('/users'),
  setRoles: (id, roles) => http.put(`/users/${id}/roles`, { roles }).then((r) => r.data.record),
}
```

| Method | Call | Returns |
|---|---|---|
| `list({limit, offset})` | `GET /path` | `{metadata, records}` |
| `search(body)` | `POST /path/search` | `{metadata, records}` |
| `get(id)` | `GET /path/{id}` | record |
| `create(body)` | `POST /path` | record |
| `update(id, body)` | `PATCH /path/{id}` | record |
| `remove(id)` | `DELETE /path/{id}` | — |

## Environment (`frontend/.env`)

| Variable | Default | Use |
|---|---|---|
| `QCLI_APP_NAME` | `Baseframe` | Shell, login, tab title |
| `QCLI_API_BASE_URL` | `/api/v1` | API base (same origin) |
| `QCLI_API_PROXY_TARGET` | `http://localhost:8000` | Dev proxy target (`quasar.config.js`) |
