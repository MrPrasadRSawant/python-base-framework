<template>
  <q-page class="flex flex-center">
    <div class="column items-center q-gutter-md">
      <img
        alt="Quasar logo"
        src="~@/assets/quasar-logo-vertical.svg"
        style="width: 200px; height: 200px"
      />

      <div class="text-h6">{{ appName }}</div>

      <q-banner v-if="health" rounded class="bg-positive text-white">
        Backend: {{ health.status }} &middot; Database: {{ health.database }}
      </q-banner>
      <q-banner v-else-if="error" rounded class="bg-negative text-white">
        Backend unreachable: {{ error }}
      </q-banner>
      <q-spinner v-else color="primary" size="2em" />

      <q-btn color="primary" to="/second" label="Go to Second Page" no-caps />
    </div>
  </q-page>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '@/boot/axios'

const appName = import.meta.env.QCLI_APP_NAME
const health = ref(null)
const error = ref(null)

onMounted(async () => {
  try {
    const { data } = await api.get('/health')
    health.value = data
  } catch (err) {
    error.value = err.message
  }
})
</script>
