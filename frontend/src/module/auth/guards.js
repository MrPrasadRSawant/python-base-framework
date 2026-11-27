/**
 * Route protection, driven by route meta:
 *
 *   meta: { public: true }                       no sign-in needed (login, 404)
 *   meta: { permission: 'users:read' }           signed in + this permission
 *   meta: { permission: ['a:read', 'b:read'] }   signed in + all of them
 *   (no meta)                                    signed in
 *
 * Permissions on parent routes apply to their children.
 */
export function installAuthGuards(router, auth) {
  router.beforeEach(async (to) => {
    await auth.restoreSession()

    if (to.matched.some((r) => r.meta.public)) {
      if (to.name === 'login' && auth.isAuthenticated) {
        return safeRedirect(to.query.redirect)
      }
      return true
    }

    if (!auth.isAuthenticated) {
      return { name: 'login', query: { redirect: to.fullPath } }
    }

    const required = to.matched.flatMap((r) => [r.meta.permission ?? []].flat())
    if (required.length && !auth.can(required)) {
      return { name: 'forbidden', query: { from: to.fullPath } }
    }
    return true
  })
}

/** Only follow in-app paths after login (never an absolute URL). */
export function safeRedirect(target) {
  return typeof target === 'string' && target.startsWith('/') && !target.startsWith('//')
    ? target
    : '/'
}
