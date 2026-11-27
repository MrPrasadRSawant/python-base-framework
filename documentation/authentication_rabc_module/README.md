# Authentication & RBAC Module

Status: **All steps done** (login, refresh rotation, RBAC, API clients, rate limiting)

## Documents

| File | Content | Status |
|---|---|---|
| [README.md](README.md) | Scope, decisions, doc rules | Done |
| [datamodel.md](datamodel.md) | Tables, columns, constraints, ER diagram | Done |
| [high_level_diagram.md](high_level_diagram.md) | Components and main flows | Done |
| [low_level_diagram.md](low_level_diagram.md) | Code layout, middleware, sequence diagrams, token claims | Done |
| [api.md](api.md) | Endpoints, request/response | Done (steps 1-5) |
| [changelog.md](changelog.md) | Changes to this module over time | Ongoing |

## Decisions

| # | Decision |
|---|---|
| D1 | Web users: JWT access token (~15 min, `Authorization: Bearer`) + refresh token (~7 days, HttpOnly/Secure/SameSite cookie, rotated, stored hashed in DB). |
| D2 | Server integrations: OAuth2 **client credentials**. `client_id` + `client_secret` → `POST /auth/token` → short-lived JWT. No refresh token. |
| D3 | One JWT format for both; `type` claim = `user` \| `service`. |
| D4 | Authorization = RBAC. Users get permissions via roles; API clients get permissions directly (scopes). One shared permission catalog. |
| D5 | Permission code format: `resource:action` (e.g. `request_logs:read`). |
| D6 | Passwords: argon2. Secrets/tokens: stored as hashes only. |
| D7 | Blocking non-browser callers of user APIs: **dropped** (not reliably possible). Rate limiting remains. |

## Implementation steps

1. Users + password hashing + login + access JWT ✅
2. Refresh token rotation + logout ✅
3. RBAC (roles, permissions, `require_permission` dependency) ✅
4. API clients (client credentials) + scopes ✅
5. Rate limiting ✅

## Doc rules

- One topic per file; keep files short.
- Update the doc in the **same PR** as the code change.
- Record every change in `changelog.md`.
