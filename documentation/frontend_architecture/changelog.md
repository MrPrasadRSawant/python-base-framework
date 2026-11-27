# Changelog

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
