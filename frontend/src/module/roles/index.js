export default {
  name: 'roles',
  routes: [
    {
      path: 'roles',
      name: 'roles',
      component: () => import('./pages/RolesPage.vue'),
      meta: { title: 'Role Management', permission: 'roles:read' },
    },
  ],
  menu: [
    {
      label: 'Role Management',
      icon: 'admin_panel_settings',
      to: { name: 'roles' },
      permission: 'roles:read',
    },
  ],
}
