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
        <div v-if="!compactDrawer" class="app-drawer__label">Workspace</div>
        <div v-if="!compactDrawer" class="app-drawer__search">
          <q-select
            v-model="featureTarget"
            dense
            outlined
            clearable
            use-input
            hide-selected
            fill-input
            input-debounce="0"
            :options="featureOptions"
            option-label="label"
            label="Go to feature"
            aria-label="Go to feature"
            @update:model-value="goToFeature"
          >
            <template #prepend><q-icon name="search" /></template>
            <template #option="scope">
              <q-item v-bind="scope.itemProps">
                <q-item-section avatar><q-icon :name="scope.opt.icon" /></q-item-section>
                <q-item-section>
                  <q-item-label>{{ scope.opt.label }}</q-item-label>
                  <q-item-label caption>{{ scope.opt.group || 'Workspace' }}</q-item-label>
                </q-item-section>
              </q-item>
            </template>
          </q-select>
        </div>
        <q-btn
          v-else
          class="app-drawer__compact-search"
          flat
          round
          dense
          icon="search"
          aria-label="Go to feature"
          @click="featureSearchOpen = true"
        >
          <q-tooltip anchor="center right" self="center left">Go to feature</q-tooltip>
        </q-btn>
        <q-list class="app-nav">
          <q-item
            v-ripple
            clickable
            :to="homeItem.to"
            exact
            aria-label="Overview"
            active-class="app-nav__active"
            class="app-nav__item"
            @click="closeMobileNavigation"
          >
            <q-item-section avatar>
              <q-icon :name="homeItem.icon" size="20px" />
              <q-tooltip v-if="compactDrawer" anchor="center right" self="center left">
                Overview
              </q-tooltip>
            </q-item-section>
            <q-item-section v-if="!compactDrawer">Overview</q-item-section>
          </q-item>
          <template v-for="group in menuGroups" :key="group.label">
            <div v-if="compactDrawer" class="app-nav__compact-group">
              <q-btn
                flat
                round
                dense
                class="app-nav__compact-trigger"
                :icon="group.icon"
                :aria-label="group.label"
              >
                <q-tooltip anchor="center right" self="center left">{{ group.label }}</q-tooltip>
                <q-menu anchor="top right" self="top left">
                  <q-list dense class="app-nav__popup">
                    <q-item
                      v-for="item in group.items"
                      :key="item.label"
                      v-ripple
                      clickable
                      :to="item.to"
                      :exact="item.exact"
                      active-class="app-nav__active"
                      @click="closeMobileNavigation"
                    >
                      <q-item-section avatar><q-icon :name="item.icon" /></q-item-section>
                      <q-item-section>{{ item.label }}</q-item-section>
                    </q-item>
                  </q-list>
                </q-menu>
              </q-btn>
            </div>
            <template v-else>
              <button
                class="app-nav__group-toggle"
                type="button"
                :aria-expanded="Boolean(expandedGroups[group.label])"
                @click="toggleGroup(group.label)"
              >
                <span class="app-nav__group-icon"><q-icon :name="group.icon" size="17px" /></span>
                <span class="app-nav__group-label">{{ group.label }}</span>
                <q-badge class="app-nav__group-count" :label="group.items.length" />
                <q-icon
                  class="app-nav__group-chevron"
                  :class="{ 'app-nav__group-chevron--open': expandedGroups[group.label] }"
                  name="expand_more"
                  size="18px"
                />
              </button>
              <q-slide-transition>
                <q-list v-show="expandedGroups[group.label]" class="app-nav__children">
                  <q-item
                    v-for="item in group.items"
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
                    <q-item-section avatar><q-icon :name="item.icon" size="20px" /></q-item-section>
                    <q-item-section>{{ item.label }}</q-item-section>
                  </q-item>
                </q-list>
              </q-slide-transition>
            </template>
          </template>
        </q-list>
        <div v-if="!compactDrawer" class="app-drawer__footer">
          <span class="app-drawer__footer-dot" aria-hidden="true" />
          A foundation for your work
        </div>
      </div>
    </q-drawer>

    <q-dialog v-model="featureSearchOpen">
      <q-card class="app-feature-search">
        <q-card-section>
          <div class="text-subtitle1 text-weight-medium">Go to feature</div>
          <div class="text-caption text-app-muted">Search available workspace features.</div>
        </q-card-section>
        <q-card-section class="q-pt-none">
          <q-select
            v-model="featureTarget"
            autofocus
            outlined
            use-input
            hide-selected
            fill-input
            input-debounce="0"
            :options="featureOptions"
            option-label="label"
            label="Search features"
            @update:model-value="goToFeature"
          >
            <template #prepend><q-icon name="search" /></template>
            <template #option="scope">
              <q-item v-bind="scope.itemProps">
                <q-item-section avatar><q-icon :name="scope.opt.icon" /></q-item-section>
                <q-item-section>
                  <q-item-label>{{ scope.opt.label }}</q-item-label>
                  <q-item-label caption>{{ scope.opt.group || 'Workspace' }}</q-item-label>
                </q-item-section>
              </q-item>
            </template>
          </q-select>
        </q-card-section>
      </q-card>
    </q-dialog>

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
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuasar } from 'quasar'

