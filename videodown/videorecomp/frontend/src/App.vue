<template>
  <div id="app">
    <NavBar />
    <el-container class="main-container">
      <el-main>
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
    <el-footer>
      <p>&copy; 2026 视频工具 | 专业视频处理平台</p>
    </el-footer>
  </div>
</template>

<script setup>
import NavBar from './components/NavBar.vue'
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  flex-direction: column;
}

.main-container {
  flex: 1;
}

.el-main {
  padding: 40px 20px;
}

.el-footer {
  background-color: rgba(255, 255, 255, 0.95);
  color: #666;
  text-align: center;
  padding: 20px;
  box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.1);
}

/* 页面切换动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
