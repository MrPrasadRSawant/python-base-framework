# Baseframe frontend

Quasar and Vue frontend for the Python Base Framework. The signed-in shell, authentication, shared components, and API client are organized by feature under `src/module` and `src/api`.

## Run

```bash
npm install
npm run dev
```

The development server runs on port 9000 and forwards `/api` requests to `http://localhost:8000`. Set `QCLI_API_PROXY_TARGET` when the backend uses another address.

## Verify

```bash
npm run check
npm run build
```

`check` runs formatting, ESLint, the color token rule, and Vitest. The production build is written to `dist/spa`.

## Customize

Design tokens are in `src/css/quasar.variables.scss`. The logo is `public/icons/baseframe-mark.svg`, and the displayed name is set with `QCLI_APP_NAME`. See `../documentation/frontend_architecture/` for the module and component conventions.
