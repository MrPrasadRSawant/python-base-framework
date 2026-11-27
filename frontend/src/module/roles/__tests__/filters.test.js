import { describe, expect, it } from 'vitest'

import { buildRoleFilters } from '../filters.js'

describe('role advanced filters', () => {
  it('combines role code and custom type', () => {
    expect(
      buildRoleFilters([
        { field: 'code', op: 'starts_with', value: ' support_' },
        { field: 'is_system', op: 'eq', value: false },
      ]),
    ).toEqual([
      { field: 'code', op: 'starts_with', value: 'support_' },
      { field: 'is_system', op: 'eq', value: false },
    ])
  })

  it('uses a full local day for the created date', () => {
    expect(buildRoleFilters([{ field: 'created_on', op: 'lte', value: '2026-11-27' }])).toEqual([
      { field: 'created_on', op: 'lt', value: new Date('2026-11-28T00:00:00').toISOString() },
    ])
  })
})
