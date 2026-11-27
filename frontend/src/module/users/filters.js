import { buildSearchFilters } from '@/components/advancedFilters.js'

export const USER_FILTER_FIELDS = [
  { label: 'Username', value: 'username', type: 'text' },
  { label: 'Name', value: 'full_name', type: 'text' },
  { label: 'Email', value: 'email', type: 'text' },
  {
    label: 'Account status',
    value: 'is_active',
    type: 'boolean',
    options: [
      { label: 'Enabled', value: true },
      { label: 'Disabled', value: false },
    ],
  },
  {
    label: 'Admin lock',
    value: 'is_locked',
    type: 'boolean',
    options: [
      { label: 'Locked', value: true },
      { label: 'Unlocked', value: false },
    ],
  },
  { label: 'Created date', value: 'created_on', type: 'date' },
  { label: 'Last sign-in', value: 'last_login_on', type: 'nullable-date' },
]

export function buildUserFilters(conditions) {
  return buildSearchFilters(conditions, USER_FILTER_FIELDS)
}
