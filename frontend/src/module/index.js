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
import audit from './audit'
import auth from './auth'
import developer from './developer'
import roles from './roles'
import users from './users'

export const modules = [auth, users, roles, audit, developer]

export const publicRoutes = modules.flatMap((m) => m.publicRoutes || [])
export const appRoutes = modules.flatMap((m) => m.routes || [])
export const menuItems = modules.flatMap((m) => m.menu || [])
