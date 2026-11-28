# Changelog

## 2026-11-28: UI

- Added the User Activity page (frontend `audit` module) and History links from the Users and Roles pages. See `documentation/frontend_architecture/audit_module.md`.

## 2026-11-28: Backend

- Added the `user_activity_logs` table (migration `16_7c3e9a1f5b2d`) and the permission
  `user_activity_logs:read`, granted to `admin`.
- Added `app/core/activity_log.py`: automatic capture of committed `create` / `update` /
  `delete` / `restore` on every table (before/after values, sensitive values redacted),
  bulk `UPDATE` / `DELETE` capture, and `record_activity()` for security events.
- Recorded `login`, `login_failed` (with reason), `logout`, `token_issued`,
  `client_auth_failed`, `session_revoked` (refresh-token reuse) and `access_denied` (every 403).
- Added the read API `/api/v1/user-activity-logs` (list, search, record history, detail).
- Added the setting `ENABLE_USER_ACTIVITY_LOG` (capture + API; default off).
- Added the request-scope ContextVar (`get_request_scope()`) so captured rows know the
  route, IP and user agent.
- Changed `replace_for_user` / `replace_for_role` / `replace_for_client` to change only
  the differences (`BaseService.replace_links`), so unchanged grants are not rewritten.
- Tests: `tests/test_user_activity_log.py`; `tests/conftest.py` routes activity rows to an
  in-memory sink in every test.
