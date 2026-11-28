# Data model: `user_activity_logs`

Append-only. Migration `16_7c3e9a1f5b2d` (also inserts the `user_activity_logs:read`
permission and grants it to `admin`).

| Column | Type | Example / notes |
|---|---|---|
| `id` | uuid PK | |
| `occurred_on` | timestamptz, indexed | when it happened (UTC) |
| `actor` | varchar(255) | `user:<id>`, `service:<client_id>`, `system`, `anonymous` |
| `actor_type` | varchar(16), indexed | `user` / `service` / `system` / `anonymous` (in a request without a valid token) |
| `actor_id` | varchar(64) | `users.id` or the API client's `client_id`; null for system/anonymous |
| `action` | varchar(32), indexed | see below |
| `status` | varchar(16), indexed | `success`, or `failed` for refused attempts |
| `entity_type` | varchar(64) | table name: `users`, `roles`, `user_roles`, ... |
| `entity_id` | varchar(64) | the record's primary key |
| `changes` | jsonb | `{"full_name": {"old": "Dana", "new": "Dana S"}}`; sensitive values `[REDACTED]` |
| `details` | jsonb | `{"reason": "wrong_password", "locked_out": false}`, `{"missing_permissions": [...]}` |
| `request_id` | uuid, indexed | joins `requests.id`, `exception_log.request_id`, `service_call_logs.request_id` |
| `method` / `route` | varchar | `PATCH` `/api/v1/users/{user_id}` (route template, never the real URL) |
| `ip_address` | varchar(64), indexed | first `X-Forwarded-For` hop, else the socket peer |
| `user_agent` | varchar(512) | |
| common columns | | `created_by` (= actor), `created_on`, `updated_by`, `updated_on`, `is_deleted` |

Composite indexes: `(entity_type, entity_id, occurred_on)` for record history,
`(actor_id, occurred_on)` for "what did this user do".

## Actions

| Action | Status | `changes` / `details` |
|---|---|---|
| `create` | success | every non-null field as `{old: null, new}` |
| `update` | success | changed fields only `{old, new}` |
| `delete` | success | hard delete: all fields `{old, new: null}`; soft delete: `{is_deleted: {old: false, new: true}}` |
| `restore` | success | `{is_deleted: {old: true, new: false}}` |
| `login` | success | |
| `login_failed` | failed | `reason`: `unknown_account`, `wrong_password` (+ `locked_out`), `account_locked`, `account_disabled` |
| `logout` | success | |
| `token_issued` | success | API client got a token |
| `client_auth_failed` | failed | `reason`: `missing_credentials`, `unknown_client`, `wrong_secret`, `client_disabled`, `client_expired`, `ip_not_allowed` |
| `session_revoked` | failed | refresh-token reuse (likely a stolen token): `reason`, `family_id` |
| `access_denied` | failed | any 403: `error_code` (`forbidden`, `cannot_grant`, `self_change`, ...) + its details |
