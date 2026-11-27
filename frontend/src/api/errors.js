/**
 * Every failed API call rejects with an ApiError, built from the backend's
 * error envelope: {"metadata": {request_id}, "error": {code, message, details}}.
 *
 *   try { await usersApi.create(form) }
 *   catch (err) { if (err.code === 'email_taken') ... }
 *
 * Branch on `code` (stable), show `message` (human readable).
 */
export class ApiError extends Error {
  constructor({ status, code, message, details = null, requestId = null, retryAfter = null }) {
    super(message)
    this.name = 'ApiError'
    this.status = status // HTTP status, 0 = network error / no response
    this.code = code // backend error.code, e.g. "invalid_credentials"
    this.details = details // backend error.details (field errors, missing permissions...)
    this.requestId = requestId // quote it when reporting a problem
    this.retryAfter = retryAfter // seconds, on 429 rate_limited
  }

  /** Field errors from a 422 as {fieldName: message}, for form validation. */
  get fieldErrors() {
    const out = {}
    for (const item of Array.isArray(this.details) ? this.details : []) {
      const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : null
      if (field && !out[field]) out[field] = item.msg
    }
    return out
  }
}

/** Convert anything axios throws into an ApiError. */
export function toApiError(err) {
  if (err instanceof ApiError) return err
  const response = err?.response
  if (!response) {
    return new ApiError({
      status: 0,
      code: err?.code === 'ECONNABORTED' ? 'timeout' : 'network_error',
      message: 'Cannot reach the server. Check your connection and try again.',
    })
  }
  const body = response.data || {}
  const error = body.error || {}
  return new ApiError({
    status: response.status,
    code: error.code || `http_${response.status}`,
    message: error.message || response.statusText || 'Request failed.',
    details: error.details ?? null,
    requestId: body.metadata?.request_id || response.headers?.['x-request-id'] || null,
    retryAfter: Number(response.headers?.['retry-after']) || null,
  })
}
