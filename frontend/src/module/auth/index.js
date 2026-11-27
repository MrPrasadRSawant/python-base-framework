/**
 * Auth module: sign-in, session (access token + refresh cookie), route guards
 * and permission checks. Other modules use it through these exports only.
 */
import { installAuth } from './install.js'
import { publicRoutes } from './routes.js'

export { useAuthStore } from './store.js'
export { useCan, vCan } from './permissions.js'
export { default as UserMenu } from './components/UserMenu.vue'

export default {
  name: 'auth',
  publicRoutes,
  routes: [],
  menu: [],
  install: installAuth,
}
