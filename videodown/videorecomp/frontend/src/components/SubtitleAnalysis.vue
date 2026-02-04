<template>
  <div class="subtitle-analysis">
    <el-card class="analysis-card">
      <template #header>
        <div class="card-header">
          <el-icon><Data-Analysis /></el-icon>
          <span>字幕时间分析</span>
        </div>
      </template>

      <!-- 分析按钮 -->
      <div class="analysis-controls">
        <el-upload
          ref="originalUpload"
          :auto-upload="false"
          :show-file-list="false"
          accept=".srt"
          :on-change="(file) => handleFileChange(file, 'original')"
          style="display: inline-block; margin-right: 10px;"
        >
          <el-button type="primary">
            <el-icon><Upload /></el-icon>
            上传原字幕
          </el-button>
        </el-upload>

        <el-upload
          ref="newUpload"
          :auto-upload="false"
          :show-file-list="false"
          accept=".srt"
          :on-change="(file) => handleFileChange(file, 'new')"
          style="display: inline-block; margin-right: 10px;"
        >
          <el-button type="success">
            <el-icon><Upload /></el-icon>
            上传新字幕
          </el-button>
        </el-upload>

        <el-button
          type="primary"
          :disabled="!canAnalyze"
          :loading="analyzing"
          @click="handleAnalyze"
        >
          <el-icon><Data-Analysis /></el-icon>
          分析字幕
        </el-button>
      </div>

      <!-- 文件显示 -->
      <div v-if="files.original || files.new" class="file-display">
        <el-tag v-if="files.original" type="info" closable @close="files.original = null">
          原字幕: {{ files.original.name }}
        </el-tag>
        <el-tag v-if="files.new" type="success" closable @close="files.new = null">
          新字幕: {{ files.new.name }}
        </el-tag>
      </div>

      <!-- 分析结果 -->
      <div v-if="analysisResult" class="analysis-results">
        <!-- 统计摘要 -->
        <el-divider content-position="left">
          <el-icon><Data-Analysis /></el-icon>
          统计摘要
        </el-divider>

        <el-descriptions :column="2" border>
          <el-descriptions-item label="原字幕条数">
            {{ analysisResult.analysis?.summary?.original_count }}
          </el-descriptions-item>
          <el-descriptions-item label="新字幕条数">
            {{ analysisResult.analysis?.summary?.new_count }}
          </el-descriptions-item>
          <el-descriptions-item label="对比条数">
            {{ analysisResult.analysis?.summary?.compared_count }}
          </el-descriptions-item>
          <el-descriptions-item label="平均开始偏移">
            <el-tag :type="getOffsetTagType(analysisResult.analysis?.summary?.start_offset?.avg)">
              {{ formatOffset(analysisResult.analysis?.summary?.start_offset?.avg) }}秒
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="最大开始偏移">
            {{ formatOffset(analysisResult.analysis?.summary?.start_offset?.max) }}秒
          </el-descriptions-item>
          <el-descriptions-item label="平均时长变化">
            {{ formatOffset(analysisResult.analysis?.summary?.duration_offset?.avg) }}秒
          </el-descriptions-item>
        </el-descriptions>

        <!-- 可视化图表 -->
        <el-divider content-position="left">
          <el-icon><Trend-Charts /></el-icon>
          时间偏移分布
        </el-divider>

        <div class="charts-container">
          <div ref="startDiffChart" style="width: 100%; height: 300px;"></div>
          <div ref="durationDiffChart" style="width: 100%; height: 300px; margin-top: 20px;"></div>
        </div>

        <!-- 时间轴对比 -->
        <el-divider content-position="left">
          <el-icon><Clock /></el-icon>
          时间轴对比 (前10条)
        </el-divider>

        <el-table :data="timelineData.slice(0, 10)" border stripe>
          <el-table-column prop="index" label="序号" width="80" />
          <el-table-column label="原字幕时间" width="180">
            <template #default="{ row }">
              {{ formatTime(row.original_start) }} - {{ formatTime(row.original_end) }}
            </template>
          </el-table-column>
          <el-table-column label="新字幕时间" width="180">
            <template #default="{ row }">
              {{ formatTime(row.new_start) }} - {{ formatTime(row.new_end) }}
            </template>
          </el-table-column>
          <el-table-column label="开始偏移" width="100">
            <template #default="{ row }">
              <el-tag :type="getOffsetTagType(row.new_start - row.original_start)" size="small">
                {{ formatOffset(row.new_start - row.original_start) }}s
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="原文本" show-overflow-tooltip />
          <el-table-column label="新文本" show-overflow-tooltip />
        </el-table>

        <!-- 推荐参数 -->
        <el-divider content-position="left">
          <el-icon><Magic-Stick /></el-icon>
          推荐剪辑参数
        </el-divider>

        <el-alert
          :title="analysisResult.recommendations?.strategy"
          type="info"
          :closable="false"
          show-icon
        >
          <template #default>
            <p><strong>合并间隙:</strong> {{ analysisResult.recommendations?.merge_gap }}秒</p>
            <p><strong>原因:</strong> {{ analysisResult.recommendations?.reason }}</p>
            <p><strong>置信度:</strong>
              <el-tag :type="getConfidenceTagType(analysisResult.recommendations?.confidence)">
                {{ analysisResult.recommendations?.confidence }}
              </el-tag>
            </p>
          </template>
        </el-alert>

        <!-- 应用推荐按钮 -->
        <div class="action-buttons">
          <el-button type="primary" @click="applyRecommendations">
            <el-icon><Check /></el-icon>
            应用推荐参数
          </el-button>
          <el-button @click="exportReport">
            <el-icon><Download /></el-icon>
            导出分析报告
          </el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { analyzeSubtitles } from '../services/api'

