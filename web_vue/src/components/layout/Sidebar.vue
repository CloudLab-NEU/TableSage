<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

const navItems = [
  { name: 'Chat', path: '/', icon: '💬', label: 'AI Assistant' },
  { name: 'KnowledgeVisualization', path: '/knowledge-visualization', icon: '📊', label: 'Knowledge Graph' },
  { name: 'TeachingVisualization', path: '/teaching-visualization', icon: '📈', label: 'Data Dashboard' }
]

const navigateTo = (path: string) => {
  router.push(path)
}
</script>

<template>
  <aside class="sidebar glass">
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

    <div class="sidebar-footer">
      <div class="user-profile">
        <div class="avatar">U</div>
        <div class="user-info">
          <div class="user-name">User</div>
          <div class="user-role">Admin</div>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 24px 16px;
  background: transparent;
  border-right: 1px solid var(--border-light);
  z-index: 10;
}

.logo-container {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 12px 32px;
}

.logo-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--primary-color), var(--accent-color));
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 1.2rem;
  box-shadow: var(--shadow-sm);
}

.logo-text {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.5px;
}

.nav-menu {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.3s ease;
  color: var(--text-secondary);
}

.nav-item:hover {
  background: var(--bg-surface-hover);
  color: var(--text-primary);
  transform: translateX(4px);
}

.nav-item.active {
  background: var(--primary-light);
  color: var(--primary-color);
  font-weight: 500;
}

.nav-icon {
  font-size: 1.2rem;
}

.nav-label {
  font-size: 0.95rem;
}

.sidebar-footer {
  margin-top: auto;
  padding-top: 24px;
  border-top: 1px solid var(--border-light);
}

.user-profile {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background 0.2s;
}

.user-profile:hover {
  background: var(--bg-surface-hover);
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  color: var(--text-primary);
}

.user-info {
  display: flex;
  flex-direction: column;
}

.user-name {
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--text-primary);
}

.user-role {
  font-size: 0.75rem;
  color: var(--text-tertiary);
}
</style>
