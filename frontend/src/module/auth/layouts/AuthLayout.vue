<template>
  <q-layout view="hHh lpR fFf">
    <q-page-container>
      <q-page class="auth-layout">
        <aside class="auth-layout__story">
          <BrandLogo inverse />
          <div class="auth-layout__message">
            <div class="auth-layout__eyebrow">THE BASEFRAME PLATFORM</div>
            <h1>Build on a stronger foundation.</h1>
            <p>A focused workspace for the systems and people your business depends on.</p>
          </div>
          <div class="auth-layout__foot">Secure access <span /> Modular by design</div>
        </aside>

        <main class="auth-layout__main">
          <BrandLogo class="auth-layout__mobile-brand" />
          <div class="auth-layout__content">
            <router-view />
          </div>
          <div class="auth-layout__copyright">Baseframe · Enterprise foundation</div>
        </main>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<script setup>
import BrandLogo from '@/components/BrandLogo.vue'
</script>

<style scoped lang="scss">
.auth-layout {
  display: grid;
  grid-template-columns: minmax(360px, 44%) minmax(0, 1fr);
  min-height: 100vh;
  background: var(--app-bg);
}

.auth-layout__story {
  --app-sidebar-bg: #{$app-dark-sidebar-bg};
  --app-sidebar-text: #{$app-dark-sidebar-text};
  --app-sidebar-muted: #{$app-dark-sidebar-muted};
  --app-sidebar-border: #{$app-dark-sidebar-border};

  display: flex;
  flex-direction: column;
  padding: clamp(32px, 4vw, 64px);
  background: var(--app-sidebar-bg);
  color: var(--app-sidebar-text);
}

.auth-layout__message {
  max-width: 510px;
  margin: auto 0;
}

.auth-layout__eyebrow {
  margin-bottom: var(--app-space-lg);
  color: var(--app-sidebar-muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.15em;
}

.auth-layout__message h1 {
  margin: 0 0 var(--app-space-lg);
  font-size: clamp(34px, 3.2vw, 54px);
  font-weight: 700;
  letter-spacing: -0.045em;
  line-height: 1.13;
}

.auth-layout__message p {
  max-width: 400px;
  margin: 0;
  color: var(--app-sidebar-muted);
  font-size: 16px;
  line-height: 1.65;
}

.auth-layout__foot {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--app-sidebar-muted);
  font-size: 12px;
}

.auth-layout__foot span {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--app-accent);
}

.auth-layout__main {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--app-space-xl);
}

.auth-layout__mobile-brand {
  display: none;
}

.auth-layout__content {
  width: min(100%, 440px);
  margin: auto 0;
}

.auth-layout__copyright {
  color: var(--app-text-muted);
  font-size: 11px;
}

@media (max-width: 800px) {
  .auth-layout {
    display: block;
  }

  .auth-layout__story {
    display: none;
  }

  .auth-layout__main {
    min-height: 100vh;
    padding: 24px;
  }

  .auth-layout__mobile-brand {
    display: inline-flex;
    align-self: flex-start;
  }
}
</style>
