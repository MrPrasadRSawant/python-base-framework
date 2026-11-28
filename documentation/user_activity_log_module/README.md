# User Activity Log Module

Status: **Done** (capture, table, API, permission, User Activity page). UI: see `../frontend_architecture/audit_module.md`.

An audit trail of what signed-in users (and API clients) do. It answers:

- *An important record changed on a given day: who changed it, what exactly, and from where?*
- *What did this user do between 10:00 and 11:00?*
- *Was anyone without the right access trying things?* (failed sign-ins, denied access, token reuse)

## Documents

| File | Content |
|---|---|
| [README.md](README.md) | Scope, decisions, how it works, doc rules |
| [datamodel.md](datamodel.md) | The `user_activity_logs` table, actions, indexes |
| [api.md](api.md) | Endpoints, examples, investigation queries |
| [changelog.md](changelog.md) | Changes to this module over time |

## Switch

`ENABLE_USER_ACTIVITY_LOG=true` (backend `.env`) turns on **both** the capture and the
`/api/v1/user-activity-logs` API. Off by default. Reading needs the permission
`user_activity_logs:read`, granted to the `admin` role by migration `16`.

## What is recorded

| Kind | Actions | How |
|---|---|---|
| Data changes | `create`, `update`, `delete`, `restore` | Automatic, for **every table**, from SQLAlchemy session events |
| Sign-in | `login`, `login_failed`, `logout` | Explicit, in `auth.py` |
| API clients | `token_issued`, `client_auth_failed` | Explicit, in `auth.py` |
| Suspicious | `session_revoked` (refresh-token reuse), `access_denied` (any 403) | Explicit |

Each row has: who (`actor`, `actor_type`, `actor_id`), when (`occurred_on`), what
(`action`, `status`), which record (`entity_type` = table, `entity_id`), the
before/after values (`changes`), and where from (`request_id`, `method`, `route`,
`ip_address`, `user_agent`).

## How capture works

```
endpoint -> service -> session.flush()  --after_flush-->  diff new/dirty/deleted -> pending (session.info)
                       session.commit() --after_commit--> pending -> user_activity_log_sink (queue)
                       session.rollback() ------------->  pending dropped
bulk update()/delete() --do_orm_execute--> rows snapshotted before/after -> pending
                                         background worker, batched --> INSERT user_activity_logs
```

Code: `backend/app/core/activity_log.py` (capture + `record_activity()`),
`app/models/user_activity_log.py`, `app/schemas/user_activity_log.py`,
`app/services/user_activity_log.py`, `app/api/v1/endpoints/user_activity_logs.py`.

## Decisions

| # | Decision |
|---|---|
| D1 | Capture at the **ORM session**, not in each endpoint, so new tables and services are audited with no extra code and nothing can be forgotten. |
| D2 | Rows are queued **on commit** only. A change that was rolled back is never reported as having happened. |
| D3 | Writes go through the existing non-blocking `DBLogSink` (same as the other log tables): a request never waits on the audit insert, and a DB outage never breaks a request. |
| D4 | Bulk `UPDATE`/`DELETE` statements are snapshotted (before, and after for updates) and recorded per row, so role/permission removals done in bulk are not invisible. Over 500 rows → one summary row. |
| D5 | Join-table "replace" (`replace_for_user`, `replace_for_role`, `replace_for_client`) now changes **only the differences** (`BaseService.replace_links`). Before, every save deleted and re-inserted all grants, which would read as "admin role removed and re-added". |
| D6 | **IP address and user agent are stored**, unlike the other log tables, because telling a stolen session from its owner is the point of this table. Access is restricted by `user_activity_logs:read`. |
| D7 | Sensitive column values (password / secret / token hashes, by the same key rules as log redaction) are stored as `[REDACTED]`: the change is visible, the value is not. |
| D8 | On a failed sign-in the typed username/email is **not** stored (people paste passwords into that field). The account is linked when it exists; otherwise the reason is `unknown_account`. |
| D9 | Not audited: the log tables themselves and `refresh_tokens` (`__activity_log__ = False`); sign-in bookkeeping columns (`users.failed_login_count`, `locked_until`, `last_login_on`, `api_clients.last_used_on`) via `__activity_log_ignore__`. Those are covered by the explicit sign-in events. |
| D10 | Reads (GET) are not duplicated here: the `requests` table already records every request with its caller (`created_by`) and route; join on `request_id`. |

## Opting a model out

```python
class MyCacheRow(AuditMixin, Base):
    __activity_log__ = False                                   # never audited

class Order(AuditMixin, Base):
    __activity_log_ignore__ = frozenset({"last_viewed_on"})   # updates to only these are skipped
```

Record a custom security event anywhere (never raises):

```python
from app.core.activity_log import record_activity
record_activity("export_downloaded", entity=report, details={"format": "csv"})
```

## Known limits

- A rolled-back `SAVEPOINT` (`session.begin_nested()`) inside a committed transaction
  is still recorded. The app does not use savepoints.
- Raw SQL (`text(...)`) and Core statements on a `Table` bypass the ORM and are not captured.
- No automatic retention yet: delete old rows with a job when volume requires it.

## Doc rules

- One topic per file; keep files short.
- Update the doc in the **same PR** as the code change.
- Record every change in `changelog.md`.
