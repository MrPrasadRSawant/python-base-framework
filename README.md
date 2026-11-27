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

Create the database (once), then run the existing migrations and the server:

```powershell
# e.g. in psql:  CREATE DATABASE app_db;
alembic upgrade head
fastapi dev app/main.py              # http://localhost:8000  (docs: /docs)
pytest
```

In local development, `.env.example` enables `DEV_SEED_ACCOUNTS=true`. On startup,
the app creates these accounts if they do not already exist:

| Username | Email | Password | Role |
|---|---|---|---|
| `Admin` | `admin@baseframework.com` | `Admin@123` | `admin` (all current permissions) |
| `Developer` | `developer@baseframework.com` | `Developer@123` | `developer` (read exception, request, and service call logs) |

Sign in with either the username or email. They are separate, case-insensitively
unique fields. The seed only runs with `ENVIRONMENT=development` and a local
PostgreSQL host. It leaves existing account passwords and roles unchanged.
Set `DEV_SEED_ACCOUNTS=false` to disable it. Normal API account creation still
requires passwords of at least 12 characters; `Admin@123` is a local demo
credential only.

Structure:
```
app/
  main.py               FastAPI app, CORS, router mount
  core/config.py        Settings loaded from .env (pydantic-settings)
  db/base.py            SQLAlchemy declarative Base
  db/session.py         Async engine + get_db dependency
  models/               ORM models (register new ones in models/__init__.py)
  schemas/              <Entity>Create / <Entity>Update / <Entity>Response per table
                        (base.py: CreateSchema / UpdateSchema / ResponseSchema)
  services/             one service class per table: its database operations
                        (base.py: BaseService with get / create / create_many /
                        update / delete / search, shared by all)
  api/v1/router.py      Version-1 router
  api/v1/endpoints/     business logic; calls services, builds responses
alembic/                Migrations (DB URL read from .env); files are numbered
                        01_<hash>_<slug>.py, 02_..., assigned automatically by
                        `alembic revision` (see add_sequence_prefix in env.py)
tests/
```

Request flow: **schema** (validates input) → **endpoint** (business logic: decide,
raise errors, build the response) → **service** (database operations for one
table) → **model**.

### Adding a table: the standard pattern

Schema names say what they are for:

| Schema | Purpose | Inherits |
|---|---|---|
| `<Entity>Create` | POST body | `CreateSchema`: unknown fields rejected, strings trimmed |
| `<Entity>Update` | PATCH body, every field optional; only sent fields change | `UpdateSchema` |
| `<Entity>Response` | one record in any response | `ResponseSchema`: id + common columns |

POST `/search` uses the shared `SearchRequest` (`app/schemas/search.py`) for every table.
Responses are always wrapped: `RecordResponse[<Entity>Response]` for one record,
`ListResponse[<Entity>Response]` for lists.

Services inherit `BaseService` and only declare the model and which fields may be
used. Every service then has the same methods:

| Method | Does |
|---|---|
| `get(id)` | one record, or `None` (soft-deleted rows hidden unless `include_deleted=True`) |
| `create(data)` / `create_many(items)` | insert from `<Entity>Create` |
| `update(id, data)` | apply the fields sent in `<Entity>Update`; `None` if not found |
| `delete(id)` | soft delete; `False` if not found |
| `search(request)` | filters + text search + sort + limit/offset |

A typo in `filter_fields` / `sort_fields` / `search_fields` fails at startup.
All these methods are tracked in `service_call_logs` automatically; decorate your
own service methods with `@track_service` (see below).

