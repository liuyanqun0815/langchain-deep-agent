<template>
  <n-config-provider :theme-overrides="themeOverrides">
    <n-message-provider>
      <div class="app-root">
        <header class="app-header">
          <h1 class="app-title">DeepAgent</h1>
          <nav class="app-nav">
            <router-link to="/" class="nav-link">聊天</router-link>
            <router-link to="/models" class="nav-link">模型</router-link>
            <router-link to="/skills" class="nav-link">技能</router-link>
          </nav>
        </header>
        <main class="app-main">
          <div class="app-main-content">
            <router-view v-slot="{ Component }">
              <transition name="fade" mode="out-in">
                <component :is="Component" />
              </transition>
            </router-view>
          </div>
        </main>
      </div>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { NConfigProvider, NMessageProvider } from "naive-ui";

const themeOverrides = {
  common: {
    primaryColor: "#22d3ee",
    primaryColorHover: "#67e8f9",
    primaryColorPressed: "#06b6d4",
    primaryColorSuppl: "#22d3ee",
  },
};
</script>

<style scoped>
.app-root {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-base);
  color: var(--text-primary);
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1.5rem;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  background: var(--bg-surface);
  box-shadow: 0 1px 0 rgba(15, 23, 42, 0.9);
}

.app-title {
  font-family: "JetBrains Mono", "SF Mono", monospace;
  font-size: 1.25rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--accent);
  margin: 0;
  text-shadow: 0 0 24px rgba(34, 211, 238, 0.4);
}

.app-nav {
  display: flex;
  gap: 1.5rem;
}

.nav-link {
  position: relative;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 0.875rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding-bottom: 2px;
  transition: color 0.18s ease, border-color 0.18s ease;
}

.nav-link:hover,
.nav-link.router-link-active {
  color: var(--accent);
  border-bottom: 2px solid var(--accent);
}

.app-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.app-main-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.app-main-content > * {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
