import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api'

import { authApi } from '../api.js'
import { useAuthStore } from '../store.js'

vi.mock('../api.js', () => ({
  authApi: { login: vi.fn(), refresh: vi.fn(), logout: vi.fn(), me: vi.fn() },
}))

const TOKEN = { access_token: 'tok', token_type: 'bearer', expires_in: 900 }
const USER = {
  id: 'u1',
  full_name: 'Alice',
  roles: ['admin'],
  permissions: ['users:read', 'users:manage'],
}
const expired = () =>
  new ApiError({ status: 401, code: 'invalid_refresh_token', message: 'Session expired' })

beforeEach(() => {
  vi.clearAllMocks()
  setActivePinia(createPinia())
  vi.mocked(authApi.login).mockResolvedValue(TOKEN)
  vi.mocked(authApi.refresh).mockResolvedValue(TOKEN)
  vi.mocked(authApi.me).mockResolvedValue(USER)
  vi.mocked(authApi.logout).mockResolvedValue()
})

describe('auth store', () => {
  it('login stores the token and the user', async () => {
    const auth = useAuthStore()
    await auth.login('alice@example.com', 'secret')
    expect(auth.accessToken).toBe('tok')
    expect(auth.isAuthenticated).toBe(true)
    expect(auth.roles).toEqual(['admin'])
    expect(auth.expiresAt).toBeGreaterThan(Date.now())
  })

  it('can() needs all permissions, canAny() one of them', async () => {
    const auth = useAuthStore()
    await auth.login('a', 'b')
    expect(auth.can('users:read')).toBe(true)
    expect(auth.can('users:read', 'roles:read')).toBe(false)
    expect(auth.can(['users:read', 'users:manage'])).toBe(true)
    expect(auth.canAny('roles:read', 'users:read')).toBe(true)
    expect(auth.canAny('roles:read')).toBe(false)
  })

  it('restoreSession signs back in from the cookie, once', async () => {
    const auth = useAuthStore()
    await Promise.all([auth.restoreSession(), auth.restoreSession()])
    await auth.restoreSession()
    expect(authApi.refresh).toHaveBeenCalledTimes(1)
    expect(auth.isAuthenticated).toBe(true)
    expect(auth.initialized).toBe(true)
  })

  it('restoreSession without a session leaves the user signed out', async () => {
    vi.mocked(authApi.refresh).mockRejectedValue(expired())
    const auth = useAuthStore()
    await auth.restoreSession()
    expect(auth.isAuthenticated).toBe(false)
    expect(auth.initialized).toBe(true)
    expect(authApi.me).not.toHaveBeenCalled()
  })

  it('a failed refresh clears the session', async () => {
    const auth = useAuthStore()
    await auth.login('a', 'b')
    vi.mocked(authApi.refresh).mockRejectedValue(expired())
    expect(await auth.refresh()).toBe(false)
    expect(auth.accessToken).toBeNull()
    expect(auth.user).toBeNull()
  })

  it('logout clears the session even if the API call fails', async () => {
    vi.mocked(authApi.logout).mockRejectedValue(new Error('offline'))
    const auth = useAuthStore()
    await auth.login('a', 'b')
    await expect(auth.logout()).rejects.toThrow('offline')
    expect(auth.isAuthenticated).toBe(false)
  })

  it('runs signed-out handlers when a signed-in session ends', async () => {
    const auth = useAuthStore()
    const handler = vi.fn()
    const unsubscribe = auth.onSignedOut(handler)

    auth.clear() // not signed in yet: nothing to reset
    expect(handler).not.toHaveBeenCalled()

    await auth.login('a', 'b')
    await auth.logout()
    expect(handler).toHaveBeenCalledTimes(1)

    unsubscribe()
    await auth.login('a', 'b')
    auth.clear()
    expect(handler).toHaveBeenCalledTimes(1)
  })
})