```python
# models/order.py
class Order(AuditMixin, Base):
    __tablename__ = "orders"
    reference: Mapped[str] = mapped_column(String(50))
    total: Mapped[int]

# schemas/order.py
class OrderCreate(CreateSchema):
    reference: str = Field(max_length=50)
    total: int = Field(ge=0)

class OrderUpdate(UpdateSchema):
    total: int | None = Field(None, ge=0)

class OrderResponse(ResponseSchema):
    reference: str
    total: int

# services/order.py
class OrderService(BaseService):
    model = Order
    filter_fields = ("reference", "total", *AUDIT_FIELDS)
    sort_fields = ("total", "created_on")
    search_fields = ("reference",)

# api/v1/endpoints/orders.py
router = APIRouter(prefix="/orders", tags=["orders"])

@router.post("", response_model=RecordResponse[OrderResponse], status_code=201)
async def create_order(payload: OrderCreate, db: AsyncSession = Depends(get_db)):
    return record_response(await OrderService(db).create(payload))

@router.post("/search", response_model=ListResponse[OrderResponse])
async def search_orders(payload: SearchRequest, db: AsyncSession = Depends(get_db)):
    return list_response(await OrderService(db).search(payload))

@router.get("/{order_id}", response_model=RecordResponse[OrderResponse])
async def get_order(order_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    order = await OrderService(db).get(order_id)
    if order is None:
        raise NotFoundError("Order not found", details={"order_id": str(order_id)})
    return record_response(order)

@router.patch("/{order_id}", response_model=RecordResponse[OrderResponse])
async def update_order(order_id: uuid.UUID, payload: OrderUpdate, db: AsyncSession = Depends(get_db)):
    order = await OrderService(db).update(order_id, payload)
    if order is None:
        raise NotFoundError("Order not found", details={"order_id": str(order_id)})
    return record_response(order)

@router.delete("/{order_id}", status_code=204)
async def delete_order(order_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    if not await OrderService(db).delete(order_id):
        raise NotFoundError("Order not found", details={"order_id": str(order_id)})
```

Then register the model in `models/__init__.py`, include the router in
`api/v1/router.py`, and run `alembic revision --autogenerate -m "add orders"`.

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

**Request IDs.** Each request gets a UUID: an incoming `X-Request-ID` is reused if it
is a UUID (normalized to lowercase, hyphenated), otherwise a new time-ordered UUIDv7 is
generated. The id goes into every log line written during that request (your own
`logging.getLogger(__name__)` calls included), the `X-Request-ID` response header,
every response's `metadata.request_id`, and it is the primary key of the request's
row in the `requests` table.

**Error responses** always look like:
```json
{"metadata": {"request_id": "3f2c...", "timestamp": "2026-11-27T10:00:00Z"},
 "error": {"code": "not_found", "message": "Order not found", "details": {"order_id": 7}}}
```
Raise the classes from `app.core.exceptions` in endpoints and services:
`raise NotFoundError("Order not found", details={"order_id": order_id})`.

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
logging record --ExceptionLogDBHandler--> exception_log_sink (bounded queue)
               --background worker, batched--> INSERT INTO exception_log
```

- **What is stored:** every API error with status >= `EXCEPTION_LOG_DB_MIN_STATUS`
  (default 400), plus any `logger.exception(...)` / ERROR-with-traceback from anywhere
  in the code (background jobs, startup, ...).
- **Never blocks or breaks a request:** rows are queued and written in batches by a
  background task. If the database is down, the error is still in the log files. A
  failed batch is retried row by row. When the queue is full, rows are dropped and
  counted. Queued rows are flushed on shutdown.
- **No user data:** no request body, query string, headers, IP address or user agent.
  User `input` is stripped from validation `details`. Message and traceback are redacted.
  The log files still have the full redacted request context; join on `request_id`.
- **Columns:** request_id, status_code, error_code, exception_type, message, traceback,
  method, path, route, endpoint, details (JSONB), level, logger, source, environment,
  hostname, process_id, occurred_on, plus the common columns.

Find everything about a failed request from the id the client received:
```sql
SELECT * FROM exception_log WHERE request_id = '3f2c...';
```

Code: `app/core/logging/db_handler.py` (record -> row),
`app/core/logging/db_sink.py` (queue + worker),
`app/services/exception_log.py` (insert / get / search), `app/models/exception_log.py`.

### `requests` table

One row per request, for endpoint monitoring and reports: traffic, error rate and
latency. Its `id` **is** the request id, so every log table joins to it. It is built
from the access-log line the middleware already writes, through the same kind of
background batched writer (`request_log_sink`), so requests never wait on it.

| Column | Example |
|---|---|
| `id` | the request id: same as `X-Request-ID`, `metadata.request_id`, `exception_log.request_id`, `service_call_logs.request_id` |
| `started_on` | exact request start (UTC); rows are written up to a second later |
| `method` | `GET` |
| `route` | `/api/v1/orders/{order_id}`: the template, never the actual URL; group by this for per-endpoint stats; `NULL` for unknown URLs |
| `endpoint` | `app.api.v1.endpoints.orders.get_order` (the handler function) |
| `status_code` | `200` |
| `duration_ms` | `12.4`: from request start until the response was fully sent |

Plus the common columns (`created_by` will hold the user once auth exists). No user
data: no actual URL path (it carries ids and search terms), IP, user agent, query
string, headers or body. Paths in
`REQUEST_LOG_EXCLUDE_PATHS` (default: `/api/v1/health`) are skipped.

Typical monitoring queries:
```sql
-- slowest endpoints in the last hour
SELECT route, count(*), round(avg(duration_ms)) AS avg_ms,
       percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_ms
