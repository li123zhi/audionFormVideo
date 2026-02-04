<template>
  <div class="batch-process-page">
    <el-page-header @back="goBack" class="page-header">
      <template #content>
        <div class="page-title">
          <el-icon><Video-Camera /></el-icon>
          <span>迭代调整剪辑</span>
        </div>
      </template>
    </el-page-header>

    <div class="batch-processor">
      <el-card class="main-card">
        <template #header>
          <div class="card-header">
            <el-icon><Files /></el-icon>
            <span>上传文件</span>
          </div>
        </template>

        <!-- 上传表单 -->
        <el-form :model="form" label-width="120px" label-position="left">
          <el-form-item label="原视频">
            <el-upload
              ref="videoUpload"
              :auto-upload="false"
              :show-file-list="true"
              :limit="1"
              accept="video/*"
              @change="handleVideoChange"
            >
              <el-button type="primary">
                <el-icon><Upload /></el-icon>
                选择视频文件
              </el-button>
            </el-upload>
          </el-form-item>

          <el-form-item label="原字幕">
            <el-upload
              ref="originalSrtUpload"
              :auto-upload="false"
              :show-file-list="true"
              :limit="1"
              accept=".srt,.SRT"
              @change="handleOriginalSrtChange"
            >
              <el-button type="primary">
                <el-icon><Upload /></el-icon>
                选择原字幕文件
              </el-button>
            </el-upload>
          </el-form-item>

          <el-form-item label="新字幕">
            <el-upload
              ref="newSrtUpload"
              :auto-upload="false"
              :show-file-list="true"
              :limit="1"
              accept=".srt,.SRT"
              @change="handleNewSrtChange"
            >
              <el-button type="primary">
                <el-icon><Upload /></el-icon>
                选择新字幕文件
              </el-button>
            </el-upload>
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              size="large"
              :disabled="!canSubmit"
              :loading="processing"
              @click="handleSubmit"
            >
              <el-icon><Video-Camera /></el-icon>
              {{ processing ? '处理中...' : '开始生成' }}
            </el-button>
            <el-button size="large" @click="handleReset" :disabled="processing">
              重置
            </el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 处理结果 -->
      <el-card v-if="taskResult" class="result-card">
        <template #header>
          <div class="card-header">
            <el-icon><Document /></el-icon>
            <span>处理结果</span>
          </div>
        </template>

        <el-descriptions :column="2" border>
          <el-descriptions-item label="状态">
            <el-tag v-if="taskResult.status === 'completed'" type="success">完成</el-tag>
            <el-tag v-else-if="taskResult.status === 'failed'" type="danger">失败</el-tag>
            <el-tag v-else type="warning">处理中</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="进度">
            <el-progress
              :percentage="taskResult.progress || 0"
              :status="taskResult.status === 'completed' ? 'success' : undefined"
            />
          </el-descriptions-item>
        </el-descriptions>

        <div v-if="taskResult.status === 'completed' && taskResult.stats" class="stats-section">
          <el-divider content-position="left">统计信息</el-divider>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="原视频时长">
              {{ taskResult.stats.original_video_duration?.toFixed(2) }}秒
            </el-descriptions-item>
            <el-descriptions-item label="新字幕总时长">
              {{ taskResult.stats.new_subtitle_total_duration?.toFixed(2) }}秒
            </el-descriptions-item>
            <el-descriptions-item label="时长差">
              <span :class="taskResult.stats.duration_difference >= 0 ? 'text-success' : 'text-warning'">
                {{ taskResult.stats.duration_difference >= 0 ? '+' : '' }}{{ taskResult.stats.duration_difference?.toFixed(2) }}秒
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="匹配率">
              {{ taskResult.stats.match_rate }}
            </el-descriptions-item>
            <el-descriptions-item label="成功匹配">
              {{ taskResult.stats.matched_segments }} / {{ taskResult.stats.total_new_subtitles }}
            </el-descriptions-item>
            <el-descriptions-item label="提取片段数">
              {{ taskResult.stats.segments_count }}
            </el-descriptions-item>
          </el-descriptions>

          <div class="download-section">
            <el-button type="success" @click="handleDownload('video')">
              <el-icon><Download /></el-icon>
              下载视频
            </el-button>
            <el-button type="info" @click="handleDownload('log')">
              <el-icon><Download /></el-icon>
              下载日志
            </el-button>
          </div>
        </div>

        <div v-if="taskResult.status === 'failed'" class="error-section">
          <el-alert type="error" :closable="false">
            {{ taskResult.error }}
          </el-alert>
        </div>
      </el-card>

      <!-- 使用说明 -->
      <el-card class="info-card">
        <template #header>
          <div class="card-header">
            <el-icon><Info-Filled /></el-icon>
            <span>使用说明</span>
          </div>
        </template>

        <div class="info-content">
          <h4>🎯 算法规则（时间轴重映射）</h4>
          <ol>
            <li>为每条新字幕在原字幕中找到匹配内容（基于文本相似度）</li>
            <li>从原视频中提取对应的片段</li>
            <li>按照新字幕的时间轴排列所有片段</li>
            <li>拼接成新视频</li>
          </ol>

          <h4>📊 处理流程</h4>
          <ol>
            <li>上传原视频、原字幕、新字幕</li>
            <li>调整匹配相似度阈值（可选，默认0.5）</li>
            <li>点击"开始生成"</li>
            <li>等待处理完成</li>
            <li>下载调整后的视频和日志</li>
          </ol>

          <h4>💡 效果说明</h4>
          <ul>
            <li>新视频时长 = 接近新字幕总时长</li>
            <li>如果新字幕比原字幕短，新视频就比原视频短 ✅</li>
            <li>如果新字幕比原字幕长，新视频就比原视频长 ✅</li>
            <li>内容与新字幕完美匹配</li>
          </ul>

          <h4>⚙️ 参数调整</h4>
          <ul>
            <li>相似度阈值：用于字幕匹配，默认0.3</li>
            <li>提高阈值：匹配更严格，可能漏掉一些字幕</li>
            <li>降低阈值：匹配更宽松，可能匹配错误</li>
          </ul>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  VideoCamera,
  Files,
  Upload,
  Document,
  Download,
  InfoFilled
} from '@element-plus/icons-vue'
import {
  uploadIterativeAdjust,
  getIterativeAdjustStatus,
  downloadIterativeAdjustFile
} from '../services/api'

