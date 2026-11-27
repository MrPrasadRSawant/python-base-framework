// Auth pages use their own layout (no menu), so they are top-level routes.
export const publicRoutes = [
  {
    path: '/login',
    component: () => import('./layouts/AuthLayout.vue'),
    meta: { public: true },
    children: [
      {
        path: '',
        name: 'login',
        component: () => import('./pages/LoginPage.vue'),
        meta: { public: true, title: 'Sign in' },
      },
    ],
  },
]
