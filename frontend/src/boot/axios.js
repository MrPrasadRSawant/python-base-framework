import { defineBoot } from '#q-app'
import axios from 'axios'

// Shared axios instance pointed at the FastAPI backend.
// Base URL comes from QCLI_API_BASE_URL in frontend/.env
const api = axios.create({
  baseURL: import.meta.env.QCLI_API_BASE_URL,
  timeout: 10000,
})

export default defineBoot(({ app }) => {
  app.config.globalProperties.$axios = axios
  app.config.globalProperties.$api = api
})

export { api }
