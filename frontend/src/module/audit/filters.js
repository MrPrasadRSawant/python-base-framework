import { buildSearchFilters } from '@/components/advancedFilters.js'

export const ACTIVITY_FILTER_FIELDS = [
  {
    label: 'Action',
    value: 'action',
    type: 'select',
    options: [
      { label: 'Created', value: 'create' },
      { label: 'Updated', value: 'update' },
      { label: 'Deleted', value: 'delete' },
      { label: 'Restored', value: 'restore' },
      { label: 'Signed in', value: 'login' },
      { label: 'Sign-in failed', value: 'login_failed' },
      { label: 'Signed out', value: 'logout' },
      { label: 'API token issued', value: 'token_issued' },
      { label: 'API client refused', value: 'client_auth_failed' },
      { label: 'Session revoked', value: 'session_revoked' },
      { label: 'Access denied', value: 'access_denied' },
    ],
  },
  {
    label: 'Status',
    value: 'status',
    type: 'select',
    options: [
      { label: 'Successful', value: 'success' },
      { label: 'Failed', value: 'failed' },
    ],
  },
  {
    label: 'Actor type',
    value: 'actor_type',
    type: 'select',
    options: [
      { label: 'User', value: 'user' },
      { label: 'API client', value: 'service' },
      { label: 'Anonymous', value: 'anonymous' },
      { label: 'System', value: 'system' },
    ],
  },
  { label: 'Actor ID', value: 'actor_id', type: 'text' },
  { label: 'Record type', value: 'entity_type', type: 'text' },
  { label: 'Record ID', value: 'entity_id', type: 'text' },
  { label: 'IP address', value: 'ip_address', type: 'text' },
  { label: 'Route', value: 'route', type: 'text' },
  { label: 'Date', value: 'occurred_on', type: 'date' },
]

export function buildActivityFilters(conditions) {
  return buildSearchFilters(conditions, ACTIVITY_FILTER_FIELDS)
}
