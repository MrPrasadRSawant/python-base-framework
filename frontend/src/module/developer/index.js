export default {
  name: 'developer',
  routes: [
    {
      path: 'developer/exceptions',
      name: 'exception-analysis',
      component: () => import('./pages/ExceptionAnalysisPage.vue'),
      meta: { title: 'Exception Analysis', permission: 'exception_logs:read' },
    },
    {
      path: 'developer/requests',
      name: 'request-lifecycle',
      component: () => import('./pages/RequestLifecyclePage.vue'),
      meta: { title: 'Request Lifecycle', permission: 'request_logs:read' },
    },
    {
      path: 'developer/permissions',
      name: 'permission-management',
      component: () => import('./pages/PermissionManagementPage.vue'),
      meta: { title: 'Permission Management', permission: 'roles:read' },
    },
  ],
  menu: [
    {
      label: 'Exception Analysis',
      group: 'Developer tools',
      groupIcon: 'developer_board',
      icon: 'monitor_heart',
      to: { name: 'exception-analysis' },
      permission: 'exception_logs:read',
    },
    {
      label: 'Request Lifecycle',
      group: 'Developer tools',
      groupIcon: 'developer_board',
      icon: 'timeline',
      to: { name: 'request-lifecycle' },
      permission: 'request_logs:read',
    },
    {
      label: 'Permission Management',
      group: 'Developer tools',
      groupIcon: 'developer_board',
      icon: 'verified_user',
      to: { name: 'permission-management' },
      permission: 'roles:read',
    },
  ],
}
