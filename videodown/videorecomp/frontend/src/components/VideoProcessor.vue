<template>
  <div class="video-processor">
    <el-card class="main-card">
      <template #header>
        <div class="card-header">
          <el-icon><Film /></el-icon>
          <span>上传文件</span>
        </div>
      </template>

      <!-- 上传区域 -->
      <div class="upload-section">
        <el-form label-width="120px">
          <!-- 原视频上传 -->
          <el-form-item label="原视频">
            <el-upload
              ref="videoUpload"
              class="upload-demo"
              drag
              :auto-upload="false"
              :limit="1"
              :on-change="(file) => handleFileChange(file, 'video')"
              :on-remove="() => handleFileRemove('video')"
              accept="video/*"
            >
              <el-icon class="el-icon--upload"><Upload-Filled /></el-icon>
              <div class="el-upload__text">
                拖拽视频到此处或 <em>点击上传</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">
                  支持 mp4, avi, mov 等视频格式
                </div>
              </template>
            </el-upload>
          </el-form-item>

          <!-- 原字幕文件上传 -->
          <el-form-item label="原字幕文件">
            <el-upload
              ref="originalSrtUpload"
              class="upload-demo"
              drag
              :auto-upload="false"
              :limit="1"
              :on-change="(file) => handleFileChange(file, 'original_srt')"
              :on-remove="() => handleFileRemove('original_srt')"
              accept=".srt"
            >
              <el-icon class="el-icon--upload"><Document /></el-icon>
              <div class="el-upload__text">
                拖拽SRT文件到此处或 <em>点击上传</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">
                  支持 .srt 格式字幕文件（可选）
                </div>
              </template>
            </el-upload>
          </el-form-item>

          <!-- 新字幕文件上传 -->
          <el-form-item label="新字幕文件">
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
                  支持 .srt 格式字幕文件（必需）
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
              accept=".zip"
            >
              <el-icon class="el-icon--upload"><Folder-Opened /></el-icon>
              <div class="el-upload__text">
                拖拽ZIP文件到此处或 <em>点击上传</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">
                  ZIP文件包含多个音频片段，将按顺序拼接
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
          :disabled="!canUpload"
          :loading="uploading"
          @click="handleUpload"
        >
          <el-icon><Video-Camera /></el-icon>
          {{ uploading ? '上传中...' : '开始处理' }}
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

    <!-- 上传进度 -->
    <el-card v-if="uploading || processing" class="progress-card">
      <template #header>
        <div class="card-header">
          <el-icon><Loading /></el-icon>
          <span>处理进度</span>
        </div>
      </template>

      <div class="progress-content">
        <el-steps :active="currentStep" finish-status="success" align-center>
          <el-step title="上传文件" :description="uploadProgress + '%'"></el-step>
          <el-step title="处理视频" :description="processProgress + '%'"></el-step>
          <el-step title="生成完成"></el-step>
        </el-steps>

        <div class="status-text">
          <p>{{ statusMessage }}</p>
        </div>
      </div>
    </el-card>

    <!-- 结果下载 -->
    <el-card v-if="completed" class="result-card">
      <template #header>
        <div class="card-header">
          <el-icon><Circle-Check /></el-icon>
          <span>处理完成</span>
        </div>
      </template>

      <div class="result-content">
        <el-alert
          title="视频生成成功！"
          type="success"
          :closable="false"
          show-icon
        />

        <!-- 新字幕版本 -->
        <div class="download-group">
          <h3>新字幕版本</h3>
          <div class="download-section">
            <el-button
              type="success"
              size="large"
              @click="handleDownload('soft')"
            >
              <el-icon><Download /></el-icon>
              下载软字幕版本
            </el-button>

            <el-button
              type="success"
              size="large"
              @click="handleDownload('hard')"
            >
              <el-icon><Download /></el-icon>
              下载硬字幕版本
            </el-button>
          </div>
        </div>

        <!-- 原字幕版本（如果有） -->
        <div v-if="files.original_srt" class="download-group">
          <h3>原字幕版本</h3>
          <div class="download-section">
            <el-button
              type="primary"
              size="large"
              @click="handleDownload('original_soft')"
            >
              <el-icon><Download /></el-icon>
              下载原字幕软字幕版本
            </el-button>

            <el-button
              type="primary"
              size="large"
              @click="handleDownload('original_hard')"
            >
              <el-icon><Download /></el-icon>
              下载原字幕硬字幕版本
            </el-button>
          </div>
        </div>

        <!-- 不带字幕版本 -->
        <div class="download-group">
          <h3>其他版本</h3>
          <div class="download-section">
            <el-button
              type="info"
              size="large"
              @click="handleDownload('no_subtitle')"
            >
              <el-icon><Download /></el-icon>
              下载不带字幕版本
            </el-button>
          </div>
        </div>

        <div class="info-section">
          <el-descriptions title="文件信息" :column="1" border>
            <el-descriptions-item label="任务ID">{{ taskId }}</el-descriptions-item>
            <el-descriptions-item label="原视频">{{ files.video?.name }}</el-descriptions-item>
            <el-descriptions-item label="原字幕文件">{{ files.original_srt?.name || '未上传' }}</el-descriptions-item>
            <el-descriptions-item label="新字幕文件">{{ files.srt?.name }}</el-descriptions-item>
            <el-descriptions-item label="配音文件">{{ files.audio?.name }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  uploadFiles,
  processVideo,
  getTaskStatus,
  downloadVideo,
  cancelTask
} from '../services/api'

