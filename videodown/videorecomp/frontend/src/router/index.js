import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/video-recomp'
  },
  {
    path: '/video-recomp',
    name: 'VideoRecomp',
    component: () => import('../views/VideoRecomp.vue'),
    meta: {
      title: '重新生成视频',
      icon: 'VideoCamera'
    }
  },
  {
    path: '/audio-splitter',
    name: 'AudioSplitter',
    component: () => import('../views/AudioSplitter.vue'),
    meta: {
      title: '拆分配音文件',
      icon: 'Scissors'
    }
  },
  {
    path: '/batch-process',
    name: 'BatchProcess',
    component: () => import('../views/BatchProcess.vue'),
    meta: {
      title: '迭代调整剪辑',
      icon: 'Files'
    }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
