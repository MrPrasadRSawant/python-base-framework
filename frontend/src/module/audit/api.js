import { createResource, http } from '@/api'

/** /user-activity-logs: list, search, get (read-only). */
export const activityApi = createResource('/user-activity-logs')

/**
 * Usernames for user ids, as {id: username}. Needs users:read; callers check it.
 * Deleted users are included: the audit trail outlives the account.
 */
export async function usernamesFor(ids) {
  if (!ids.length) return {}
  const { data } = await http.post('/users/search', {
    filters: [{ field: 'id', op: 'in', value: ids }],
    limit: Math.min(ids.length, 100),
    include_total: false,
    include_deleted: true,
  })
  return Object.fromEntries(data.records.map((user) => [user.id, user.username]))
}
