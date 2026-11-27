# API

Prefix `/api/v1`. Responses use the standard envelopes (`{"metadata", "record"}`, errors `{"metadata", "error"}`).

| Method | Path | Auth | Step | Status |
|---|---|---|---|---|
| POST | `/auth/register` | public (if `AUTH_SELF_REGISTRATION_ENABLED`) | 1 | ✅ |
| POST | `/auth/login` | public | 1 | ✅ |
| GET | `/auth/me` | user token | 1 | ✅ |
| POST | `/auth/refresh` | refresh cookie | 2 | ✅ |
| POST | `/auth/logout` | refresh cookie | 2 | ✅ |
| POST | `/auth/token` (`grant_type=password`) | public, form-encoded | 3 | ✅ |
| POST | `/auth/token` (`grant_type=client_credentials`) | client credentials | 4 | ✅ |
| GET, POST /search, GET /{id} | `/api-clients` | `api_clients:read` | 4 | ✅ |
| POST, PATCH /{id}, PUT /{id}/permissions, POST /{id}/rotate-secret, DELETE /{id} | `/api-clients` | `api_clients:manage` | 4 | ✅ |
| GET, POST /search, GET /{id} | `/users` | `users:read` | 3 | ✅ |
| POST, PATCH /{id}, DELETE /{id}, PUT /{id}/roles, PUT /{id}/lock | `/users` | `users:manage` | 3 | ✅ |
| GET, POST /search, GET /{id} | `/roles` | `roles:read` | 3 | ✅ |
| POST, PATCH /{id}, DELETE /{id}, PUT /{id}/permissions | `/roles` | `roles:manage` | 3 | ✅ |
| GET | `/permissions` | `roles:read` | 3 | ✅ |
| all | `/exception-logs`, `/requests`, `/service-call-logs` | `*_logs:read` | 3 | ✅ |

## POST /auth/register
```json
{"username": "Alice", "email": "alice@example.com", "full_name": "Alice", "password": "min-12-characters"}
```
201 → `record`: `UserResponse` (id, username, email, full_name, is_active, is_locked, locked_until, last_login_on, audit fields).
Email is lower-cased. Username and email are separate and each is case-insensitively unique. Errors: 403 `registration_disabled`, 409 `email_taken` or `username_taken`, 422 validation.

## POST /auth/login
```json
{"identifier": "Alice", "password": "..."}
```
200 → `{"record": {"access_token": "<jwt>", "token_type": "bearer", "expires_in": 900}}` + `Set-Cookie: refresh_token=…; HttpOnly; Path=/api/v1/auth`

`identifier` accepts a username or email. 401 `invalid_credentials` for every failure (unknown account, wrong password, inactive, locked).
After `LOGIN_MAX_FAILED` wrong passwords the account is locked for `LOGIN_LOCK_MINUTES`.

## POST /auth/refresh
No body; sends the refresh cookie (axios: `withCredentials: true`).
200 → same body as login + a **new** refresh cookie (the old one stops working).
401 `invalid_refresh_token`: missing, unknown, expired, or reused (reuse revokes the whole session).

## POST /auth/logout
No body. Revokes the session and clears the cookie. Always 204.
The access token stays valid until it expires (≤ 15 min); the frontend drops it.

## POST /auth/token (OAuth2)
Form: `grant_type=password&username=<username-or-email>&password=...`
200 → plain OAuth2 body (no envelope): `{"access_token", "token_type": "bearer", "expires_in"}`. No refresh cookie.
Used by Swagger and OAuth2 tools; the web app uses `/auth/login`.

### Client credentials (server integrations)
```
POST /api/v1/auth/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&client_id=cli_...&client_secret=...
```
Or send `Authorization: Basic base64(client_id:client_secret)` with `grant_type=client_credentials`.
200 → `{"access_token", "token_type": "bearer", "expires_in"}` (a `service` token). When it expires, request a new one; there is no refresh token.
401 `invalid_client` for every failure (unknown, wrong secret, disabled, expired, IP not allowed).

## API clients (admin)
- `POST /api-clients` `{"name", "description"?, "permissions": [...], "allowed_ips"?: ["10.0.0.0/8"], "expires_on"?}` → 201, includes `client_id` and **`client_secret` (shown once)**
- `PATCH /api-clients/{id}` `{"name"?, "description"?, "is_active"?, "allowed_ips"?, "expires_on"?}`
- `PUT /api-clients/{id}/permissions` `{"permissions": [...]}` replaces the full set
- `POST /api-clients/{id}/rotate-secret` → new secret (shown once); the old one stops working immediately
- `DELETE /api-clients/{id}` → 204

