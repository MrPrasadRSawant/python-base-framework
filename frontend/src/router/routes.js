import { appRoutes, publicRoutes } from '@/module'

// Routes are contributed by the modules (src/module/*). Only the shell lives here.
const routes = [
  ...publicRoutes,

  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    children: [
      {
        path: '',
        name: 'home',
        component: () => import('@/pages/HomePage.vue'),
        meta: { title: 'Overview' },
      },
      {
        path: 'forbidden',
        name: 'forbidden',
        component: () => import('@/pages/ForbiddenPage.vue'),
        meta: { title: 'No access' },
      },
      ...appRoutes,
    ],
  },

  // Always last.
  {
    path: '/:catchAll(.*)*',
    component: () => import('@/pages/ErrorNotFound.vue'),
    meta: { public: true, title: 'Not found' },
  },
]

export default routes
