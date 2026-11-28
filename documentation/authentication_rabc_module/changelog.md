# Changelog

## 2026-11-28: User activity log permission

- Added the permission `user_activity_logs:read` (migration `16_7c3e9a1f5b2d`), granted to `admin`. See `documentation/user_activity_log_module/`.
- Sign-in, failed sign-in (with the real reason), sign-out, API-client token and refresh-token reuse events are now recorded in `user_activity_logs`; the API responses are unchanged.

## 2026-11-27: Usernames and default developer access

- Added a separate case-insensitive unique username, with migration backfill for existing users. Login and the OAuth password grant accept username or email.
- Seeded the `developer` role with read access to exception, request, and service call logs. The existing `admin` role retains all current permissions.
- Added `roles:read` and `roles:manage` to the developer role for Permission Management, with changes limited to permissions the developer already holds.
- Added optional local development seeding for the requested Admin and Developer accounts. Existing passwords and role assignments are preserved.

## 2026-11-27: Swagger documentation
- Added an API overview page (`app/api/api_description.md`): auth flows, authorization, envelopes, error codes, search and paging, rate limits, tracing. Also added tag descriptions and version `1.0.0`.
- Every endpoint now has a summary, an **Access** line (permission / signed-in user / public), behaviour notes and its exact error responses (`error_responses()` in `app/api/responses.py`).
- Added consumer-facing descriptions and examples to the auth, user, role and API client schemas, and to the common audit fields.
- Global error responses reduced to 422 / 500; each route documents its own 401/403/404/409/429.
- Added `tests/test_api_docs.py`, which keeps Access lines in sync with the real permission checks.
- Removed the unused `ClientCredentials` schema.

## 2026-11-27: Step 5, rate limiting
- Added `core/rate_limit.py`: an in-memory fixed-window limiter, the `rate_limit()` dependency and `limiter.check()`.
- Limited `/auth/login`, `/auth/token`, `/auth/register` and `/auth/refresh` per IP; client_credentials also per client_id. Over the limit returns 429 `rate_limited` + `Retry-After`.
- Added settings `RATE_LIMIT_ENABLED` and `RATE_LIMIT_LOGIN|REGISTER|REFRESH|TOKEN|TOKEN_PER_CLIENT`.
- Fixed: a form `client_id` without a secret was overwritten by the HTTP Basic fallback.
- Tests: `tests/test_rate_limit.py`.

## 2026-11-27: Step 4, API clients (client credentials)
- Added tables `api_clients` and `api_client_permissions` (migration `12_94c192e6ef7e`), plus the permissions `api_clients:read` and `api_clients:manage` (granted to admin).
- `POST /auth/token` now also accepts `grant_type=client_credentials` (form or HTTP Basic) and returns a `service` token with the client's permissions.
- Added `/api-clients` admin APIs: create (secret shown once), update, permissions, rotate-secret, delete.
- Checks on every token request: active, not expired, IP allowlist, argon2 secret; `last_used_on` is updated.
- Swagger OAuth2 scheme now has both password and clientCredentials flows.
- Added setting `SERVICE_TOKEN_TTL_MINUTES`.
- Tests: `tests/test_api_clients.py`.

## 2026-11-27: Swagger Authorize
- Added `POST /auth/token` (OAuth2 password grant, form-encoded, plain OAuth2 response).
- `get_principal` declares the `OAuth2Password` and `BearerToken` security schemes, so Swagger shows the Authorize button and lock icons.
- Swagger keeps the authorization across reloads (`persistAuthorization`).
- Login logic moved into one shared `_authenticate_user` (used by `/auth/login` and `/auth/token`).

## 2026-11-27: Step 3, RBAC
- Added tables `roles`, `permissions`, `user_roles`, `role_permissions` (migration `11_2bd946304e47`), which seeds the permission catalog and the system role `admin`.
- Added the permission catalog `core/security/permissions.py` (`Perm`).
- Access tokens (login and refresh) now carry the user's permissions; `/auth/me` returns roles and permissions.
- Added `/users`, `/roles` and `/permissions` admin APIs, with grant, manage and self-protection rules.
- The log APIs now require `exception_logs:read`, `request_logs:read` and `service_call_logs:read`.
- Added `python -m app.scripts.create_admin` to bootstrap the first admin.
- Tests: `tests/test_rbac.py`; the log API tests now call as an admin (`admin_headers` fixture).

## 2026-11-27: Step 2, refresh token rotation + logout
- Added `refresh_tokens` table (migration `10_db13bc33eaa4`).
- Login now also sets an HttpOnly refresh cookie (path `/api/v1/auth`).
- Added `POST /auth/refresh` (rotation; reuse revokes the family) and `POST /auth/logout`.
- Added `RefreshTokenService` (`issue`, `get_by_token`, `rotate`, `revoke_family`, `delete_expired`), all `@track_service`.
- Added settings `REFRESH_TOKEN_TTL_DAYS`, `REFRESH_COOKIE_NAME`, `REFRESH_COOKIE_SECURE`, `REFRESH_COOKIE_SAMESITE`.

## 2026-11-27: Step 1, users + login + access JWT
- Added `users` table (migration `09_12d624dcb207`), with a partial unique index on email.
- Added `core/security`: argon2 passwords, JWT access tokens, `Principal`, route dependencies.
- Added `AuthenticationMiddleware`: sets the principal and the actor (`user:<id>`), which is written to `created_by` / `updated_by` and the log tables.
- Added endpoints `POST /auth/register`, `POST /auth/login`, `GET /auth/me`.
- Added settings `JWT_*`, `ACCESS_TOKEN_TTL_MINUTES`, `LOGIN_MAX_FAILED`, `LOGIN_LOCK_MINUTES`, `AUTH_SELF_REGISTRATION_ENABLED`.
- Added dependencies `pyjwt`, `pwdlib[argon2]`.
- Added tests in `tests/test_auth.py`.
