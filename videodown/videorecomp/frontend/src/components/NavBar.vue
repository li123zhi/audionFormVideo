<template>
  <el-menu
    :default-active="activeMenu"
    mode="horizontal"
    :ellipsis="false"
    router
    class="navbar"
  >
    <div class="logo-container">
      <el-icon class="logo-icon"><Video-Camera /></el-icon>
      <span class="logo-text">视频工具</span>
    </div>

    <el-menu-item index="/video-recomp">
      <el-icon><Video-Camera /></el-icon>
      <span>重新生成视频</span>
    </el-menu-item>

    <el-menu-item index="/audio-splitter">
      <el-icon><Scissors /></el-icon>
      <span>拆分配音文件</span>
    </el-menu-item>

    <el-menu-item index="/batch-process">
      <el-icon><Files /></el-icon>
      <span>迭代调整剪辑</span>
    </el-menu-item>
  </el-menu>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const activeMenu = computed(() => route.path)
</script>

<style scoped>
.navbar {
  border-bottom: 2px solid #667eea;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 0 20px;
}

:deep(.el-menu-item) {
  color: white;
  font-size: 16px;
  transition: all 0.3s;
}

:deep(.el-menu-item:hover) {
  background-color: rgba(255, 255, 255, 0.1) !important;
}

:deep(.el-menu-item.is-active) {
  background-color: rgba(255, 255, 255, 0.2) !important;
  border-bottom-color: white !important;
  color: white;
  font-weight: 600;
}

.logo-container {
  display: flex;
  align-items: center;
  margin-right: 40px;
  float: left;
  height: 60px;
}

.logo-icon {
  font-size: 28px;
  color: white;
  margin-right: 10px;
}

.logo-text {
  color: white;
  font-size: 20px;
  font-weight: 600;
  letter-spacing: 1px;
}

:deep(.el-icon) {
  margin-right: 5px;
}
</style>
