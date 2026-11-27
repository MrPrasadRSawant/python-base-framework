<template>
  <q-dialog :model-value="modelValue" :persistent="saving" @update:model-value="close">
    <q-card class="manage-roles">
      <div class="manage-roles__header">
        <div class="manage-roles__identity">
          <div class="manage-roles__icon" aria-hidden="true">
            <q-icon name="admin_panel_settings" size="22px" />
          </div>
          <div>
            <h2>Manage user roles</h2>
            <p>
              {{ user?.full_name }} <span v-if="user?.email">· {{ user.email }}</span>
            </p>
          </div>
        </div>
        <q-btn
          flat
          round
          dense
          icon="close"
          aria-label="Close role assignment"
          :disable="saving"
          @click="close(false)"
        />
      </div>

      <div class="manage-roles__body">
        <q-banner v-if="error" rounded class="bg-negative text-white q-mb-md">
          <template #avatar><q-icon name="error_outline" /></template>
          {{ error }}
          <template v-if="!userDetail" #action>
            <q-btn flat dense no-caps color="white" label="Retry" @click="emit('retry')" />
          </template>
        </q-banner>

        <div class="manage-roles__intro">
          Choose the roles this user should have. Saving replaces their current role assignment.
        </div>

        <div v-if="loading" class="manage-roles__loading">
          <q-spinner color="primary" size="28px" />
          <span>Loading roles…</span>
        </div>
        <template v-else-if="userDetail">
          <div class="manage-roles__list-heading">
            <span>Available roles</span>
            <span class="manage-roles__count">{{ selected.length }} selected</span>
          </div>
          <q-input
            v-model="query"
            dense
            outlined
            clearable
            placeholder="Find a role"
            aria-label="Find a role"
            class="manage-roles__search"
          >
            <template #prepend><q-icon name="search" /></template>
          </q-input>

          <div v-if="visibleRoles.length" class="manage-roles__list">
            <div
              v-for="role in visibleRoles"
              :key="role.code"
              class="manage-roles__option"
              :class="{ 'manage-roles__option--selected': selected.includes(role.code) }"
              @click="toggleRole(role.code)"
            >
              <q-checkbox
                :model-value="selected.includes(role.code)"
                :aria-label="role.name"
                :disable="saving"
                @update:model-value="toggleRole(role.code)"
                @click.stop
              />
              <span class="manage-roles__option-copy">
                <span class="manage-roles__option-name">{{ role.name }}</span>
                <span class="manage-roles__option-code">{{ role.code }}</span>
                <span v-if="role.description" class="manage-roles__option-description">{{
                  role.description
                }}</span>
              </span>
              <AppStatusChip v-if="role.is_system" status="system" label="System" />
            </div>
          </div>
          <div v-else class="manage-roles__empty">
            {{ query ? 'No roles match your search.' : 'No roles are available.' }}
          </div>
          <div class="manage-roles__hint">
            A user with no roles can sign in but has no module access. New access applies after
            their token refreshes.
          </div>
        </template>
      </div>

      <div class="manage-roles__footer">
        <span class="manage-roles__footer-note">{{
          userDetail ? `${selected.length} role${selected.length === 1 ? '' : 's'} selected` : ''
        }}</span>
        <q-space />
        <q-btn flat no-caps label="Cancel" :disable="saving" @click="close(false)" />
        <q-btn
          color="primary"
          unelevated
          no-caps
          label="Save roles"
          :loading="saving"
          :disable="!userDetail || loading || unchanged"
          @click="emit('save', [...selected])"
        />
      </div>
    </q-card>
  </q-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

import AppStatusChip from '@/components/AppStatusChip.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  user: { type: Object, default: null },
  userDetail: { type: Object, default: null },
  roles: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  error: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'retry', 'save'])

const selected = ref([])
const query = ref('')
const visibleRoles = computed(() => {
  const term = query.value?.trim().toLowerCase()
  return term
    ? props.roles.filter((role) =>
        [role.name, role.code, role.description].some((value) =>
          value?.toLowerCase().includes(term),
        ),
      )
    : props.roles
})
const unchanged = computed(
  () =>
    [...selected.value].sort().join('|') === [...(props.userDetail?.roles || [])].sort().join('|'),
)

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      query.value = ''
      selected.value = []
    }
  },
)
watch(
  () => props.userDetail,
  (detail) => {
    if (props.modelValue && detail) selected.value = [...detail.roles]
  },
)

function close(value = false) {
  emit('update:modelValue', value)
}

function toggleRole(code) {
  if (props.saving) return
  selected.value = selected.value.includes(code)
    ? selected.value.filter((item) => item !== code)
    : [...selected.value, code]
}
</script>

<style scoped lang="scss">
.manage-roles {
  display: flex;
  flex-direction: column;
  width: 680px;
  max-width: calc(100vw - 32px);
  max-height: min(760px, calc(100vh - 32px));
  border-radius: var(--app-radius-lg);
}

.manage-roles__header,
.manage-roles__footer {
  display: flex;
  align-items: center;
  gap: var(--app-space-md);
  flex: none;
  padding: var(--app-space-md) var(--app-space-lg);
  background: var(--app-surface);
}

.manage-roles__header {
  justify-content: space-between;
  border-bottom: 1px solid var(--app-border);
}

.manage-roles__identity {
  display: flex;
  align-items: center;
  gap: var(--app-space-sm);
  min-width: 0;
}

.manage-roles__icon {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  flex: none;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  color: var(--app-primary);
}

.manage-roles h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
}

.manage-roles p {
  overflow: hidden;
  margin: 2px 0 0;
  color: var(--app-text-muted);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.manage-roles__body {
  min-height: 0;
  overflow-y: auto;
  padding: var(--app-space-lg);
  background: var(--app-surface-muted);
}

.manage-roles__intro,
.manage-roles__hint,
.manage-roles__loading,
.manage-roles__empty,
.manage-roles__footer-note {
  color: var(--app-text-muted);
  font-size: 13px;
}

.manage-roles__loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--app-space-sm);
  min-height: 180px;
}

.manage-roles__list-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: var(--app-space-lg) 0 var(--app-space-sm);
  font-size: 13px;
  font-weight: 700;
}

.manage-roles__count {
  color: var(--app-text-muted);
  font-weight: 500;
}

.manage-roles__search {
  margin-bottom: var(--app-space-sm);
}

.manage-roles__list {
  display: grid;
  gap: var(--app-space-sm);
}

.manage-roles__option {
  display: flex;
  align-items: center;
  gap: var(--app-space-sm);
  padding: var(--app-space-sm);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  background: var(--app-surface);
  cursor: pointer;
}

.manage-roles__option--selected {
  border-color: var(--app-primary);
}

.manage-roles__option-copy {
  display: grid;
  min-width: 0;
}

.manage-roles__option-name {
  font-size: 13px;
  font-weight: 600;
}

.manage-roles__option-code,
.manage-roles__option-description {
  overflow: hidden;
  color: var(--app-text-muted);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.manage-roles__option .q-chip {
  margin-left: auto;
}

.manage-roles__empty {
  padding: var(--app-space-lg);
  border: 1px dashed var(--app-border);
  border-radius: var(--app-radius-md);
  text-align: center;
}

.manage-roles__hint {
  margin-top: var(--app-space-md);
}

.manage-roles__footer {
  border-top: 1px solid var(--app-border);
}

@media (max-width: 680px) {
  .manage-roles__header,
  .manage-roles__body,
  .manage-roles__footer {
    padding-right: var(--app-space-md);
    padding-left: var(--app-space-md);
  }

  .manage-roles__footer-note {
    display: none;
  }
}
</style>
