/**
 * Module registry. Each feature lives in its own folder under module/ and
 * exports a definition:
 *
 *   export default {
 *     name: 'users',
 *     publicRoutes: [],     // top-level routes with their own layout (e.g. /login)
 *     routes: [],           // pages inside the main layout (signed-in area)
 *     menu: [               // drawer entries; shown only with the permission
 *       { label: 'Users', icon: 'group', to: { name: 'users' }, permission: 'users:read' },
 *     ],
 *     install: ({ app, router, store }) => {},   // optional, runs at startup
 *     reset: ({ store }) => {},  // optional, on sign-out: drop the user's data
 *   }
 *
 * Adding a module = create module/<name>/index.js and list it below.
 */
import auth from './auth'

export const modules = [auth]

export const publicRoutes = modules.flatMap((m) => m.publicRoutes || [])
export const appRoutes = modules.flatMap((m) => m.routes || [])
export const menuItems = modules.flatMap((m) => m.menu || [])