import BrandLogo from '@/components/BrandLogo.vue'
import { menuItems } from '@/module'
import { UserMenu, useAuthStore } from '@/module/auth'

const drawerOpen = ref(false)
const drawerExpanded = ref(true)
const $q = useQuasar()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const expandedGroups = ref({})
const featureTarget = ref(null)
const featureSearchOpen = ref(false)
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

const homeItem = { label: 'Overview', icon: 'space_dashboard', to: { name: 'home' }, exact: true }
const availableFeatures = computed(() => [
  homeItem,
  ...menuItems.filter((item) => !item.permission || auth.can(item.permission)),
])
const featureOptions = computed(() => availableFeatures.value)
const menuGroups = computed(() => {
  const grouped = new Map()
  for (const item of availableFeatures.value.slice(1)) {
    const label = item.group || 'Other features'
    const group = grouped.get(label) || { label, items: [], icon: item.groupIcon || 'apps' }
    group.items.push(item)
    grouped.set(label, group)
  }
  return [...grouped.values()]
})

function toggleGroup(label) {
  expandedGroups.value[label] = !expandedGroups.value[label]
}

function goToFeature(item) {
  if (!item) return
  const group = item.group
  if (group) expandedGroups.value[group] = true
  router.push(item.to)
  featureTarget.value = null
  featureSearchOpen.value = false
  closeMobileNavigation()
}

watch(
  () => route.name,
  (name) => {
    const activeItem = availableFeatures.value.find((item) => item.to.name === name)
    if (activeItem?.group) expandedGroups.value[activeItem.group] = true
  },
  { immediate: true },
)
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

.app-drawer__search {
  padding: 0 12px 12px;
}

.app-drawer__search :deep(.q-field__control) {
  background: var(--app-surface);
}

.app-drawer__compact-search {
  align-self: center;
  margin: 0 auto 10px;
  color: var(--app-sidebar-muted);
}

.app-nav {
  padding: 0 12px;
  flex: 1;
}

.app-nav__group-toggle {
  display: flex;
  width: 100%;
  min-height: 40px;
  align-items: center;
  gap: 9px;
  padding: 0 12px;
  margin: 8px 0 2px;
  color: var(--app-sidebar-muted);
  text-align: left;
  background: transparent;
  border: 0;
  border-radius: var(--app-radius-md);
  cursor: pointer;
  transition:
    color 150ms ease,
    background-color 150ms ease;
}

.app-nav__group-toggle:hover {
  color: var(--app-sidebar-text);
  background: var(--app-sidebar-hover);
}

.app-nav__group-icon {
  display: grid;
  width: 22px;
  flex: none;
  place-items: center;
}

.app-nav__group-label {
  flex: 1;
  font-size: 11px;
  font-weight: 650;
}

.app-nav__group-count {
  padding: 2px 6px;
  color: var(--app-sidebar-muted);
  background: var(--app-sidebar-hover);
  font-size: 10px;
}

.app-nav__group-chevron {
  flex: none;
  transition: transform 150ms ease;
}

.app-nav__group-chevron--open {
  transform: rotate(180deg);
}

.app-nav__children {
  padding-left: 8px;
}

.app-nav__compact-group {
  display: flex;
  justify-content: center;
  margin: 5px 0;
}

.app-nav__compact-trigger {
  color: var(--app-sidebar-muted);
}

.app-nav__popup {
  min-width: 220px;
  padding: 6px;
}

.app-feature-search {
  width: min(480px, calc(100vw - 32px));
  max-width: 480px;
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