// 文件存储
const files = ref({
  video: null,
  original_srt: null,
  srt: null,
  audio: null
})

// 状态
const uploading = ref(false)
const processing = ref(false)
const completed = ref(false)
const uploadProgress = ref(0)
const processProgress = ref(0)
const currentStep = ref(0)
const statusMessage = ref('')
const taskId = ref(null)

// 计算属性
const canUpload = computed(() => {
  return files.value.video && files.value.srt && files.value.audio
})

// 处理文件选择
function handleFileChange(file, type) {
  files.value[type] = file.raw
}

// 处理文件移除
function handleFileRemove(type) {
  files.value[type] = null
}

// 上传并处理
async function handleUpload() {
  if (!canUpload.value) {
    ElMessage.warning('请先上传所有必需的文件')
    return
  }

  uploading.value = true
  currentStep.value = 0
  statusMessage.value = '正在上传文件...'

  try {
    const formData = new FormData()
    formData.append('video', files.value.video)
    if (files.value.original_srt) {
      formData.append('original_srt', files.value.original_srt)
    }
    formData.append('srt', files.value.srt)
    formData.append('audio', files.value.audio)

    // 上传文件
    const uploadResponse = await uploadFiles(formData, (progress) => {
      uploadProgress.value = progress
      statusMessage.value = `正在上传文件... ${progress}%`
    })

    taskId.value = uploadResponse.data.task_id
    uploadProgress.value = 100

    // 开始处理
    uploading.value = false
    processing.value = true
    currentStep.value = 1
    statusMessage.value = '正在处理视频...'

    await processVideo(taskId.value)

    // 轮询状态
    pollStatus()

  } catch (error) {
    console.error('上传失败:', error)
    ElMessage.error(error.response?.data?.error || '上传失败，请重试')
    resetState()
  }
}

// 轮询处理状态
function pollStatus() {
  const interval = setInterval(async () => {
    try {
      const response = await getTaskStatus(taskId.value)
      const status = response.data

      processProgress.value = status.progress || 0
      statusMessage.value = status.message || '正在处理视频...'

      if (status.status === 'completed') {
        clearInterval(interval)
        processing.value = false
        completed.value = true
        currentStep.value = 2
        statusMessage.value = '处理完成！'
        ElMessage.success('视频处理完成！')
      } else if (status.status === 'failed') {
        clearInterval(interval)
        ElMessage.error(status.error || '处理失败')
        resetState()
      }

    } catch (error) {
      clearInterval(interval)
      console.error('获取状态失败:', error)
      ElMessage.error('获取处理状态失败')
      resetState()
    }
  }, 2000)
}

// 下载视频
async function handleDownload(type) {
  try {
    const response = await downloadVideo(taskId.value, type)

    // 创建下载链接
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url

    // 文件名映射
    const filenameMap = {
      'soft': `output_new_soft_subtitle_${taskId.value}.mp4`,
      'hard': `output_new_hard_subtitle_${taskId.value}.mp4`,
      'original_soft': `output_original_soft_subtitle_${taskId.value}.mp4`,
      'original_hard': `output_original_hard_subtitle_${taskId.value}.mp4`,
      'no_subtitle': `output_no_subtitle_${taskId.value}.mp4`
    }

    const filename = filenameMap[type] || `output_${type}_${taskId.value}.mp4`

    link.setAttribute('download', filename)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)

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

    await cancelTask(taskId.value)
    ElMessage.success('任务已取消')
    resetState()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('取消任务失败:', error)
      ElMessage.error('取消任务失败')
    }
  }
}

// 重置状态
function resetState() {
  uploading.value = false
  processing.value = false
  completed.value = false
  uploadProgress.value = 0
  processProgress.value = 0
  currentStep.value = 0
  statusMessage.value = ''
  taskId.value = null
}
</script>

<style scoped>
.video-processor {
  max-width: 900px;
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
  margin-top: 30px;
  font-size: 16px;
  color: #666;
}

.result-content {
  padding: 20px 0;
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

.download-group {
  margin-top: 30px;
}

.download-group h3 {
  margin-bottom: 15px;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}
</style>
