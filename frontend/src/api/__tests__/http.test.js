import { AxiosError } from 'axios'
import { beforeEach, describe, expect, it } from 'vitest'

import { ApiError, toApiError } from '../errors.js'
import { configureAuth, http } from '../http.js'

/**
 * Fake backend: `routes` maps "METHOD /path" to a handler(config) returning
 * [status, body]. Every request is recorded in `calls`.
 */
let routes
let calls

function errorBody(code, message = code) {
  return { metadata: { request_id: 'rid-1' }, error: { code, message } }
}

http.defaults.adapter = async (config) => {
  const key = `${config.method.toUpperCase()} ${config.url}`
  calls.push({ key, authorization: config.headers.Authorization })
  const handler = routes[key]
  if (!handler) throw new Error(`no fake route for ${key}`)
  const [status, data, headers = {}] = await handler(config)
  const response = { status, statusText: String(status), data, headers, config }
  if (status >= 400) {
    throw new AxiosError(`HTTP ${status}`, 'ERR_BAD_RESPONSE', config, null, response)
  }
  return response
}

let token
let refreshCount
let sessionEnded

beforeEach(() => {
  routes = {}
  calls = []
  token = 'old'
  refreshCount = 0
  sessionEnded = 0
  configureAuth({
    getToken: () => token,
    refresh: async () => {
      refreshCount += 1
      token = 'new'
      return true
    },
    onSessionEnded: () => {
      sessionEnded += 1
    },
  })
})

// The token is accepted only when it is the new one.
function protectedRoute() {
  return (config) =>
    config.headers.Authorization === 'Bearer new'
      ? [200, { record: 'ok' }]
      : [401, errorBody('token_expired')]
}

describe('http', () => {
  it('sends the access token', async () => {
    token = 'new'
    routes['GET /things'] = protectedRoute()
    await http.get('/things')
    expect(calls[0].authorization).toBe('Bearer new')
  })

  it('does not send the token with skipAuth', async () => {
    routes['POST /auth/login'] = () => [200, {}]
    await http.post('/auth/login', {}, { skipAuth: true })
    expect(calls[0].authorization).toBeUndefined()
  })

  it('refreshes once on token_expired and retries', async () => {
    routes['GET /things'] = protectedRoute()
    const { data } = await http.get('/things')
    expect(data.record).toBe('ok')
    expect(refreshCount).toBe(1)
    expect(calls.map((c) => c.authorization)).toEqual(['Bearer old', 'Bearer new'])
  })

  it('shares one refresh between parallel requests', async () => {
    routes['GET /a'] = protectedRoute()
    routes['GET /b'] = protectedRoute()
    routes['GET /c'] = protectedRoute()
    await Promise.all([http.get('/a'), http.get('/b'), http.get('/c')])
    expect(refreshCount).toBe(1)
  })

  it('ends the session when the refresh fails', async () => {
    configureAuth({ refresh: async () => false })
    routes['GET /things'] = protectedRoute()
    await expect(http.get('/things')).rejects.toMatchObject({ status: 401, code: 'token_expired' })
    expect(sessionEnded).toBe(1)
  })

  it('retries only once', async () => {
    routes['GET /things'] = () => [401, errorBody('token_expired')]
    await expect(http.get('/things')).rejects.toBeInstanceOf(ApiError)
    expect(calls).toHaveLength(2)
    expect(refreshCount).toBe(1)
  })

  it('does not refresh with skipAuthRefresh or for other errors', async () => {
    routes['POST /auth/refresh'] = () => [401, errorBody('invalid_refresh_token')]
    routes['GET /forbidden'] = () => [403, errorBody('forbidden')]
    await expect(http.post('/auth/refresh', null, { skipAuthRefresh: true })).rejects.toMatchObject(
      { code: 'invalid_refresh_token' },
    )
    await expect(http.get('/forbidden')).rejects.toMatchObject({ status: 403, code: 'forbidden' })
    expect(refreshCount).toBe(0)
    expect(sessionEnded).toBe(0)
  })
})

describe('ApiError', () => {
  it('is built from the error envelope', () => {
    const err = toApiError({
      response: {
        status: 429,
        data: errorBody('rate_limited', 'Too many'),
        headers: { 'retry-after': '30' },
      },
    })
    expect(err).toMatchObject({
      status: 429,
      code: 'rate_limited',
      message: 'Too many',
      requestId: 'rid-1',
      retryAfter: 30,
    })
  })

  it('reports network errors and timeouts', () => {
    expect(toApiError(new Error('down'))).toMatchObject({ status: 0, code: 'network_error' })
    expect(toApiError({ code: 'ECONNABORTED' })).toMatchObject({ code: 'timeout' })
  })

  it('maps 422 details to field errors', () => {
    const err = new ApiError({
      status: 422,
      code: 'validation_error',
      message: 'Invalid',
      details: [
        { loc: ['body', 'email'], msg: 'not an email' },
        { loc: ['body', 'password'], msg: 'too short' },
      ],
    })
    expect(err.fieldErrors).toEqual({ email: 'not an email', password: 'too short' })
  })
})
