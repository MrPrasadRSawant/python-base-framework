import { defineBoot } from '#q-app'

import { appName } from '@/brand'
import { modules } from '@/module'
import { useAuthStore } from '@/module/auth'

// Install feature modules, clear their state on sign-out, and keep the browser
// title aligned with the current route.
export default defineBoot((ctx) => {
  for (const module of modules) module.install?.(ctx)

  useAuthStore(ctx.store).onSignedOut(() => {
    for (const module of modules) module.reset?.(ctx)
  })

  ctx.router.afterEach((to) => {
    document.title = to.meta.title ? `${to.meta.title} · ${appName}` : appName
  })
})