Disabling, deleting or rotating blocks new tokens at once. A token already issued stays valid until it expires (≤ `SERVICE_TOKEN_TTL_MINUTES`).

## Swagger (`/docs`)
Click **Authorize**, then use one of:
- **OAuth2 / password**: enter username or email + password (client_id/secret empty) → Swagger calls `/auth/token`.
- **OAuth2 / clientCredentials**: enter an API client's client_id + client_secret.
- **BearerToken**: paste an access token.

Protected routes show a lock icon. The token is kept across reloads (`persistAuthorization`).

## GET /auth/me
Header `Authorization: Bearer <jwt>` → 200 `record`: `UserDetailResponse` (`UserResponse` + `roles`, `permissions`).
401 no/invalid/expired token · 403 service token · 404 user deleted or disabled.

## Users (admin)
- `POST /users` `{"username", "email", "full_name", "password", "roles": ["admin"]}` → 201 `UserDetailResponse`
- `PATCH /users/{id}` `{"username"?, "full_name"?, "is_active"?}`; disabling also signs the user out
- `PUT /users/{id}/lock` `{"locked": true|false}` sets a persistent administrator lock, separate from `is_active`. Locking revokes refresh sessions; unlocking also clears a temporary failed-password lockout.
- `PUT /users/{id}/roles` `{"roles": [...]}` replaces the full set (`[]` removes all)
- `DELETE /users/{id}` → 204 (soft delete; signs the user out)

## Roles (admin)
- `POST /roles` `{"code": "support_agent", "name": "...", "description"?}` → 201 `RoleDetailResponse` (+ `permissions`)
- `PUT /roles/{id}/permissions` `{"permissions": ["users:read"]}` replaces the full set
- `DELETE /roles/{id}` → 204, also removes the role from every user

Migrations seed `admin` with all current permissions. `developer` has
`exception_logs:read`, `request_logs:read`, `service_call_logs:read`, and
`roles:read` / `roles:manage` for Permission Management. Role changes remain
limited to permissions the developer already holds, and developers cannot assign
roles to users. Optional local development seeding creates one account for each
role (see the repository README). It never runs against a remote or production database.

## Rate limits
`/auth/login`, `/auth/token`, `/auth/register` and `/auth/refresh` are limited per client IP; client_credentials is also limited per client_id. Over the limit: `429` `rate_limited` + `Retry-After: <seconds>`. Limits are in `RATE_LIMIT_*` settings.

## RBAC errors
| Status | `error.code` | When |
|---|---|---|
| 403 | `forbidden` | missing permission (`details.missing_permissions`) |
| 403 | `cannot_grant` | granting or touching permissions you don't hold |
| 403 | `self_change` | disabling, deleting or re-roling yourself |
| 403 | `system_role` | deleting or editing the permissions of `admin` |
| 409 | `email_taken` / `username_taken` / `role_code_taken` | duplicate |
| 422 | `unknown_roles` / `unknown_permissions` | code not found |

## Documenting an endpoint (Swagger)

Swagger at `/docs` (ReDoc at `/redoc`) is the reference for frontend and integration teams.
The overview page comes from `backend/app/api/api_description.md`, and tag descriptions from `OPENAPI_TAGS` in `main.py`.

Every route needs:
1. `summary="..."`: a short title.
2. A docstring that **starts with an Access line**:
   - `**Access:** Public.`
   - `**Access:** Signed-in user (user token only).`
   - ``**Access:** Permission `x:y`.``

   Follow it with behaviour, side effects and the search fields.
3. `responses=error_responses(...)` (from `app/api/responses.py`) with the route's error statuses and `error.code` values. Use `PROTECTED` for 401 + 403.
4. Schema docstrings and `Field(description=..., examples=[...])` written for API consumers. Internal notes go in `#` comments, not docstrings.

`tests/test_api_docs.py` fails if a route has no summary or Access line, if the Access line doesn't name the permissions the code requires, if a protected route lacks 401/403, or if a tag has no description.

## Protecting a route
```python
from app.core.security import CurrentUser, require_permission
from app.core.security.permissions import Perm

@router.get("/me")
async def me(principal: CurrentUser): ...

@router.get("", dependencies=[Depends(require_permission(Perm.ORDERS_READ))])
async def list_orders(...): ...
```
