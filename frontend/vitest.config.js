import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'

// Unit tests for plain JS logic (api layer, stores, guards). Tests sit next to
// the code in __tests__/ folders: src/**/__tests__/*.test.js
export default defineConfig({
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  test: {
    environment: 'node',
    include: ['src/**/__tests__/**/*.test.js'],
    restoreMocks: true,
  },
})
