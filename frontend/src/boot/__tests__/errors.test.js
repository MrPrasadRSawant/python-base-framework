import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api'

// errors.js imports Quasar's Notify and the boot helper; only describeError is tested here.
vi.mock('quasar', () => ({ Notify: { create: vi.fn() } }))
vi.mock('#q-app', () => ({ defineBoot: (fn) => fn }))

const { describeError } = await import('../errors.js')

describe('describeError', () => {
  it('shows an ApiError message with its request id', () => {
    const err = new ApiError({
      status: 500,
      code: 'internal_error',
      message: 'Boom',
      requestId: 'r1',
    })
    expect(describeError(err)).toEqual({ message: 'Boom', caption: 'Request id: r1' })
  })

  it('hides internal details of other errors', () => {
    expect(describeError(new TypeError('x is undefined'))).toEqual({
      message: 'Something went wrong. Please try again.',
      caption: '',
    })
  })
})
