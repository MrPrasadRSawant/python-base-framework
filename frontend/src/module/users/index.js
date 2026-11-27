export default {
  name: 'users',
  routes: [
    {
      path: 'users',
      name: 'users',
      component: () => import('./pages/UsersPage.vue'),
      meta: { title: 'User Management', permission: 'users:read' },
    },
  ],
  menu: [
    {
      label: 'User Management',
      group: 'Access management',
      groupIcon: 'manage_accounts',
      icon: 'group',
      to: { name: 'users' },
      permission: 'users:read',
    },
  ],
}
