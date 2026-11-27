/**
 * Auth state: the signed-in user, their permissions and the access token.
 *
 * The access token is kept in memory only (never localStorage), so scripts
 * injected into the page cannot steal a long-lived credential. After a page
 * reload, restoreSession() gets a new token from the HttpOnly refresh cookie.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { authApi } from './api.js'

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref(null)
  const expiresAt = ref(0) // epoch ms
  const user = ref(null)
  const initialized = ref(false) // restoreSession() finished
  let restoring = null
  const signedOutHandlers = new Set()

  const isAuthenticated = computed(() => Boolean(accessToken.value && user.value))
  const permissions = computed(() => new Set(user.value?.permissions || []))
  const roles = computed(() => user.value?.roles || [])

  /** True when the user holds every listed permission. */
  function can(...codes) {
    return codes.flat().every((code) => permissions.value.has(code))
  }

  /** True when the user holds at least one listed permission. */
  function canAny(...codes) {
    return codes.flat().some((code) => permissions.value.has(code))
  }

  function setToken({ access_token: token, expires_in: expiresIn }) {
    accessToken.value = token
    expiresAt.value = Date.now() + expiresIn * 1000
  }

  function clear() {
    const wasSignedIn = Boolean(user.value)
    accessToken.value = null
    expiresAt.value = 0
    user.value = null
    // Let other modules drop the previous user's data (module `reset` hooks).
    if (wasSignedIn) {
      for (const handler of signedOutHandlers) {
        try {
          handler()
        } catch (err) {
          console.error('signed-out handler failed', err)
        }
      }
    }
  }

  /** Run `handler` whenever a signed-in session ends (logout, expiry). Returns an unsubscribe. */
  function onSignedOut(handler) {
    signedOutHandlers.add(handler)
    return () => signedOutHandlers.delete(handler)
  }

  async function login(identifier, password) {
    setToken(await authApi.login(identifier, password))
    user.value = await authApi.me()
  }

  /** New access token from the refresh cookie. Returns false when the session is over. */
  async function refresh() {
    try {
      setToken(await authApi.refresh())
    } catch {
      clear()
      return false
    }
    // Pick up role / permission changes in the background (not awaited:
    // this runs while the HTTP layer waits for the refresh to finish).
    if (user.value) reloadUser().catch(() => {})
    return true
  }

  async function reloadUser() {
    user.value = await authApi.me()
  }

  /** Called once at startup (by the router guard): sign back in from the cookie. */
  function restoreSession() {
    if (initialized.value) return Promise.resolve()
    if (!restoring) {
      restoring = (async () => {
        try {
          if (await refresh()) await reloadUser()
        } catch {
          clear()
        } finally {
          initialized.value = true
          restoring = null
        }
      })()
    }
    return restoring
  }

  async function logout() {
    try {
      await authApi.logout()
    } finally {
      clear()
    }
  }

  return {
    accessToken,
    expiresAt,
    user,
    initialized,
    isAuthenticated,
    permissions,
    roles,
    can,
    canAny,
    login,
    refresh,
    reloadUser,
    restoreSession,
    logout,
    clear,
    onSignedOut,
  }
})
