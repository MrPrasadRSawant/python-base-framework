/**
 * Security & audit module: the user activity log (who changed what, sign-ins,
 * refused attempts). Other modules link to it by route name with a query:
 *
 *   router.push({ name: 'user-activity', query: { entityType: 'users', entityId: id } })
 *   router.push({ name: 'user-activity', query: { actorId: userId } })
 */
export const ACTIVITY_PERMISSION = 'user_activity_logs:read'

export default {
  name: 'audit',
  routes: [
    {
      path: 'audit/activity',
      name: 'user-activity',
      component: () => import('./pages/UserActivityPage.vue'),
      meta: { title: 'User Activity', permission: ACTIVITY_PERMISSION },
    },
  ],
  menu: [
    {
      label: 'User Activity',
      group: 'Security & audit',
      groupIcon: 'shield',
      icon: 'manage_history',
      to: { name: 'user-activity' },
      permission: ACTIVITY_PERMISSION,
    },
  ],
}
