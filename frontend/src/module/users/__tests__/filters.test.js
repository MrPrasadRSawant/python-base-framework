import { describe, expect, it } from 'vitest'

import { buildUserFilters } from '../filters.js'

describe('user advanced filters', () => {
  it('combines text and disabled account conditions', () => {
    expect(
      buildUserFilters([
        { field: 'email', op: 'ends_with', value: ' example.com ' },
        { field: 'is_active', op: 'eq', value: false },
      ]),
    ).toEqual([
      { field: 'email', op: 'ends_with', value: 'example.com' },
      { field: 'is_active', op: 'eq', value: false },
    ])
  })

  it('includes the entire selected end date', () => {
    expect(buildUserFilters([{ field: 'created_on', op: 'lte', value: '2026-11-27' }])).toEqual([
      { field: 'created_on', op: 'lt', value: new Date('2026-11-28T00:00:00').toISOString() },
    ])
  })

  it('supports users who have never signed in', () => {
    expect(buildUserFilters([{ field: 'last_login_on', op: 'is_null', value: '' }])).toEqual([
      { field: 'last_login_on', op: 'is_null', value: true },
    ])
  })

  it('rejects incomplete or invalid conditions', () => {
    expect(() => buildUserFilters([{ field: 'full_name', op: 'contains', value: ' ' }])).toThrow(
      'Enter a value for Name.',
    )
    expect(() =>
      buildUserFilters([{ field: 'created_on', op: 'gte', value: '2026-02-30' }]),
    ).toThrow('Choose a valid date.')
  })
})