const router = useRouter()

// 表单数据
const form = ref({
  videoFile: null,
  originalSrtFile: null,
  newSrtFile: null
})

// 处理状态
const processing = ref(false)
const taskResult = ref(null)
const taskId = ref(null)

// 检查是否可以提交
const canSubmit = computed(() => {
  return form.value.videoFile &&
         form.value.originalSrtFile &&
         form.value.newSrtFile &&
         !processing.value
})

// 处理文件选择
const handleVideoChange = (file) => {
  form.value.videoFile = file.raw
}

const handleOriginalSrtChange = (file) => {
  form.value.originalSrtFile = file.raw
}

const handleNewSrtChange = (file) => {
  form.value.newSrtFile = file.raw
}

// 提交表单
const handleSubmit = async () => {
  if (!canSubmit.value) {
    ElMessage.warning('请先选择所有文件')
    return
  }

  try {
    processing.value = true
    taskResult.value = null

    // 创建FormData
    const formData = new FormData()
    formData.append('video', form.value.videoFile)
    formData.append('original_srt', form.value.originalSrtFile)
    formData.append('new_srt', form.value.newSrtFile)

    // 上传并开始处理
    const response = await uploadIterativeAdjust(formData)
    taskId.value = response.task_id

    ElMessage.success('任务已创建，正在处理...')

    // 开始轮询状态
    pollTaskStatus()

  } catch (error) {
    console.error('提交失败:', error)
    ElMessage.error(error.message || '提交失败')
    processing.value = false
  }
}

// 轮询任务状态
const pollTaskStatus = async () => {
  if (!taskId.value) return

  try {
    const status = await getIterativeAdjustStatus(taskId.value)
    taskResult.value = status

    if (status.status === 'completed') {
      processing.value = false
      ElMessage.success('处理完成！')
      return
    }

    if (status.status === 'failed') {
      processing.value = false
      ElMessage.error('处理失败')
      return
    }

    // 继续轮询
    setTimeout(pollTaskStatus, 2000)

  } catch (error) {
    console.error('查询状态失败:', error)
    processing.value = false
    ElMessage.error('查询状态失败')
  }
}

// 下载文件
const handleDownload = async (fileType) => {
  if (!taskId.value) {
    ElMessage.warning('任务不存在')
    return
  }

  try {
    await downloadIterativeAdjustFile(taskId.value, fileType)
    ElMessage.success('下载成功')
  } catch (error) {
    console.error('下载失败:', error)
    ElMessage.error(error.message || '下载失败')
  }
}

// 重置表单
const handleReset = () => {
  form.value = {
    videoFile: null,
    originalSrtFile: null,
    newSrtFile: null
  }
  taskResult.value = null
  taskId.value = null
}

// 返回
const goBack = () => {
  router.push('/')
}
</script>

<style scoped>
.batch-process-page {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 20px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 20px;
  font-weight: 600;
}

.batch-processor {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
}

.el-form-item {
  margin-bottom: 24px;
}

.stats-section {
  margin-top: 20px;
}

.download-section {
  margin-top: 20px;
  display: flex;
  gap: 10px;
}

.error-section {
  margin-top: 20px;
}

.info-content h4 {
  margin: 15px 0 10px 0;
  color: #409EFF;
}

.info-content ol, .info-content ul {
  margin: 10px 0;
  padding-left: 20px;
}

.info-content li {
  margin: 8px 0;
  line-height: 1.6;
}

.text-success {
  color: #67C23A;
  font-weight: 600;
}

.text-warning {
  color: #E6A23C;
  font-weight: 600;
}
</style>
