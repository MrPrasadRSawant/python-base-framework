# Changelog

## 2026-11-27: Developer monitoring and permission tools

- Added Exception Analysis with severity filters, error-code frequency, summary metrics, and redacted exception detail linked to its request.
- Added Request Lifecycle reports with response-time summaries and a chronological drilldown of service calls, nested work, failures, and response timing.
- Added Permission Management to review the catalog and assign role permissions. The Developer role can manage only permissions it already holds and cannot assign roles to users.

## 2026-11-27: User and Role Management

- Added separate, unique usernames to user creation, search, and sign-in. The login page accepts username or email.
- Added User Management with quick search, an advanced filter dialog, account creation, and enable/disable and lock/unlock actions.
- Added role assignment for existing users through a dedicated Manage roles dialog.
- Added Role Management with quick search, the shared advanced filter dialog, role creation and editing, permission assignment, and protected deletion.
- System role permissions are view-only. Permission options the administrator does not hold cannot be changed.

## 2026-11-27: Quality hardening
- Added unit tests (Vitest 4) for the API layer, auth store, guards and error messages; `npm test`.
- Added ESLint rule `app/module-boundaries` (modules only through `@/module/<name>`), and blocked `axios` outside `src/api`.
- Added `scripts/check-colors.mjs` (`npm run lint:colors`), which fails on hard-coded colors outside the tokens.
- Added the global error handler `boot/errors.js` for unhandled Vue errors and promise rejections.
- Added a module `reset()` hook, run on sign-out through the auth store's `onSignedOut()`.
- Added `npm run check` = lint + colors + tests.
- Fixed `lint:check`: it ran `prettier` without `--check`, so formatting was never checked. Prettier now accepts CRLF (`endOfLine: auto`, since Git on Windows checks out CRLF) and skips lock files (`.prettierignore`).

## 2026-11-27: Foundation + Auth module
- Added the API layer `src/api`: `http` (Bearer token, refresh-once with cross-tab lock, retry), `ApiError`, `createResource()`.
- Added the design tokens in `css/quasar.variables.scss` and CSS custom properties in `app.scss`, with light/dark support. No hard-coded colors remain elsewhere.
- Added generic components: `AppPageHeader`, `AppTable` (server-side paging, sort and search), `AppFormDialog`, `AppConfirmDialog`, `AppStatusChip`, `AppEmptyState`, plus the `useNotify` composable.
- Added the module system: `src/module/index.js` registry, and `boot/modules.js` (runs install hooks, sets the page title).
- Added the auth module: login page, in-memory token, session restore from the refresh cookie, route guards, `useCan` / `v-can`, user menu.
- New shell: `MainLayout` (permission-filtered menu, dark toggle, user menu), plus the Home, Forbidden and NotFound pages.
- Dev proxy `/api` → `http://localhost:8000`; `QCLI_API_BASE_URL=/api/v1`. Quasar `Notify` and `Dialog` plugins enabled.
- Removed the starter demo: `boot/axios.js`, `EssentialLink`, `IndexPage`, `SecondPage`, `example-store`.
