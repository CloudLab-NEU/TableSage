<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

const navItems = [
  { name: 'Chat', path: '/', icon: '💬', label: 'AI 问答助手' },
  { name: 'KnowledgeVisualization', path: '/knowledge-visualization', icon: '📊', label: '知识图谱大屏' },
  { name: 'TeachingVisualization', path: '/teaching-visualization', icon: '📈', label: '教学数据看板' }
]

const navigateTo = (path: string) => {
  router.push(path).catch(() => {})
}
</script>

<template>
  <header class="navbar glass">
    <div class="logo-container">
      <div class="logo-icon">TS</div>
      <h1 class="logo-text">TableSage</h1>
    </div>

    <nav class="nav-menu">
      <div 
        v-for="item in navItems" 
        :key="item.path"
        class="nav-item"
        :class="{ active: route.path === item.path }"
        @click="navigateTo(item.path)"
      >
        <span class="nav-icon">{{ item.icon }}</span>
        <span class="nav-label">{{ item.label }}</span>
      </div>
    </nav>
  </header>
</template>

<style scoped>
.navbar {
  height: var(--header-height);
  width: 100%;
  display: flex;
  align-items: center;
  padding: 0 24px;
  background: var(--bg-surface-glass);
  z-index: 50;
  position: relative;
}

.logo-container {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-right: 48px;
}

.logo-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--primary-color), var(--accent-color));
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 1rem;
  box-shadow: var(--shadow-sm);
}

.logo-text {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.5px;
}

.nav-menu {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 100%;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: all 0.3s ease;
  color: var(--text-secondary);
  font-size: 0.95rem;
  font-weight: 500;
}

.nav-item:hover {
  background: var(--bg-surface-hover);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--primary-light);
  color: var(--primary-color);
}

.nav-icon {
  font-size: 1.1rem;
}
</style>