FROM requests WHERE started_on > now() - interval '1 hour'
GROUP BY route ORDER BY p95_ms DESC;

-- error rate per endpoint today
SELECT route, count(*) FILTER (WHERE status_code >= 500) * 100.0 / count(*) AS pct_5xx
FROM requests WHERE started_on > current_date GROUP BY route;

-- reports: a request with every service call and error it produced
SELECT r.id, r.route, r.status_code, r.duration_ms,
       s.call_order, s.service_name, s.duration_ms AS service_ms, e.error_code
FROM requests r
LEFT JOIN service_call_logs s ON s.request_id = r.id
LEFT JOIN exception_log e ON e.request_id = r.id
WHERE r.started_on > current_date
ORDER BY r.started_on, s.call_order;
```

The links from `exception_log.request_id` and `service_call_logs.request_id` to
`requests.id` are **logical** (same UUID type, indexed, used in JOINs) rather than
enforced foreign keys. The three tables are written by separate background writers,
so a service call or exception row usually reaches the database before its request
row, and health checks have no request row at all. An enforced foreign key would
reject those rows.

Read it over the API at `/api/v1/requests` (list / search / detail by request id,
see below) when `REQUEST_LOG_API_ENABLED=true`, or with SQL.

No automatic cleanup yet. The table grows by one row per request, so delete old
rows (e.g. `DELETE FROM requests WHERE started_on < now() - interval '30 days'`)
or add a retention job once volume needs it.

### `service_call_logs` table

One row per call of a function decorated with `@track_service`, for service load
monitoring: which services a request called, in what order, how long each took,
and whether it succeeded. Every `BaseService` method (get / create / create_many /
update / delete / search) is already decorated, so all table services are tracked.

```python
from app.core.service_tracking import track_service

class OrderService(BaseService):
    model = Order

    @track_service                     # recorded as "OrderService.mark_paid"
    async def mark_paid(self, order_id): ...

@track_service(name="pricing.calculate")   # plain functions, sync or async
def calculate_price(order): ...
```

| Column | Example |
|---|---|
| `request_id` | links to `requests.id` (and `exception_log.request_id`); `NULL` outside a request (jobs, startup) |
| `call_order` | `1, 2, 3…` in the order calls started within the request |
| `parent_call_order` | `call_order` of the tracked call that made this one; `NULL` = called by the endpoint |
| `service_name` | `OrderService.mark_paid` (runtime class, so inherited methods show the real service) |
| `started_on` / `duration_ms` | start time (UTC) and how long the call took |
| `status` | `success`, or `failed` when the function raised (the error is re-raised unchanged) |
| `error_type` | exception class only, e.g. `IntegrityError`; no message, arguments or return values |

Nested tracked calls get their own rows (`update` calls `get`, so both appear).
Rows go through the same background writer as the other log tables; the writers
themselves are not tracked. Set `SERVICE_CALL_LOG_DB_ENABLED=false` to switch it off.

```sql
-- what one request did, step by step
SELECT call_order, service_name, status, duration_ms
FROM service_call_logs WHERE request_id = '3f2c...' ORDER BY call_order;

-- busiest and slowest services in the last hour
SELECT service_name, count(*) AS calls, round(avg(duration_ms)) AS avg_ms,
       count(*) FILTER (WHERE status = 'failed') AS failures
FROM service_call_logs WHERE started_on > now() - interval '1 hour'
GROUP BY service_name ORDER BY calls DESC;
```

### Developer report

Built from the three tables joined on the request id (`requests.id`):

```
requests                  status, route, duration, outcome
 ├─ service_call_logs      each service: order, parent, duration, success/failed
 └─ exception_log          failure reason: error code, exception type, message
