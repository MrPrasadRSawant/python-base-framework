/**
 * Auth endpoints (backend: /api/v1/auth/*). See Swagger "auth" for details.
 *
 * login / refresh / logout never send the access token and never trigger the
 * automatic refresh-and-retry (they *are* the session endpoints).
 */
import { http } from '@/api'

const SESSION_CALL = { skipAuth: true, skipAuthRefresh: true }

export const authApi = {
  /** -> {access_token, token_type, expires_in}; also sets the refresh cookie. */
  async login(identifier, password) {
    const { data } = await http.post('/auth/login', { identifier, password }, SESSION_CALL)
    return data.record
  },

  /** New access token from the refresh cookie (the cookie is rotated). */
  async refresh() {
    const { data } = await http.post('/auth/refresh', null, SESSION_CALL)
    return data.record
  },

  /** Ends the session server-side and clears the cookie. Always succeeds. */
  async logout() {
    await http.post('/auth/logout', null, SESSION_CALL)
  },

  /** Signed-in user with roles and effective permissions. */
  async me() {
    const { data } = await http.get('/auth/me')
    return data.record
  },
}
