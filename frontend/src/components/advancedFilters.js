export const MAX_FILTER_CONDITIONS = 20

const TEXT_OPERATORS = [
  { label: 'Contains', value: 'contains' },
  { label: 'Starts with', value: 'starts_with' },
  { label: 'Ends with', value: 'ends_with' },
  { label: 'Is exactly', value: 'eq' },
  { label: 'Is not', value: 'ne' },
]
const DATE_OPERATORS = [
  { label: 'On or after', value: 'gte' },
  { label: 'On or before', value: 'lte' },
]

export function operatorsFor(fieldName, fields) {
  const field = fields.find((item) => item.value === fieldName)
  if (field?.type === 'select')
    return TEXT_OPERATORS.filter((item) => ['eq', 'ne'].includes(item.value))
  if (field?.type === 'text') return TEXT_OPERATORS
  if (field?.type === 'boolean') return [{ label: 'Is', value: 'eq' }]
  if (field?.type === 'nullable-date') {
    return [
      ...DATE_OPERATORS,
      { label: 'Never', value: 'is_null' },
      { label: 'Has a date', value: 'is_not_null' },
    ]
  }
  return DATE_OPERATORS
}

export function newCondition(fields) {
  return { field: fields[0].value, op: operatorsFor(fields[0].value, fields)[0].value, value: '' }
}

function localDayStart(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) throw new Error('Choose a valid date.')
  const date = new Date(`${value}T00:00:00`)
  const [year, month, day] = value.split('-').map(Number)
  if (
    Number.isNaN(date.getTime()) ||
    date.getFullYear() !== year ||
    date.getMonth() + 1 !== month ||
    date.getDate() !== day
  ) {
    throw new Error('Choose a valid date.')
  }
  return date
}

export function buildSearchFilters(conditions, fields) {
  if (conditions.length > MAX_FILTER_CONDITIONS) throw new Error('Too many filter conditions.')
  return conditions.map((condition) => {
    const field = fields.find((item) => item.value === condition.field)
    if (!field) throw new Error('Choose a filter field.')
    if (!operatorsFor(field.value, fields).some((item) => item.value === condition.op)) {
      throw new Error(`Choose a valid condition for ${field.label}.`)
    }

    if (condition.op === 'is_null' || condition.op === 'is_not_null') {
      return { field: field.value, op: 'is_null', value: condition.op === 'is_null' }
    }
    if (field.type === 'boolean') {
      if (typeof condition.value !== 'boolean') throw new Error(`Choose ${field.label}.`)
      return { field: field.value, op: 'eq', value: condition.value }
    }
    if (field.type === 'select') {
      if (!field.options?.some((item) => item.value === condition.value)) {
        throw new Error(`Choose ${field.label}.`)
      }
      return { field: field.value, op: condition.op, value: condition.value }
    }
    if (field.type === 'date' || field.type === 'nullable-date') {
      const date = localDayStart(condition.value)
      if (condition.op === 'lte') {
        date.setDate(date.getDate() + 1)
        return { field: field.value, op: 'lt', value: date.toISOString() }
      }
      return { field: field.value, op: 'gte', value: date.toISOString() }
    }

    const value = condition.value?.trim()
    if (!value) throw new Error(`Enter a value for ${field.label}.`)
    return { field: field.value, op: condition.op, value }
  })
}