```

| Endpoint | Answers |
|---|---|
| `GET /api/v1/requests/{request_id}/report` | one request: outcome, failure reason, every service call nested under its caller with total / own time / % of the request, the slowest step, time outside services |
| `POST /api/v1/requests/report` | many requests (same filters / sort / paging as `/requests/search`): status, outcome, failure reason, slowest service |

A real drill-down (`GET /api/v1/requests/{id}/report`, shortened):
```json
{"record": {
  "method": "GET", "route": "/api/v1/exception-logs/{log_id}", "status_code": 404,
  "outcome": "failed",
  "failure": {"kind": "client_error", "error_code": "not_found",
              "exception_type": "NotFoundError", "message": "Exception log not found",
              "exception_log_id": "…"},
  "timing": {"request_ms": 324.7, "in_services_ms": 201.6, "outside_services_ms": 123.2,
             "slowest_service": "ExceptionLogService.get", "slowest_service_ms": 201.6},
  "services": [{"call_order": 1, "parent_call_order": null, "depth": 0,
                "service_name": "ExceptionLogService.get", "offset_ms": 113.6,
                "duration_ms": 201.6, "self_ms": 201.6, "percent_of_request": 62.1,
                "status": "success", "is_slowest": true}]}}
```

- **Outcome:** `failed` for any status ≥ 400. `failure.kind` is `client_error` (4xx)
  or `server_error` (5xx). The reason comes from `exception_log`; open
  `/api/v1/exception-logs/{exception_log_id}` for the traceback.
- **Own time (`self_ms`):** a call's duration minus the tracked calls it made, so a
  parent never looks slow just because a child was. `is_slowest` marks the highest
  own time.
- **Outside services:** request time minus top-level service time: routing,
  validation, endpoint code, response serialization.
- A service `status` of `success` with a failed request is normal: e.g. `get`
  returned nothing and the endpoint decided on 404.
- Rows land about a second after a request ends, so a report fetched immediately
  may be incomplete.

Recent failures with their reasons:
```json
POST /api/v1/requests/report
{"filters": [{"field": "status_code", "op": "gte", "value": 400}],
 "sort": [{"field": "started_on", "direction": "desc"}]}
```

### Response envelopes (every resource endpoint)

| Kind | Shape |
|---|---|
| list / search | `{"metadata": {...}, "records": [...]}` |
| single record | `{"metadata": {"request_id", "timestamp"}, "record": {...}}` |
| error | `{"metadata": {"request_id", "timestamp"}, "error": {"code", "message", "details"}}` |

List metadata:

| Field | Meaning |
|---|---|
| `request_id` | same as the `X-Request-ID` header and the `id` of the request's row in `requests` |
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
GET  /api/v1/<resource>?limit=20&offset=0     simple page, newest first
POST /api/v1/<resource>/search                filters + text search + sort + page
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
bad value returns a 422 that points at the failing filter. Only the fields in the
service's `filter_fields` / `sort_fields` are accepted; anything else gets a 422
with code `invalid_filter`.

Both log tables have read-only `GET` (list) / `POST /search` / `GET /{id}` endpoints.
Each is switched on by its own setting, and should get admin auth before being
enabled in production:

| Table | Endpoints | Setting |
|---|---|---|
| `exception_log` | `/api/v1/exception-logs` | `EXCEPTION_LOG_API_ENABLED` |
| `requests` | `/api/v1/requests` | `REQUEST_LOG_API_ENABLED` |
| `service_call_logs` | `/api/v1/service-call-logs` | `SERVICE_CALL_LOG_API_ENABLED` |

For example, the slowest failing requests:
```json
POST /api/v1/requests/search
{"filters": [{"field": "status_code", "op": "gte", "value": 500}],
 "sort": [{"field": "duration_ms", "direction": "desc"}], "limit": 20}
```

### Common columns (every table)

Inherit `AuditMixin` (`app/db/mixins.py`):

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | UUIDv7 (time-ordered) on Python 3.14+, else v4; DB default `gen_random_uuid()` |
| `created_by` | varchar(255) | current actor, default `system` |
| `created_on` | timestamptz | UTC, set on insert |
| `updated_by` | varchar(255) null | set on every UPDATE |
| `updated_on` | timestamptz null | UTC, set on every UPDATE |
| `is_deleted` | boolean | default `false`; set by `obj.soft_delete()` |

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
