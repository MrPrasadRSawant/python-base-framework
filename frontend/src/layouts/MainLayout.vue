<template>
  <q-layout view="hHh Lpr lFf" class="app-shell">
    <q-header class="app-header">
      <q-toolbar class="app-header__toolbar">
        <q-btn
          class="app-header__menu"
          flat
          round
          dense
          :icon="compactDrawer ? 'menu_open' : 'menu'"
          :aria-label="menuToggleLabel"
          @click="toggleNavigation"
        >
          <q-tooltip>{{ menuToggleLabel }}</q-tooltip>
        </q-btn>
        <BrandLogo class="lt-md" compact />
        <div class="app-header__location gt-sm">
          <span class="app-header__section">Workspace</span>
          <q-icon name="chevron_right" size="17px" />
          <span class="app-header__current">{{ $route.meta.title || 'Overview' }}</span>
        </div>
        <q-space />
        <q-btn
          flat
          round
          dense
          :icon="$q.dark.isActive ? 'light_mode' : 'dark_mode'"
          :aria-label="$q.dark.isActive ? 'Switch to light theme' : 'Switch to dark theme'"
          @click="$q.dark.toggle()"
        >
          <q-tooltip>{{ $q.dark.isActive ? 'Light theme' : 'Dark theme' }}</q-tooltip>
        </q-btn>
        <span class="app-header__divider" aria-hidden="true" />
        <UserMenu />
      </q-toolbar>
    </q-header>

    <q-drawer
      v-model="drawerOpen"
      show-if-above
      bordered
      :breakpoint="1024"
      :width="248"
      :mini="compactDrawer"
      :mini-width="76"
      class="app-drawer"
    >
      <div class="app-drawer__body" :class="{ 'app-drawer__body--compact': compactDrawer }">
        <router-link
          class="app-drawer__brand"
          :to="{ name: 'home' }"
          aria-label="Baseframe home"
          @click="closeMobileNavigation"
        >
          <BrandLogo inverse />
        </router-link>
        <div v-if="!compactDrawer" class="app-drawer__label">Main menu</div>
        <q-list class="app-nav">
          <q-item
            v-for="item in visibleMenu"
            :key="item.label"
            v-ripple
            clickable
            :to="item.to"
            :exact="item.exact"
            :aria-label="item.label"
            active-class="app-nav__active"
            class="app-nav__item"
            @click="closeMobileNavigation"
          >
            <q-item-section avatar>
              <q-icon :name="item.icon" size="20px" />
              <q-tooltip v-if="compactDrawer" anchor="center right" self="center left">
                {{ item.label }}
              </q-tooltip>
            </q-item-section>
            <q-item-section v-if="!compactDrawer">{{ item.label }}</q-item-section>
          </q-item>
        </q-list>
        <div v-if="!compactDrawer" class="app-drawer__footer">
          <span class="app-drawer__footer-dot" aria-hidden="true" />
          A foundation for your work
        </div>
      </div>
    </q-drawer>

    <q-page-container>
      <router-view #default="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </q-page-container>
  </q-layout>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useQuasar } from 'quasar'

import BrandLogo from '@/components/BrandLogo.vue'
import { menuItems } from '@/module'
import { UserMenu, useAuthStore } from '@/module/auth'

const drawerOpen = ref(false)
const drawerExpanded = ref(true)
const $q = useQuasar()
const auth = useAuthStore()
const compactDrawer = computed(() => $q.screen.gt.sm && !drawerExpanded.value)
const menuToggleLabel = computed(() =>
  $q.screen.lt.md
    ? drawerOpen.value
      ? 'Close navigation'
      : 'Open navigation'
    : compactDrawer.value
      ? 'Expand navigation'
      : 'Collapse navigation',
)

function toggleNavigation() {
  if ($q.screen.lt.md) drawerOpen.value = !drawerOpen.value
  else drawerExpanded.value = !drawerExpanded.value
}

function closeMobileNavigation() {
  if ($q.screen.lt.md) drawerOpen.value = false
}

const HOME = { label: 'Overview', icon: 'space_dashboard', to: { name: 'home' }, exact: true }
const visibleMenu = computed(() => [
  HOME,
  ...menuItems.filter((item) => !item.permission || auth.can(item.permission)),
])
</script>

<style scoped lang="scss">
.app-shell {
  background: var(--app-bg);
}

.app-header {
  background: var(--app-surface);
  color: var(--app-text);
  border-bottom: 1px solid var(--app-border);
  box-shadow: none;
}

.app-header__toolbar {
  min-height: 64px;
  padding: 0 var(--app-space-lg);
  gap: var(--app-space-sm);
}

.app-header__menu {
  margin-left: -8px;
}

.app-header__location {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
}

.app-header__section,
.app-header__location .q-icon {
  color: var(--app-text-muted);
}

.app-header__current {
  font-weight: 600;
}

.app-header__divider {
  height: 24px;
  border-left: 1px solid var(--app-border);
  margin: 0 var(--app-space-sm);
}

.app-drawer {
  color: var(--app-sidebar-text);
  border-color: var(--app-sidebar-border);
}

.app-drawer__body {
  display: flex;
  min-height: 100%;
  flex-direction: column;
}

.app-drawer__brand {
  display: block;
  padding: 22px 18px 28px;
  color: inherit;
  text-decoration: none;
}

.app-drawer__body--compact .app-drawer__brand :deep(.brand-logo__copy) {
  display: none;
}

.app-drawer__label {
  padding: 0 24px 10px;
  color: var(--app-sidebar-muted);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.11em;
  text-transform: uppercase;
}

.app-nav {
  padding: 0 12px;
  flex: 1;
}

.app-nav__item {
  min-height: 44px;
  margin: 3px 0;
  padding: 0 12px;
  border-radius: var(--app-radius-md);
  color: var(--app-sidebar-muted);
  font-weight: 500;
  transition:
    background-color 150ms ease,
    color 150ms ease;
}

.app-nav__item:hover,
.app-nav__active {
  background: var(--app-sidebar-hover);
  color: var(--app-sidebar-text);
}

.app-nav__active {
  background: var(--app-sidebar-active);
  color: var(--app-sidebar-active-text);
}

.app-nav__item :deep(.q-item__section--avatar) {
  min-width: 34px;
}

.app-drawer__body--compact .app-nav {
  padding: 0 8px;
}

.app-drawer__body--compact .app-nav__item {
  justify-content: center;
  padding: 0;
}

.app-drawer__body--compact .app-nav__item :deep(.q-item__section--avatar) {
  min-width: 0;
  align-items: center;
}

.app-drawer__footer {
  display: flex;
  align-items: center;
  gap: 9px;
  margin: 16px 20px 22px;
  padding-top: 17px;
  border-top: 1px solid var(--app-sidebar-border);
  color: var(--app-sidebar-muted);
  font-size: 11px;
}

.app-drawer__footer-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--app-accent);
}

@media (max-width: 599px) {
  .app-header__toolbar {
    padding: 0 var(--app-space-md);
  }

  .app-header :deep(.brand-logo__copy),
  .app-header__divider {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .app-nav__item {
    transition: none;
  }
}
</style>
