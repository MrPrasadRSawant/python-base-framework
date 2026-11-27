import { createResource, http } from '@/api'

const resource = createResource('/roles')

export const rolesApi = {
  ...resource,

  async setPermissions(id, permissions) {
    const { data } = await http.put(`/roles/${id}/permissions`, { permissions })
    return data.record
  },
}

export async function listPermissions() {
  const permissions = []
  let offset = 0
  let hasMore = true

  while (hasMore) {
    const { data } = await http.get('/permissions', { params: { limit: 100, offset } })
    permissions.push(...data.records)
    hasMore = data.metadata.has_more && data.records.length > 0
    offset = data.metadata.next_offset ?? offset + data.records.length
  }

  return permissions
}
