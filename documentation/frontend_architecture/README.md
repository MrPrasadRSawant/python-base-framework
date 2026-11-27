# Frontend Architecture

Status: **Foundation, Auth, Users, and Roles modules done**

Quasar 2 (Vue 3, Vite) + Pinia + axios, JavaScript.

## Documents

| File | Content |
|---|---|
| [README.md](README.md) | Decisions, rules |
| [structure.md](structure.md) | Folders, module contract, request flow |
| [api_layer.md](api_layer.md) | HTTP client, token refresh, errors, generic resource client |
| [components.md](components.md) | Generic UI components and how to use them |
| [theming.md](theming.md) | Color / spacing tokens, dark mode |
| [auth_module.md](auth_module.md) | Login, session, guards, permissions in the UI |
| [users_module.md](users_module.md) | Admin list, creation, status, and lock flows |
| [roles_module.md](roles_module.md) | Role list, details, permissions, and deletion flows |
| [quality.md](quality.md) | Lint rules, color check, unit tests, error handling |
| [changelog.md](changelog.md) | Changes over time |

## Decisions

| # | Decision |
|---|---|
| F1 | Feature code lives in `src/module/<name>/`. Shared code lives in `api/`, `components/`, `composables/`, `css/` and `layouts/`. |
| F2 | Screens never call axios directly: module `api.js` → `src/api/http.js`. |
| F3 | The access token is kept **in memory only**. On reload the session is restored from the HttpOnly refresh cookie. |
| F4 | Dev server proxies `/api` → FastAPI, so the app and API share an origin. Production serves both behind one domain as well. |
| F5 | Colors, spacing and radii are defined only in `src/css/quasar.variables.scss`. |
| F6 | Permission checks in the UI only hide things; the backend enforces them. |

## Rules

- No hex or `rgb()` values outside `quasar.variables.scss`. Use Quasar color props (`color="primary"`) or `var(--app-*)`. Enforced by `npm run lint:colors`.
- Build pages from the `App*` components (`AppPageHeader`, `AppTable`, `AppFormDialog`…) for a consistent UI.
- A module imports another module only through its `index.js`, e.g. `import { useAuthStore } from '@/module/auth'`. Enforced by ESLint (`app/module-boundaries`), and `axios` is allowed only in `src/api/`.
- Run `npm run check` before committing.
- Branch on `ApiError.code`, show `ApiError.message`.
- Update these docs in the same change as the code.
