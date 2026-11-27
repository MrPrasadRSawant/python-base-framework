export { rolesApi, listPermissions } from './api.js'

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
      group: 'Access management',
      groupIcon: 'manage_accounts',
      icon: 'admin_panel_settings',
      to: { name: 'roles' },
      permission: 'roles:read',
    },
  ],
}
