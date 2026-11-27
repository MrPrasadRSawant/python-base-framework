/**
 * Generic client for a backend resource that follows the standard pattern:
 *
 *   GET    /<path>?limit=&offset=   list      -> {metadata, records}
 *   POST   /<path>/search           search    -> {metadata, records}
 *   GET    /<path>/{id}             get       -> record
 *   POST   /<path>                  create    -> record
 *   PATCH  /<path>/{id}             update    -> record
 *   DELETE /<path>/{id}             remove
 *
 *   export const usersApi = createResource('/users')
 *   const page = await usersApi.search({ search: 'ali', limit: 20 })
 *
 * Extra endpoints of a resource go in the module's own api.js, using `http`.
 */
import { http } from './http.js'

export function createResource(path) {
  return {
    path,

    async list({ limit, offset } = {}) {
      const { data } = await http.get(path, { params: { limit, offset } })
      return data
    },

    /** body: SearchRequest {search, filters, sort, limit, offset, include_total} */
    async search(body = {}) {
      const { data } = await http.post(`${path}/search`, body)
      return data
    },

    async get(id) {
      const { data } = await http.get(`${path}/${id}`)
      return data.record
    },

    async create(body) {
      const { data } = await http.post(path, body)
      return data.record
    },

    async update(id, body) {
      const { data } = await http.patch(`${path}/${id}`, body)
      return data.record
    },

    async remove(id) {
      await http.delete(`${path}/${id}`)
    },
  }
}
