/**
 * Hide UI the user is not allowed to use. The backend still enforces every
 * permission; this only keeps the screen honest.
 *
 * Preferred (removes the element):
 *   const { can } = useCan()
 *   <q-btn v-if="can('users:manage')" label="Add user" />
 *
 * Directive (hides the element; value is one code or an array = all required):
 *   <q-btn v-can="'users:manage'" label="Add user" />
 *   <q-btn v-can:any="['users:read', 'roles:read']" />
 */
import { watchEffect } from 'vue'

import { useAuthStore } from './store.js'

export function useCan() {
  const auth = useAuthStore()
  return { can: auth.can, canAny: auth.canAny }
}

function allowed(binding) {
  const auth = useAuthStore()
  const codes = Array.isArray(binding.value) ? binding.value : [binding.value]
  return binding.arg === 'any' ? auth.canAny(codes) : auth.can(codes)
}

export const vCan = {
  mounted(el, binding) {
    el._canDisplay = el.style.display
    // Re-evaluates when the user's permissions change.
    el._canStop = watchEffect(() => {
      el.style.display = allowed(binding) ? el._canDisplay : 'none'
    })
  },
  unmounted(el) {
    el._canStop?.()
  },
}
