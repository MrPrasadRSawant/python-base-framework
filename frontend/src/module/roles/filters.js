import { buildSearchFilters } from '@/components/advancedFilters.js'

export const ROLE_FILTER_FIELDS = [
  { label: 'Role name', value: 'name', type: 'text' },
  { label: 'Code', value: 'code', type: 'text' },
  {
    label: 'Role type',
    value: 'is_system',
    type: 'boolean',
    options: [
      { label: 'System', value: true },
      { label: 'Custom', value: false },
    ],
  },
  { label: 'Created date', value: 'created_on', type: 'date' },
]

export function buildRoleFilters(conditions) {
  return buildSearchFilters(conditions, ROLE_FILTER_FIELDS)
}
