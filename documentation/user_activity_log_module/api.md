# API: `/api/v1/user-activity-logs`

Mounted only with `ENABLE_USER_ACTIVITY_LOG=true`. Every route needs
`user_activity_logs:read` (401 without a token, 403 without the permission).
Standard envelopes, paging and search (see the root README).

| Method | Path | Does |
|---|---|---|
| GET | `/user-activity-logs?limit=&offset=` | newest first |
| POST | `/user-activity-logs/search` | filters + text search + sort + paging |
| GET | `/user-activity-logs/entities/{entity_type}/{entity_id}` | full history of one record |
| GET | `/user-activity-logs/{log_id}` | one row |

Search fields:

| Option | Fields |
|---|---|
| `filters` | `occurred_on`, `actor`, `actor_type`, `actor_id`, `action`, `status`, `entity_type`, `entity_id`, `request_id`, `method`, `route`, `ip_address`, audit columns |
| `sort` | `occurred_on` (default desc), `action`, `actor`, `entity_type`, `status` |
| `search` | `actor`, `action`, `entity_type`, `entity_id`, `route`, `ip_address`, request id |

## Investigation recipes

Who changed anything on 27 Nov:
```json
POST /api/v1/user-activity-logs/search
{"filters": [
  {"field": "occurred_on", "op": "between", "value": ["2026-11-27T00:00:00Z", "2026-11-28T00:00:00Z"]},
  {"field": "action", "op": "in", "value": ["create", "update", "delete", "restore"]}]}
```

Who touched this user record, ever: `GET /api/v1/user-activity-logs/entities/users/<user id>`

Everything one user did: `{"filters": [{"field": "actor_id", "value": "<user id>"}]}`

Refused attempts (failed sign-ins, denied access, token reuse):
`{"filters": [{"field": "status", "value": "failed"}]}`

Same IP across several accounts:
```sql
SELECT ip_address, count(DISTINCT actor_id) AS accounts, count(*) AS events
FROM user_activity_logs WHERE occurred_on > now() - interval '1 day'
GROUP BY ip_address HAVING count(DISTINCT actor_id) > 1 ORDER BY accounts DESC;
```

Everything a request did (activity + services + errors):
```sql
SELECT a.action, a.entity_type, a.changes, s.service_name, e.error_code
FROM user_activity_logs a
LEFT JOIN service_call_logs s ON s.request_id = a.request_id
LEFT JOIN exception_log e ON e.request_id = a.request_id
WHERE a.request_id = '3f2c...';
```
