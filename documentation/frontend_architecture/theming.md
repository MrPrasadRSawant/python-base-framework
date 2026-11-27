# Theming and brand

The frontend uses a restrained navy, blue, and teal palette. The sidebar has a light surface in light mode and a navy surface in dark mode, with matching text tokens in each. All application colors, spacing, radii, and shadows live in `frontend/src/css/quasar.variables.scss`. `app.scss` exposes them as `--app-*` properties so components can follow light and dark mode without duplicating values.

| Area | Tokens |
| --- | --- |
| Quasar brand and status | `$primary`, `$secondary`, `$accent`, `$positive`, `$negative`, `$warning`, `$info` |
| Page and card surfaces | `$app-light-*`, `$app-dark-*` |
| Navigation | `$app-sidebar-*` |
| Shape and spacing | `$app-radius-*`, `$app-space-*`, `$app-shadow-card` |

Use Quasar color props for buttons and status chips. Use CSS properties such as `var(--app-surface)` and `var(--app-border)` in component styles. Do not add color literals to pages or components; `npm run lint:colors` checks this.

The Baseframe mark is `frontend/public/icons/baseframe-mark.svg`. `BrandLogo.vue` uses it in the application shell and sign-in screen; `index.html` uses it as the favicon. The displayed name comes from `QCLI_APP_NAME` (with a fallback in `frontend/src/brand.js`). Keep `frontend/package.json` in sync for the build metadata.

The navigation drawer collapses to an icon rail with labels on hover. Below 1024 px it becomes a full-width overlay controlled by the same header button. The dashboard stacks its columns on smaller screens. Page transitions use a short fade and vertical shift, and turn off when the user requests reduced motion.
