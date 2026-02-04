<template>
  <div class="audio-splitter-page">
    <el-page-header @back="goBack" class="page-header">
      <template #content>
        <div class="page-title">
          <el-icon><Scissor /></el-icon>
          <span>拆分配音文件</span>
        </div>
      </template>
    </el-page-header>

    <div class="audio-splitter">
      <el-card class="main-card">
        <template #header>
          <div class="card-header">
            <el-icon><Upload /></el-icon>
            <span>上传文件</span>
          </div>
        </template>

        <!-- 上传区域 -->
        <div class="upload-section">
          <el-form label-width="120px">
            <!-- 字幕文件上传 -->
            <el-form-item label="字幕文件">
              <el-upload
                ref="srtUpload"
                class="upload-demo"
                drag
                :auto-upload="false"
                :limit="1"
                :on-change="(file) => handleFileChange(file, 'srt')"
                :on-remove="() => handleFileRemove('srt')"
                accept=".srt"
              >
                <el-icon class="el-icon--upload"><Document /></el-icon>
                <div class="el-upload__text">
                  拖拽SRT文件到此处或 <em>点击上传</em>
                </div>
                <template #tip>
                  <div class="el-upload__tip">
                    支持 .srt 格式字幕文件，将根据时间轴拆分配音
                  </div>
                </template>
              </el-upload>
            </el-form-item>

            <!-- 配音文件上传 -->
            <el-form-item label="配音文件">
              <el-upload
                ref="audioUpload"
                class="upload-demo"
                drag
                :auto-upload="false"
                :limit="1"
                :on-change="(file) => handleFileChange(file, 'audio')"
                :on-remove="() => handleFileRemove('audio')"
                accept="audio/*,video/*"
              >
                <el-icon class="el-icon--upload"><Microphone /></el-icon>
                <div class="el-upload__text">
                  拖拽配音文件到此处或 <em>点击上传</em>
                </div>
                <template #tip>
                  <div class="el-upload__tip">
                    支持 mp3, wav, m4a, mp4 等音频/视频格式
                  </div>
                </template>
              </el-upload>
            </el-form-item>
          </el-form>
        </div>

        <!-- 操作按钮 -->
        <div class="action-buttons">
          <el-button
            type="primary"
            size="large"
            :disabled="!canSplit"
            :loading="splitting"
            @click="handleSplit"
          >
            <el-icon><Scissor /></el-icon>
            {{ splitting ? '拆分中...' : '开始拆分' }}
          </el-button>

          <el-button
            v-if="taskId"
            type="danger"
            size="large"
            @click="handleCancel"
          >
            <el-icon><Close /></el-icon>
            取消任务
          </el-button>
        </div>
      </el-card>

      <!-- 拆分进度 -->
      <el-card v-if="splitting" class="progress-card">
        <template #header>
          <div class="card-header">
            <el-icon><Loading /></el-icon>
            <span>拆分进度</span>
          </div>
        </template>

        <div class="progress-content">
          <el-progress :percentage="progress" :status="progressStatus" />
          <div class="status-text">
            <p>{{ statusMessage }}</p>
          </div>
        </div>
      </el-card>

      <!-- 拆分结果 -->
      <el-card v-if="completed" class="result-card">
        <template #header>
          <div class="card-header">
            <el-icon><Circle-Check /></el-icon>
            <span>拆分完成</span>
          </div>
        </template>

        <div class="result-content">
          <el-alert
            :title="`成功拆分为 ${segments.length} 个音频片段`"
            type="success"
            :closable="false"
            show-icon
          />

          <!-- 本地保存路径 -->
          <el-card class="path-card" shadow="never">
            <template #header>
              <div class="path-header">
                <el-icon><Folder-Opened /></el-icon>
                <span>本地保存路径</span>
              </div>
            </template>
            <div class="path-content">
              <el-text class="local-path" tag="code">{{ localPath }}</el-text>
              <el-button
                size="small"
                @click="copyPath"
              >
                <el-icon><Document-Copy /></el-icon>
                复制路径
              </el-button>
            </div>
          </el-card>

          <!-- 片段列表 -->
          <div class="segments-list">
            <el-table :data="segments" border stripe>
              <el-table-column type="index" label="#" width="60" />
              <el-table-column prop="index" label="序号" width="80" />
              <el-table-column prop="start" label="开始时间" width="120" />
              <el-table-column prop="end" label="结束时间" width="120" />
              <el-table-column prop="duration" label="时长(秒)" width="120" />
              <el-table-column prop="text" label="字幕内容" show-overflow-tooltip />
            </el-table>
          </div>

          <!-- 下载区域（可选） -->
          <el-collapse>
            <el-collapse-item title="下载选项（可选）" name="1">
              <div class="download-section">
                <el-button
                  type="success"
                  size="large"
                  @click="handleDownloadAll"
                >
                  <el-icon><Download /></el-icon>
                  下载所有片段 (ZIP)
                </el-button>
              </div>
            </el-collapse-item>
          </el-collapse>

          <div class="info-section">
            <el-descriptions title="文件信息" :column="1" border>
              <el-descriptions-item label="任务ID">{{ taskId }}</el-descriptions-item>
              <el-descriptions-item label="配音文件">{{ files.audio?.name }}</el-descriptions-item>
              <el-descriptions-item label="字幕文件">{{ files.srt?.name }}</el-descriptions-item>
              <el-descriptions-item label="片段数量">{{ segments.length }}</el-descriptions-item>
            </el-descriptions>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  splitAudioBySubtitles,
  getAudioSplitStatus,
  downloadAudioSplitResult
} from '../services/api'

