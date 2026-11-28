/**
 * Presentation rules for user activity rows (GET/POST /user-activity-logs).
 * Pure functions: no Vue, no API calls, so they are unit-tested directly.
 */

export const DATA_ACTIONS = ['create', 'update', 'delete', 'restore']
export const SIGN_IN_ACTIONS = [
  'login',
  'login_failed',
  'logout',
  'token_issued',
  'client_auth_failed',
  'session_revoked',
]

const ACTIONS = {
  create: { label: 'Created', icon: 'add_circle_outline' },
  update: { label: 'Updated', icon: 'edit' },
  delete: { label: 'Deleted', icon: 'delete_outline' },
  restore: { label: 'Restored', icon: 'restore' },
  login: { label: 'Signed in', icon: 'login' },
  login_failed: { label: 'Sign-in failed', icon: 'no_accounts' },
  logout: { label: 'Signed out', icon: 'logout' },
  token_issued: { label: 'API token issued', icon: 'key' },
  client_auth_failed: { label: 'API client refused', icon: 'key_off' },
  session_revoked: { label: 'Session revoked', icon: 'gpp_bad' },
  access_denied: { label: 'Access denied', icon: 'block' },
}

export function actionLook(action) {
  return ACTIONS[action] || { label: humanize(action), icon: 'bolt' }
}

/** Quick filter presets for the page toggle. */
export const QUICK_FILTERS = [
  { label: 'All activity', value: 'all' },
  { label: 'Data changes', value: 'changes' },
  { label: 'Sign-ins', value: 'sign_ins' },
  { label: 'Refused', value: 'refused' },
]

export function quickFilter(value) {
  if (value === 'changes') return [{ field: 'action', op: 'in', value: DATA_ACTIONS }]
  if (value === 'sign_ins') return [{ field: 'action', op: 'in', value: SIGN_IN_ACTIONS }]
  if (value === 'refused') return [{ field: 'status', op: 'eq', value: 'failed' }]
  return []
}

/** Filters from the page URL (?entityType=&entityId=&actorId=), set by History links. */
export function contextFilters({ entityType, entityId, actorId } = {}) {
  const out = []
  if (typeof entityType === 'string' && entityType) {
    out.push({ field: 'entity_type', op: 'eq', value: entityType })
  }
  if (typeof entityId === 'string' && entityId) {
    out.push({ field: 'entity_id', op: 'eq', value: entityId })
  }
  if (typeof actorId === 'string' && actorId) {
    out.push({ field: 'actor_id', op: 'eq', value: actorId })
  }
  return out
}

const ENTITY_LABELS = {
  users: 'User',
  roles: 'Role',
  permissions: 'Permission',
  user_roles: 'User role',
  role_permissions: 'Role permission',
  api_clients: 'API client',
  api_client_permissions: 'API client permission',
}

export function entityLabel(entityType) {
  if (!entityType) return ''
  return ENTITY_LABELS[entityType] || humanize(entityType)
}

export function shortId(id) {
  const text = String(id ?? '')
  return text.length > 12 ? `${text.slice(0, 8)}…` : text
}

/** Who did it, for display. `names` maps user ids to usernames when known. */
export function actorLabel(row, names = {}) {
  if (row.actor_type === 'user') return names[row.actor_id] || `User ${shortId(row.actor_id)}`
  if (row.actor_type === 'service') return `API client ${row.actor_id}`
  if (row.actor_type === 'anonymous') return 'Anonymous'
  return 'System'
}

export const REDACTED = '[REDACTED]'
const ISO_DATETIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'medium',
})

export function formatDateTime(value) {
  return value ? dateFormatter.format(new Date(value)) : '—'
}

/** One stored value as display text. */
export function formatValue(value) {
  if (value === null || value === undefined) return '—'
  if (value === REDACTED) return 'Hidden (sensitive)'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'string' && ISO_DATETIME.test(value)) {
    const date = new Date(value)
    return Number.isNaN(date.getTime()) ? value : formatDateTime(value)
  }
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

/** `changes` JSON -> rows for the before/after table, sorted by field. */
export function changeRows(changes) {
  if (!changes || typeof changes !== 'object') return []
  return Object.keys(changes)
    .sort()
    .map((field) => {
      const change = changes[field] || {}
      return {
        field,
        label: humanize(field),
        before: formatValue(change.old),
        after: formatValue(change.new),
        sensitive: change.old === REDACTED || change.new === REDACTED,
      }
    })
}

/** `details` JSON -> [{label, value}] for security events. */
export function detailRows(details) {
  if (!details || typeof details !== 'object') return []
  return Object.entries(details).map(([key, value]) => ({
    label: humanize(key),
    value: Array.isArray(value) ? value.join(', ') : formatValue(humanizeCode(key, value)),
  }))
}

function humanizeCode(key, value) {
  return (key === 'reason' || key === 'error_code') && typeof value === 'string'
    ? humanize(value)
    : value
}

export function humanize(text) {
  const words = String(text ?? '')
    .replace(/_/g, ' ')
    .trim()
  return words ? words[0].toUpperCase() + words.slice(1) : ''
}
