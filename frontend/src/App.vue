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
    primaryColor: "#0ea5e9",
    primaryColorHover: "#38bdf8",
    primaryColorPressed: "#0284c7",
    primaryColorSuppl: "#0ea5e9",
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
  padding: 0.65rem 1.5rem;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  background: var(--bg-surface);
}

.app-title {
  font-size: 1.15rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--accent);
  margin: 0;
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
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: color 0.18s ease, border-color 0.18s ease;
}

.nav-link:hover,
.nav-link.router-link-active {
  color: var(--accent);
  border-bottom-color: var(--accent);
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
