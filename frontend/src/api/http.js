/**
 * The single HTTP client for the backend. Modules never import axios directly:
 * they call `http` (usually through api/crud.js or their own api.js).
 *
 * What it does for every request:
 *  - Sends `Authorization: Bearer <access token>` (from the auth module).
 *  - Sends cookies (`withCredentials`), so the refresh cookie reaches /auth/*.
 *  - On `401 token_expired`: refreshes the token once, then retries the request.
 *    Concurrent requests share one refresh, and a browser-wide lock makes
 *    other tabs wait, so the refresh token is never used twice.
 *  - Turns every failure into an ApiError (api/errors.js).
 *
 * Per-request options (axios config):
 *  - skipAuth: true          do not send the access token (login, refresh)
 *  - skipAuthRefresh: true   do not refresh + retry on 401
 */
import axios from 'axios'

import { toApiError } from './errors.js'

export const http = axios.create({
  baseURL: import.meta.env.QCLI_API_BASE_URL || '/api/v1',
  timeout: 15000,
  withCredentials: true,
})

// Filled in by the auth module (module/auth/session.js) at startup.
const auth = {
  getToken: () => null,
  refresh: async () => false, // returns true when a new token was obtained
  onSessionEnded: () => {},
}

export function configureAuth(handlers) {
  Object.assign(auth, handlers)
}

// ---- one refresh at a time (this tab and other tabs) ---------------------
let refreshing = null

function withBrowserLock(fn) {
  // Web Locks API: serializes refreshes across tabs of the same origin.
  if (typeof navigator !== 'undefined' && navigator.locks?.request) {
    return navigator.locks.request('app-auth-refresh', fn)
  }
  return fn()
}

export function refreshOnce() {
  if (!refreshing) {
    refreshing = withBrowserLock(() => auth.refresh()).finally(() => {
      refreshing = null
    })
  }
  return refreshing
}

// ---- interceptors ----------------------------------------------------------
http.interceptors.request.use((config) => {
  const token = config.skipAuth ? null : auth.getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (response) => response,
  async (err) => {
    const error = toApiError(err)
    const config = err.config || {}
    const canRetry = error.status === 401 && !config.skipAuthRefresh && !config._retried
    if (canRetry && ['token_expired', 'invalid_token', 'not_authenticated'].includes(error.code)) {
      const sentToken = config.headers?.Authorization
      // Another request may already have refreshed: retry with the new token.
      const current = auth.getToken()
      const refreshed = current && `Bearer ${current}` !== sentToken ? true : await refreshOnce()
      if (refreshed) {
        config._retried = true
        return http.request(config)
      }
      auth.onSessionEnded()
    }
    return Promise.reject(error)
  },
)