const emit = defineEmits(['apply-recommendations'])

// 文件
const files = ref({
  original: null,
  new: null
})

// 状态
const analyzing = ref(false)
const analysisResult = ref(null)

// 图表引用
const startDiffChart = ref(null)
const durationDiffChart = ref(null)

// 计算属性
const canAnalyze = computed(() => files.value.original && files.value.new)

const timelineData = computed(() => {
  return analysisResult.value?.visualization?.timeline || []
})

// 处理文件选择
function handleFileChange(file, type) {
  files.value[type] = file.raw
}

// 分析字幕
async function handleAnalyze() {
  if (!canAnalyze.value) {
    ElMessage.warning('请先上传原字幕和新字幕')
    return
  }

  analyzing.value = true

  try {
    const formData = new FormData()
    formData.append('original_srt', files.value.original)
    formData.append('new_srt', files.value.new)

    const response = await analyzeSubtitles(formData)
    analysisResult.value = response.data

    ElMessage.success('分析完成')

    // 渲染图表
    await nextTick()
    renderCharts()
  } catch (error) {
    console.error('分析失败:', error)
    ElMessage.error(error.response?.data?.error || '分析失败')
  } finally {
    analyzing.value = false
  }
}

// 渲染图表
function renderCharts() {
  if (!analysisResult.value) return

  const viz = analysisResult.value.visualization

  // 开始偏移直方图
  if (startDiffChart.value) {
    const chart1 = echarts.init(startDiffChart.value)
    const data1 = viz.start_diff_histogram

    chart1.setOption({
      title: {
        text: '开始时间偏移分布',
        left: 'center'
      },
      tooltip: {
        trigger: 'axis'
      },
      xAxis: {
        type: 'category',
        data: data1.bins.map((v, i) => i),
        name: '偏移值'
      },
      yAxis: {
        type: 'value',
        name: '数量'
      },
      series: [{
        type: 'bar',
        data: data1.counts,
        itemStyle: {
          color: '#409EFF'
        }
      }]
    })
  }

  // 时长偏移直方图
  if (durationDiffChart.value) {
    const chart2 = echarts.init(durationDiffChart.value)
    const data2 = viz.duration_diff_histogram

    chart2.setOption({
      title: {
        text: '时长变化分布',
        left: 'center'
      },
      tooltip: {
        trigger: 'axis'
      },
      xAxis: {
        type: 'category',
        data: data2.bins.map((v, i) => i),
        name: '变化值'
      },
      yAxis: {
        type: 'value',
        name: '数量'
      },
      series: [{
        type: 'bar',
        data: data2.counts,
        itemStyle: {
          color: '#67C23A'
        }
      }]
    })
  }
}

// 应用推荐参数
function applyRecommendations() {
  if (!analysisResult.value?.recommendations) return

  emit('apply-recommendations', {
    merge_gap: analysisResult.value.recommendations.merge_gap,
    use_precise: analysisResult.value.recommendations.confidence === 'low'
  })

  ElMessage.success('已应用推荐参数')
}

// 导出报告
function exportReport() {
  if (!analysisResult.value) return

  const data = JSON.stringify(analysisResult.value, null, 2)
  const blob = new Blob([data], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `subtitle_analysis_${Date.now()}.json`
  link.click()
  URL.revokeObjectURL(url)

  ElMessage.success('报告已导出')
}

// 辅助函数
function formatOffset(value) {
  if (value === null || value === undefined) return 'N/A'
  return (value >= 0 ? '+' : '') + value.toFixed(3)
}

function formatTime(seconds) {
  if (seconds === null || seconds === undefined) return 'N/A'
  const date = new Date(0)
  date.setSeconds(seconds)
  return date.toISOString().substr(11, 12)
}

function getOffsetTagType(value) {
  if (Math.abs(value) < 0.3) return 'success'
  if (Math.abs(value) < 1.0) return 'warning'
  return 'danger'
}

function getConfidenceTagType(confidence) {
  switch (confidence) {
    case 'high': return 'success'
    case 'medium': return 'warning'
    case 'low': return 'danger'
    default: return 'info'
  }
}
</script>

<style scoped>
.subtitle-analysis {
  margin-bottom: 20px;
}

.analysis-card {
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

.analysis-controls {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
}

.file-display {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.analysis-results {
  margin-top: 20px;
}

.charts-container {
  margin: 20px 0;
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-top: 20px;
}
</style>
