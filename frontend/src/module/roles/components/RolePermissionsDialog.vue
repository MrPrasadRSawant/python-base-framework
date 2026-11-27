<template>
  <q-dialog :model-value="modelValue" :persistent="saving" @update:model-value="close">
    <q-card class="role-permissions">
      <div class="role-permissions__header">
        <div class="role-permissions__identity">
          <div class="role-permissions__icon" aria-hidden="true">
            <q-icon name="verified_user" size="22px" />
          </div>
          <div>
            <h2>{{ editable ? 'Manage permissions' : 'Role permissions' }}</h2>
            <p>
              {{ role?.name }} <span v-if="role?.code">· {{ role.code }}</span>
            </p>
          </div>
        </div>
        <q-btn
          flat
          round
          dense
          icon="close"
          aria-label="Close permissions"
          :disable="saving"
          @click="close(false)"
        />
      </div>

      <div class="role-permissions__body">
        <div class="role-permissions__intro">
          {{
            role?.is_system
              ? 'System role permissions are maintained by the application.'
              : editable
                ? 'Choose the access this role grants. Changes take effect when users receive a new access token.'
                : 'View the access granted by this role.'
          }}
        </div>

        <div v-if="groups.length" class="role-permissions__groups">
          <section v-for="group in groups" :key="group.key" class="role-permissions__group">
            <h3>{{ group.label }}</h3>
            <div
              v-for="permission in group.items"
              :key="permission.code"
              class="role-permissions__item"
            >
              <q-checkbox
                v-model="selected"
                :val="permission.code"
                :label="permission.code"
                :disable="!editable || !grantableCodes.includes(permission.code)"
                dense
              />
              <div class="role-permissions__description">
                {{ permission.description || 'No description' }}
              </div>
            </div>
          </section>
        </div>
        <div v-else class="role-permissions__empty">No permissions are available.</div>
      </div>

      <div class="role-permissions__footer">
        <span v-if="editable" class="role-permissions__note">
          Permissions you do not hold are shown but cannot be changed.
        </span>
        <q-space />
        <q-btn
          flat
          no-caps
          :label="editable ? 'Cancel' : 'Close'"
          :disable="saving"
          @click="close(false)"
        />
        <q-btn
          v-if="editable"
          color="primary"
          unelevated
          no-caps
          label="Save permissions"
          :disable="unchanged"
          :loading="saving"
          @click="emit('save', [...selected])"
        />
      </div>
    </q-card>
  </q-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  role: { type: Object, default: null },
  catalog: { type: Array, default: () => [] },
  canManage: { type: Boolean, default: false },
  grantableCodes: { type: Array, default: () => [] },
  saving: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'save'])

const selected = ref([])
const editable = computed(() => props.canManage && !props.role?.is_system)
const unchanged = computed(
  () =>
    [...selected.value].sort().join('|') === [...(props.role?.permissions || [])].sort().join('|'),
)
const groups = computed(() => {
  const byResource = new Map()
  for (const permission of props.catalog) {
    const resource = permission.code.split(':')[0]
    if (!byResource.has(resource)) {
      byResource.set(resource, {
        key: resource,
        label: resource.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()),
        items: [],
      })
    }
    byResource.get(resource).items.push(permission)
  }
  return [...byResource.values()]
})

watch(
  () => props.modelValue,
  (open) => {
    if (open) selected.value = [...(props.role?.permissions || [])]
  },
)

function close(value = false) {
  emit('update:modelValue', value)
}
</script>

<style scoped lang="scss">
.role-permissions {
  display: flex;
  flex-direction: column;
  width: 800px;
  max-width: calc(100vw - 32px);
  max-height: min(780px, calc(100vh - 32px));
  border-radius: var(--app-radius-lg);
}

.role-permissions__header,
.role-permissions__footer {
  display: flex;
  align-items: center;
  gap: var(--app-space-md);
  flex: none;
  padding: var(--app-space-md) var(--app-space-lg);
  background: var(--app-surface);
}

.role-permissions__header {
  justify-content: space-between;
  border-bottom: 1px solid var(--app-border);
}

.role-permissions__identity {
  display: flex;
  align-items: center;
  gap: var(--app-space-sm);
}

.role-permissions__icon {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  flex: none;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  color: var(--app-primary);
}

.role-permissions h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
}

.role-permissions p {
  margin: 2px 0 0;
  color: var(--app-text-muted);
  font-size: 13px;
}

.role-permissions__body {
  min-height: 0;
  overflow-y: auto;
  padding: var(--app-space-lg);
  background: var(--app-surface-muted);
}

.role-permissions__intro,
.role-permissions__note,
.role-permissions__empty {
  color: var(--app-text-muted);
  font-size: 13px;
}

.role-permissions__groups {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--app-space-md);
  margin-top: var(--app-space-md);
}

.role-permissions__group {
  padding: var(--app-space-md);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  background: var(--app-surface);
}

.role-permissions h3 {
  margin: 0 0 var(--app-space-sm);
  font-size: 13px;
  font-weight: 700;
}

.role-permissions__item + .role-permissions__item {
  margin-top: var(--app-space-md);
}

.role-permissions__description {
  margin-left: 32px;
  color: var(--app-text-muted);
  font-size: 12px;
}

.role-permissions__footer {
  border-top: 1px solid var(--app-border);
}

@media (max-width: 680px) {
  .role-permissions__header,
  .role-permissions__body,
  .role-permissions__footer {
    padding-right: var(--app-space-md);
    padding-left: var(--app-space-md);
  }

  .role-permissions__groups {
    grid-template-columns: minmax(0, 1fr);
  }

  .role-permissions__note {
    display: none;
  }
}
</style>
