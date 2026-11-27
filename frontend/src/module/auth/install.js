/**
 * Wires the auth module into the app (called by boot/modules.js):
 *  - gives the HTTP layer the access token and the refresh function,
 *  - sends the user to the login page when the session ends,
 *  - installs the route guards and the v-can directive.
 */
import { configureAuth } from '@/api'

import { installAuthGuards } from './guards.js'
import { vCan } from './permissions.js'
import { useAuthStore } from './store.js'

export function installAuth({ app, router, store }) {
  const auth = useAuthStore(store)

  configureAuth({
    getToken: () => auth.accessToken,
    refresh: () => auth.refresh(),
    onSessionEnded: () => {
      auth.clear()
      const current = router.currentRoute.value
      if (!current.matched.some((r) => r.meta.public)) {
        router.replace({ name: 'login', query: { redirect: current.fullPath } })
      }
    },
  })

  installAuthGuards(router, auth)
  app.directive('can', vCan)
}
