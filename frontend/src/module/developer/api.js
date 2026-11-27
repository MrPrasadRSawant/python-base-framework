import { createResource, http } from '@/api'

export const exceptionsApi = createResource('/exception-logs')

export const requestReportsApi = {
  async search(body) {
    const { data } = await http.post('/requests/report', body)
    return data
  },

  async get(requestId) {
    const { data } = await http.get(`/requests/${requestId}/report`)
    return data.record
  },
}

export async function getException(id) {
  const { data } = await http.get(`/exception-logs/${id}`)
  return data.record
}
