import { defineBoot } from '#q-app'
import { Notify } from 'quasar'

import { ApiError } from '@/api'

/**
 * Last line of defence: errors nobody handled (in a component, a watcher or an
 * un-awaited promise) are logged and shown as a toast instead of failing silently.
 * Handled errors (caught by the screen) never reach this.
 */
export function describeError(err) {
  if (err instanceof ApiError) {
    return { message: err.message, caption: err.requestId ? `Request id: ${err.requestId}` : '' }
  }
  return { message: 'Something went wrong. Please try again.', caption: '' }
}

function show(err) {
  // A session that ended is handled by the auth module (redirect to sign-in).
  if (err instanceof ApiError && err.status === 401) return
  const { message, caption } = describeError(err)
  Notify.create({
    type: 'negative',
    icon: 'error_outline',
    position: 'top-right',
    timeout: 6000,
    message,
    caption: caption || undefined,
  })
}

export default defineBoot(({ app }) => {
  app.config.errorHandler = (err, _instance, info) => {
    console.error(`[vue] ${info}`, err)
    show(err)
  }

  window.addEventListener('unhandledrejection', (event) => {
    console.error('[unhandled promise]', event.reason)
    show(event.reason)
  })
})
