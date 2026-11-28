import { describe, expect, it } from 'vitest'

import {
  actionLook,
  actorLabel,
  changeRows,
  contextFilters,
  DATA_ACTIONS,
  detailRows,
  entityLabel,
  formatValue,
  quickFilter,
  REDACTED,
  shortId,
} from '../activity.js'
import { buildActivityFilters } from '../filters.js'

describe('quick filters', () => {
  it('maps each preset to backend search filters', () => {
    expect(quickFilter('all')).toEqual([])
    expect(quickFilter('changes')).toEqual([{ field: 'action', op: 'in', value: DATA_ACTIONS }])
    expect(quickFilter('sign_ins')[0]).toMatchObject({ field: 'action', op: 'in' })
    expect(quickFilter('sign_ins')[0].value).toContain('login_failed')
    expect(quickFilter('refused')).toEqual([{ field: 'status', op: 'eq', value: 'failed' }])
  })
})

describe('context filters from the URL', () => {
  it('builds record-history and actor filters', () => {
    expect(contextFilters({ entityType: 'users', entityId: 'u-1' })).toEqual([
      { field: 'entity_type', op: 'eq', value: 'users' },
      { field: 'entity_id', op: 'eq', value: 'u-1' },
    ])
    expect(contextFilters({ actorId: 'u-2' })).toEqual([
      { field: 'actor_id', op: 'eq', value: 'u-2' },
    ])
  })

  it('ignores missing or repeated (array) query values', () => {
    expect(contextFilters({})).toEqual([])
    expect(contextFilters({ entityType: ['users', 'roles'], actorId: '' })).toEqual([])
  })
})

describe('labels', () => {
  it('describes actors', () => {
    const user = { actor_type: 'user', actor_id: '0192f5f0-aaaa-7000-8000-000000000001' }
    expect(actorLabel(user, { [user.actor_id]: 'Admin' })).toBe('Admin')
    expect(actorLabel(user)).toBe('User 0192f5f0…')
    expect(actorLabel({ actor_type: 'service', actor_id: 'cli_1' })).toBe('API client cli_1')
    expect(actorLabel({ actor_type: 'anonymous' })).toBe('Anonymous')
    expect(actorLabel({ actor_type: 'system' })).toBe('System')
  })

  it('describes actions and record types, with fallbacks', () => {
    expect(actionLook('login_failed').label).toBe('Sign-in failed')
    expect(actionLook('export_downloaded')).toEqual({ label: 'Export downloaded', icon: 'bolt' })
    expect(entityLabel('user_roles')).toBe('User role')
    expect(entityLabel('purchase_orders')).toBe('Purchase orders')
    expect(shortId('42')).toBe('42')
  })
})

describe('before/after values', () => {
  it('formats changes as sorted rows and flags sensitive values', () => {
    const rows = changeRows({
      password_hash: { old: REDACTED, new: REDACTED },
      full_name: { old: 'Dana', new: 'Dana S' },
      is_active: { old: true, new: false },
    })
    expect(rows.map((r) => r.field)).toEqual(['full_name', 'is_active', 'password_hash'])
    expect(rows[0]).toMatchObject({ label: 'Full name', before: 'Dana', after: 'Dana S' })
    expect(rows[1]).toMatchObject({ before: 'Yes', after: 'No', sensitive: false })
    expect(rows[2]).toMatchObject({ before: 'Hidden (sensitive)', sensitive: true })
  })

  it('shows created and deleted values with an empty side', () => {
    expect(changeRows({ code: { old: null, new: 'auditor' } })[0]).toMatchObject({
      before: '—',
      after: 'auditor',
    })
    expect(changeRows(null)).toEqual([])
  })

  it('formats objects, numbers and timestamps', () => {
    expect(formatValue(['10.0.0.0/8'])).toBe('["10.0.0.0/8"]')
    expect(formatValue(0)).toBe('0')
    expect(formatValue('2026-11-28T04:10:31+00:00')).not.toContain('T04')
  })

  it('formats security event details', () => {
    expect(
      detailRows({ reason: 'wrong_password', locked_out: true, missing_permissions: ['a', 'b'] }),
    ).toEqual([
      { label: 'Reason', value: 'Wrong password' },
      { label: 'Locked out', value: 'Yes' },
      { label: 'Missing permissions', value: 'a, b' },
    ])
  })
})

describe('advanced filters', () => {
  it('builds text and whole-day date conditions', () => {
    expect(
      buildActivityFilters([
        { field: 'ip_address', op: 'eq', value: ' 10.0.0.4 ' },
        { field: 'occurred_on', op: 'lte', value: '2026-11-27' },
      ]),
    ).toEqual([
      { field: 'ip_address', op: 'eq', value: '10.0.0.4' },
      { field: 'occurred_on', op: 'lt', value: new Date('2026-11-28T00:00:00').toISOString() },
    ])
  })

  it('rejects empty values', () => {
    expect(() => buildActivityFilters([{ field: 'action', op: 'eq', value: '' }])).toThrow(
      'Choose Action.',
    )
  })

  it('uses controlled choices for event filters', () => {
    expect(
      buildActivityFilters([
        { field: 'action', op: 'eq', value: 'login_failed' },
        { field: 'status', op: 'eq', value: 'failed' },
      ]),
    ).toEqual([
      { field: 'action', op: 'eq', value: 'login_failed' },
      { field: 'status', op: 'eq', value: 'failed' },
    ])
    expect(() => buildActivityFilters([{ field: 'status', op: 'eq', value: 'unknown' }])).toThrow(
      'Choose Status.',
    )
  })
})
