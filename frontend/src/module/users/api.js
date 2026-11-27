import { createResource, http } from '@/api'

const resource = createResource('/users')

export const usersApi = {
  ...resource,

  async setLocked(id, locked) {
    const { data } = await http.put(`/users/${id}/lock`, { locked })
    return data.record
  },

  async setRoles(id, roles) {
    const { data } = await http.put(`/users/${id}/roles`, { roles })
    return data.record
  },
}

export async function listRoles() {
  const roles = []
  let offset = 0
  let hasMore = true

  while (hasMore) {
    const { data } = await http.get('/roles', { params: { limit: 100, offset } })
    roles.push(...data.records)
    hasMore = data.metadata.has_more && data.records.length > 0
    offset = data.metadata.next_offset ?? offset + data.records.length
  }

  return roles
}
