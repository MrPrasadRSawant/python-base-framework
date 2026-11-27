/**
 * Consistent toasts for the whole app.
 *
 *   const notify = useNotify()
 *   notify.success('User created')
 *   notify.error(err)               // ApiError -> its message (+ request id)
 */
import { useQuasar } from 'quasar'

export function useNotify() {
  const $q = useQuasar()

  return {
    success(message) {
      $q.notify({ type: 'positive', message, icon: 'check_circle', position: 'top-right' })
    },
    info(message) {
      $q.notify({ type: 'info', message, position: 'top-right' })
    },
    error(errOrMessage) {
      const err = typeof errOrMessage === 'string' ? null : errOrMessage
      $q.notify({
        type: 'negative',
        message: err ? err.message : errOrMessage,
        caption: err?.requestId ? `Request id: ${err.requestId}` : undefined,
        icon: 'error_outline',
        position: 'top-right',
        timeout: 6000,
      })
    },
  }
}
