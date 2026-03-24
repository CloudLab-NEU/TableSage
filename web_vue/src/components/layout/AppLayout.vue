<script setup lang="ts">
import Navbar from './Navbar.vue'
</script>

<template>
  <div class="app-layout">
    <Navbar />
    <main class="main-content">
      <div class="page-container">
         <slot />
      </div>
    </main>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  background-color: var(--bg-base);
  overflow: hidden;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
  background: var(--bg-surface);
  min-height: 0;
}

.page-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  width: 100%;
  min-height: 0;
}
</style>