const router = useRouter()

// 文件存储
const files = ref({
  srt: null,
  audio: null
})

// 状态
const splitting = ref(false)
const completed = ref(false)
const progress = ref(0)
const progressStatus = ref('')
const statusMessage = ref('')
const taskId = ref(null)
const segments = ref([])
const localPath = ref('')

// 计算属性
const canSplit = computed(() => {
  return files.value.srt && files.value.audio
})

// 返回首页
function goBack() {
  router.push('/')
}

// 处理文件选择
function handleFileChange(file, type) {
  files.value[type] = file.raw
}

// 处理文件移除
function handleFileRemove(type) {
  files.value[type] = null
}

// 开始拆分
async function handleSplit() {
  if (!canSplit.value) {
    ElMessage.warning('请先上传字幕文件和配音文件')
    return
  }

  splitting.value = true
  progress.value = 0
  statusMessage.value = '正在上传文件...'
  progressStatus.value = ''

  try {
    const formData = new FormData()
    formData.append('srt', files.value.srt)
    formData.append('audio', files.value.audio)

    // 上传并开始拆分
    const response = await splitAudioBySubtitles(formData, (percent) => {
      progress.value = percent
      statusMessage.value = `正在拆分... ${percent}%`
    })

    taskId.value = response.data.task_id

    // 轮询状态
    pollStatus()

  } catch (error) {
    console.error('拆分失败:', error)
    ElMessage.error(error.response?.data?.error || '拆分失败，请重试')
    resetState()
  }
}

// 轮询拆分状态
function pollStatus() {
  const interval = setInterval(async () => {
    try {
      const response = await getAudioSplitStatus(taskId.value)
      const status = response.data

      progress.value = status.progress || 0
      statusMessage.value = status.message || '正在拆分...'

      if (status.status === 'completed') {
        clearInterval(interval)
        splitting.value = false
        completed.value = true
        progress.value = 100
        progressStatus.value = 'success'
        statusMessage.value = '拆分完成！'
        segments.value = status.segments || []
        localPath.value = status.local_output_dir || '未知路径'
        ElMessage.success(`成功拆分为 ${segments.value.length} 个片段`)
      } else if (status.status === 'failed') {
        clearInterval(interval)
        progressStatus.value = 'exception'
        ElMessage.error(status.error || '拆分失败')
        resetState()
      }

    } catch (error) {
      clearInterval(interval)
      console.error('获取状态失败:', error)
      ElMessage.error('获取拆分状态失败')
      resetState()
    }
  }, 2000)
}

// 下载所有片段（ZIP）
async function handleDownloadAll() {
  try {
    await downloadAudioSplitResult(taskId.value)
    ElMessage.success('下载开始')
  } catch (error) {
    console.error('下载失败:', error)
    ElMessage.error('下载失败，请重试')
  }
}

// 取消任务
async function handleCancel() {
  try {
    await ElMessageBox.confirm('确定要取消当前任务吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    // TODO: 实现取消API
    ElMessage.success('任务已取消')
    resetState()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('取消任务失败:', error)
      ElMessage.error('取消任务失败')
    }
  }
}

// 复制路径到剪贴板
function copyPath() {
  navigator.clipboard.writeText(localPath.value).then(() => {
    ElMessage.success('路径已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败，请手动复制')
  })
}

// 重置状态
function resetState() {
  splitting.value = false
  completed.value = false
  progress.value = 0
  progressStatus.value = ''
  statusMessage.value = ''
  taskId.value = null
  segments.value = []
  localPath.value = ''
}
</script>

<style scoped>
.audio-splitter-page {
  min-height: 100vh;
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 24px;
  font-weight: 600;
  color: #333;
}

.audio-splitter {
  max-width: 1000px;
  margin: 0 auto;
}

.main-card,
.progress-card,
.result-card {
  margin-bottom: 24px;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
}

.upload-section {
  padding: 20px 0;
}

.upload-demo {
  width: 100%;
}

:deep(.el-upload-dragger) {
  padding: 40px;
  border-radius: 8px;
}

:deep(.el-icon--upload) {
  font-size: 67px;
  color: #667eea;
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-top: 30px;
}

.progress-content {
  padding: 30px 0;
}

.status-text {
  text-align: center;
  margin-top: 20px;
  font-size: 16px;
  color: #666;
}

.result-content {
  padding: 20px 0;
}

.path-card {
  margin: 20px 0;
  background-color: #f5f7fa;
  border: 1px solid #dcdfe6;
}

.path-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.path-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 0;
}

.local-path {
  flex: 1;
  font-family: 'Courier New', monospace;
  font-size: 14px;
  color: #409eff;
  word-break: break-all;
  padding: 10px;
  background-color: white;
  border-radius: 4px;
  border: 1px solid #dcdfe6;
}

.segments-list {
  margin: 30px 0;
}

.download-section {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin: 30px 0;
}

.info-section {
  margin-top: 30px;
}
</style>
