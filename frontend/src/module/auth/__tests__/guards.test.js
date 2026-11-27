import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { installAuthGuards, safeRedirect } from '../guards.js'

const Page = { render: () => null }

function setup({ signedIn = false, permissions = [] } = {}) {
  const auth = {
    isAuthenticated: signedIn,
    restoreSession: vi.fn().mockResolvedValue(),
    can: (codes) => [codes].flat().every((c) => permissions.includes(c)),
  }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', name: 'login', component: Page, meta: { public: true } },
      { path: '/', name: 'home', component: Page },
      { path: '/forbidden', name: 'forbidden', component: Page },
      { path: '/users', name: 'users', component: Page, meta: { permission: 'users:read' } },
      {
        path: '/admin',
        component: Page,
        meta: { permission: 'roles:read' },
        children: [
          { path: 'keys', name: 'keys', component: Page, meta: { permission: 'api_clients:read' } },
        ],
      },
      { path: '/:all(.*)*', name: 'not-found', component: Page, meta: { public: true } },
    ],
  })
  installAuthGuards(router, auth)
  return { router, auth }
}

async function go(router, path) {
  await router.push(path)
  return router.currentRoute.value
}

describe('auth guards', () => {
  it('restores the session before deciding', async () => {
    const { router, auth } = setup()
    await go(router, '/login')
    expect(auth.restoreSession).toHaveBeenCalled()
  })

  it('sends signed-out users to login with a redirect back', async () => {
    const { router } = setup()
    const route = await go(router, '/users?tab=2')
    expect(route.name).toBe('login')
    expect(route.query.redirect).toBe('/users?tab=2')
  })

  it('lets anyone open public routes', async () => {
    const { router } = setup()
    expect((await go(router, '/no/such/page')).name).toBe('not-found')
  })

  it('allows signed-in users with the permission', async () => {
    const { router } = setup({ signedIn: true, permissions: ['users:read'] })
    expect((await go(router, '/users')).name).toBe('users')
  })

  it('sends users without the permission to forbidden', async () => {
    const { router } = setup({ signedIn: true })
    const route = await go(router, '/users')
    expect(route.name).toBe('forbidden')
    expect(route.query.from).toBe('/users')
  })

  it('requires the permissions of parent routes too', async () => {
    const { router } = setup({ signedIn: true, permissions: ['api_clients:read'] })
    expect((await go(router, '/admin/keys')).name).toBe('forbidden')
    const { router: r2 } = setup({
      signedIn: true,
      permissions: ['api_clients:read', 'roles:read'],
    })
    expect((await go(r2, '/admin/keys')).name).toBe('keys')
  })

  it('moves signed-in users away from the login page', async () => {
    const { router } = setup({ signedIn: true, permissions: ['users:read'] })
    expect((await go(router, '/login?redirect=/users')).name).toBe('users')
  })
})

describe('safeRedirect', () => {
  it('only follows in-app paths', () => {
    expect(safeRedirect('/users?x=1')).toBe('/users?x=1')
    expect(safeRedirect('https://evil.example')).toBe('/')
    expect(safeRedirect('//evil.example')).toBe('/')
    expect(safeRedirect(undefined)).toBe('/')
  })
})
