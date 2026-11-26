# Python Base Framework

Full-stack starter: **FastAPI** (backend) + **Quasar** (frontend) + **PostgreSQL**.

```
backend/    FastAPI app (pip + requirements.txt, SQLAlchemy async, Alembic)
frontend/   Quasar app (created with `npm init quasar`, Vite, Pinia, axios)
```

## Prerequisites
- Python 3.12+
- Node.js 22.12+ / 24 / 26
- PostgreSQL running locally (default `localhost:5432`)

## Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env              # then set POSTGRES_* values
```

Create the database (once), then run migrations and the server:

```powershell
# e.g. in psql:  CREATE DATABASE app_db;
alembic revision --autogenerate -m "init"
alembic upgrade head
fastapi dev app/main.py              # http://localhost:8000  (docs: /docs)
pytest
```

Structure:
```
app/
  main.py               FastAPI app, CORS, router mount
  core/config.py        Settings loaded from .env (pydantic-settings)
  db/base.py            SQLAlchemy declarative Base
  db/session.py         Async engine + get_db dependency
  models/               ORM models (register new ones in models/__init__.py)
  schemas/              Pydantic request/response models
  api/v1/router.py      Version-1 router
  api/v1/endpoints/     health.py, items.py (example CRUD)
alembic/                Migrations (DB URL read from .env)
tests/
```

## Logging, errors & request tracing (backend)

```
app/core/request_context.py         request-id ContextVar + helpers
app/core/redaction.py               Redactor: key-based + pattern-based masking
app/core/logging/
  setup.py                          setup_logging(): console + rotating files
  formatters.py                     JsonFormatter / TextFormatter (both redact output)
  filters.py                        RequestIdFilter (stamps every record)
  request_info.py                   redacted snapshot of a request for logs
app/core/exceptions/
  errors.py                         AppException hierarchy (NotFoundError, ConflictError, ...)
  handlers.py                       handlers: AppException, HTTPException, validation, SQLAlchemy
  reporting.py                      report_exception(): the one place errors are logged
  responses.py                      error_response(): the one error envelope
app/middleware/
  request_context.py                assigns the request id, captures the body, sets the response header
  access_log.py                     one line per request (status, duration)
  unhandled_exception.py            unhandled error -> logged 500 envelope
  __init__.py                       register_middleware(): order documented here
```

**Request IDs.** Each request gets an id: a valid incoming `X-Request-ID` is reused,
otherwise a new one is generated. The id goes into every log line written during that
request (your own `logging.getLogger(__name__)` calls included), the `X-Request-ID`
response header, and every error body.

**Error responses** always look like:
```json
{"error": {"code": "not_found", "message": "Item not found",
           "request_id": "3f2c...", "details": {"item_id": 7}}}
```
Raise the classes from `app.core.exceptions` in endpoints and services:
`raise NotFoundError("Item not found", details={"item_id": item_id})`.

| Exception | Status | Log level |
|---|---|---|
| `AppException` subclasses | their own status | WARNING (4xx) / ERROR (5xx) |
| `HTTPException`, unknown route, wrong method | 404 / 405 / ... | WARNING |
| `RequestValidationError` | 422 (input of sensitive fields masked) | WARNING |
| `IntegrityError` / other `SQLAlchemyError` | 409 / 500 (SQL never sent to client) | WARNING / ERROR |
| anything else | 500 | ERROR + traceback, headers and body |

**Redaction.** All log output is masked before it's written:
- values under sensitive keys (password, token, secret, api_key, authorization, cookie,
  cvv, ... plus `REDACT_EXTRA_KEYS`), wherever they appear: body, query string, headers
  or `extra=`
- passwords in URLs, Bearer/Basic tokens, JWTs, `key=value` secrets
- Luhn-valid card numbers (last 4 digits kept)
- emails (optional, `REDACT_EMAILS`)

**Output.** The console uses `LOG_FORMAT` (text or json). `logs/app.log` and
`logs/error.log` are always JSON and rotate by size.

### `exception_log` table

Errors are also stored in PostgreSQL, alongside the log files:

```
logging record --ExceptionLogDBHandler--> ExceptionLogSink (bounded queue)
               --background worker, batched--> INSERT INTO exception_log
