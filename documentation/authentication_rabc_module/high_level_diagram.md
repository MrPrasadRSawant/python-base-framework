# High Level Design

## 1. Context

```mermaid
flowchart LR
    U([Web user]) --> FE[Quasar frontend]
    FE -- "Bearer JWT (user) + refresh cookie" --> API
    S([Server integration]) -- "Bearer JWT (service)" --> API
    subgraph API[FastAPI backend]
        AUTH[Auth module]
        BIZ[Business APIs]
    end
    API --> DB[(PostgreSQL)]
```

Two kinds of caller, one token format:

| Caller | Gets token from | Token `type` | Permissions from |
|---|---|---|---|
| Web user | `/auth/login`, `/auth/refresh` | `user` | roles |
| Server integration | `/auth/token` (client credentials) | `service` | client scopes |

## 2. Components

```mermaid
flowchart TB
    subgraph Endpoints
        E1["/auth/login · /refresh · /logout · /me"]
        E2["/auth/token"]
        E3["/api-clients (admin)"]
        E4[Business routes]
    end
    subgraph Security["core/security"]
        DEP[Dependencies<br/>require_permission / require_user / require_service]
        TOK[JWT tokens]
        PWD[Password / secret hashing]
    end
    subgraph Services
        SA[AuthService]
        SC[ApiClientService]
        SR[RbacService]
    end
    E1 --> SA
    E2 --> SC
    E3 --> SC
    E4 --> DEP --> TOK
    SA --> PWD & TOK & SR
    SC --> PWD & TOK & SR
    SA & SC & SR --> DB[(users · roles · permissions<br/>refresh_tokens · api_clients)]
```

## 3. Main flows

```mermaid
flowchart LR
    subgraph A[Issue token]
        L[Login / client credentials] --> V[Verify credentials] --> P[Load permissions] --> J[Sign JWT]
    end
    subgraph B[Use token]
        R[Request + Bearer] --> D[Verify JWT] --> C{Has permission?}
        C -- yes --> H[Handler]
        C -- no --> X[403]
    end
    J -.-> R
```

- **Web user:** access token ~15 min; refresh cookie (~7 days, rotated) renews it silently.
- **Integration:** requests a new service token on expiry; no refresh token.
- **Authorization:** checked from token claims only, with no DB hit per request.

## 4. Security boundaries

| Concern | Control |
|---|---|
| Stolen access token | short TTL (15 min) |
| Stolen refresh token | HttpOnly cookie, rotation, reuse → revoke family |
| Brute-force login | lockout after N failures, rate limiting |
| Leaked client secret | stored hashed, rotate / revoke, optional IP allowlist |
| Audit | actor (`user:<id>` / `service:<client_id>`) written to `created_by` / `updated_by` and request logs |
