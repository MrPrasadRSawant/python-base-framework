# Quality Checks

Run everything with `npm run check` (lint + colors + tests) from `frontend/`.

| Command | Checks |
|---|---|
| `npm run lint:check` | Prettier + ESLint, including the architecture rules below |
| `npm run lint:colors` | No hard-coded colors outside the token file |
| `npm test` / `npm run test:watch` | Vitest unit tests |
| `npm run build` | Production build |

## Architecture rules (ESLint)

| Rule | Fails on |
|---|---|
| `app/module-boundaries` (local rule, `eslint-rules/module-boundaries.js`) | Importing a module's internal files (`@/module/auth/store.js`) from outside it, or reaching from one module into another (`../users/api.js`). Allowed: `@/module/<name>`. |
| `no-restricted-imports` | `import axios` outside `src/api/` (use `@/api`) |

## Color rule (`scripts/check-colors.mjs`)

Scans `.vue`, `.js`, `.scss` and `.css` under `src/` (templates, scripts and styles) for hex colors and `rgb()` / `rgba()` / `hsl()` / `hsla()`. The only allowed file is `src/css/quasar.variables.scss`.

## Unit tests

Tests sit next to the code in `__tests__/` folders (`vitest.config.js`, node environment, `@` alias).

| File | Covers |
|---|---|
| `src/api/__tests__/http.test.js` | Bearer header, refresh-once + retry, shared refresh for parallel 401s, session end, no refresh loops, `ApiError` mapping |
| `src/module/auth/__tests__/store.test.js` | login, `can` / `canAny`, restore session once, failed refresh, logout, signed-out handlers |
| `src/module/auth/__tests__/guards.test.js` | redirect to login, public routes, permissions (incl. parent routes), forbidden, `safeRedirect` |
| `src/boot/__tests__/errors.test.js` | global error messages |

New modules add their own `__tests__/` for stores and non-trivial logic.

## Runtime safety nets

| Concern | Handling |
|---|---|
| Unhandled errors (components, watchers, promises) | `boot/errors.js`: logged + toast (ApiError message and request id; generic text otherwise). 401s are left to the auth module. |
| Data left from the previous user | On sign-out (logout or expired session) the auth store runs its `onSignedOut` handlers. `boot/modules.js` calls every module's `reset()`. |