```

- **What is stored:** every API error with status >= `EXCEPTION_LOG_DB_MIN_STATUS`
  (default 400), plus any `logger.exception(...)` / ERROR-with-traceback from anywhere
  in the code (background jobs, startup, ...).
- **Never blocks or breaks a request:** rows are queued and written in batches by a
  background task. If the database is down, the error is still in the log files. A
  failed batch is retried row by row. When the queue is full, rows are dropped and
  counted. Queued rows are flushed on shutdown.
- **Redacted** exactly like the file logs: message, traceback, headers, query, body.
- **Columns:** request_id, status_code, error_code, exception_type, message, traceback,
  method, path, route, endpoint, client_ip, user_agent, query_params / request_headers /
  request_body / details (JSONB), level, logger, source, environment, hostname,
  process_id, occurred_on, plus the common columns.

Find everything about a failed request from the id the client received:
```sql
SELECT * FROM exception_log WHERE request_id = '3f2c...';
```

Code: `app/core/logging/db_handler.py` (record -> row), `app/services/exception_log_sink.py`
(queue + worker), `app/repositories/exception_log.py` (insert), `app/models/exception_log.py`.

### Response envelopes (every resource endpoint)

| Kind | Shape |
|---|---|
| list / search | `{"metadata": {...}, "records": [...]}` |
| single record | `{"metadata": {"request_id", "timestamp"}, "record": {...}}` |
| error | `{"metadata": {"request_id", "timestamp"}, "error": {"code", "message", "details"}}` |

List metadata:

| Field | Meaning |
|---|---|
| `request_id` | same as the `X-Request-ID` header and `exception_log.request_id` |
| `timestamp` | response time (UTC) |
| `limit`, `offset` | the page that was requested |
| `count` | records in this response |
| `total_count` | all matching records; `null` when `include_total=false` |
| `has_more` | more records after this page (accurate even without a total) |
| `next_offset` / `previous_offset` | ready-to-use offsets, `null` at either end |
| `sort` | ordering actually applied, including the `id` tie-breaker |

`/health` stays a plain object, because load balancers and probes expect that.

### List & search

```
GET  /api/v1/items?limit=20&offset=0     simple page, newest first
POST /api/v1/items/search                filters + text search + sort + page
```

```json
{
  "search": "widget",
  "filters": [
    {"field": "name", "op": "starts_with", "value": "Wid"},
    {"field": "created_on", "op": "between", "value": ["2026-01-01T00:00:00Z", "2026-12-31T23:59:59Z"]},
    {"field": "created_by", "op": "in", "value": ["system", "alice"]}
  ],
  "sort": [{"field": "name", "direction": "asc"}],
  "limit": 20,
  "offset": 0,
  "include_total": true,
  "include_deleted": false
}
```

Operators: `eq ne gt gte lt lte in not_in between contains starts_with ends_with is_null`.
Filters are combined with AND. `search` is a case-insensitive OR across the resource's
text fields. Values are converted to the column's type (UUID, datetime, ...), and a
bad value returns a 422 that points at the failing filter. Only allow-listed fields
are accepted, and they appear as enums in `/docs`.

Adding list and search to a new table takes one config object:

```python
ORDER_SEARCH = SearchConfig(
    model=Order,
    filterable=("status", "total", *AUDIT_FIELDS),
    sortable=("total", "created_on"),
    searchable=("reference",),
)

@router.post("/search", response_model=ListResponse[OrderRead])
async def search_orders(payload: ORDER_SEARCH.request_model, db=Depends(get_db)):
    return list_response(await run_search(db, ORDER_SEARCH, payload))
```

`exception_log` has the same `GET` / `POST /search` / `GET /{id}` endpoints under
`/api/v1/exception-logs` when `EXCEPTION_LOG_API_ENABLED=true`.

### Common columns (every table)

Inherit `AuditMixin` (`app/db/mixins.py`):

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | UUIDv7 (time-ordered) on Python 3.14+, else v4; DB default `gen_random_uuid()` |
| `created_by` | varchar(255) | current actor, default `system` |
| `created_on` | timestamptz | UTC, set on insert |
| `updated_by` | varchar(255) null | set on every UPDATE |
| `updated_on` | timestamptz null | UTC, set on every UPDATE |
| `is_deleted` | boolean | default `false` |
| `deleted_by` / `deleted_on` | null | set by `obj.soft_delete()` |

The actor comes from `set_current_actor()` in `app/core/request_context.py`. Once
authentication is added, call it with the user id in auth middleware and every table's
`created_by` / `updated_by` (and `exception_log.created_by`) is filled automatically.

```python
class Order(AuditMixin, Base):
    __tablename__ = "orders"
    total: Mapped[int]
```
Then `alembic revision --autogenerate -m "add orders"` and `alembic upgrade head`.

## Frontend

```powershell
cd frontend
npm install
copy .env.example .env
npm run dev                          # http://localhost:9000
npm run build
```

Only variables prefixed with `QCLI_` in `frontend/.env` reach client code, via
`import.meta.env.QCLI_*`. The shared axios instance lives in `src/boot/axios.js`
(`import { api } from '@/boot/axios'`). The home page calls `/api/v1/health`
to show backend and database status.

## Environment variables

| File | Key | Purpose |
|---|---|---|
| backend/.env | `APP_NAME`, `ENVIRONMENT`, `DEBUG` | App settings |
| backend/.env | `API_V1_PREFIX` | API prefix (default `/api/v1`) |
| backend/.env | `CORS_ORIGINS` | Comma-separated allowed origins |
| backend/.env | `POSTGRES_HOST/PORT/USER/PASSWORD/DB` | Database connection |
| frontend/.env | `QCLI_APP_NAME` | Display name |
| frontend/.env | `QCLI_API_BASE_URL` | Backend base URL |
