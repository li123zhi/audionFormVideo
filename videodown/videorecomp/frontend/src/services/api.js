import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 300000 // 5分钟超时
})

// 上传文件
export function uploadFiles(formData, onProgress) {
  return api.post('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    onUploadProgress: (progressEvent) => {
      if (onProgress) {
        const percentCompleted = Math.round(
          (progressEvent.loaded * 100) / progressEvent.total
        )
        onProgress(percentCompleted)
      }
    }
  })
}

// 处理视频
export function processVideo(taskId) {
  return api.post(`/process/${taskId}`)
}

// 获取处理状态
export function getTaskStatus(taskId) {
  return api.get(`/status/${taskId}`)
}

// 下载视频
export function downloadVideo(taskId, type = 'soft') {
  return api.get(`/download/${taskId}/${type}`, {
    responseType: 'blob'
  })
}

// 取消任务
export function cancelTask(taskId) {
  return api.delete(`/task/${taskId}`)
}

// ========== 字幕分析和增强剪辑API ==========

// 分析字幕时间差异
export function analyzeSubtitles(formData) {
  return api.post('/analyze-subtitles', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    timeout: 60000 // 1分钟超时
  })
}

// 增强剪辑上传
export function uploadEnhancedClip(formData, onProgress) {
  return api.post('/enhanced-clip', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    onUploadProgress: (progressEvent) => {
      if (onProgress) {
        const percentCompleted = Math.round(
          (progressEvent.loaded * 100) / progressEvent.total
        )
        onProgress(percentCompleted)
      }
    }
  })
}

// 处理增强剪辑
export function processEnhancedClip(taskId) {
  return api.post(`/process-enhanced/${taskId}`)
}

// 批量剪辑视频
export function batchClipVideos(data) {
  return api.post('/batch-clip', data, {
    timeout: 600000 // 10分钟超时
  })
}

// ========== 紧凑剪辑API（累积偏移算法）==========

// 紧凑剪辑上传
export function uploadCompactClip(formData, onProgress) {
  return api.post('/compact-clip', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    onUploadProgress: (progressEvent) => {
      if (onProgress) {
        const percentCompleted = Math.round(
          (progressEvent.loaded * 100) / progressEvent.total
        )
        onProgress(percentCompleted)
      }
    }
  })
}

// 处理紧凑剪辑
export function processCompactClip(taskId) {
  return api.post(`/process-compact/${taskId}`)
}

// ========== 时间轴对齐API ==========

// 时间轴对齐上传
export function uploadTimelineAlign(formData, onProgress) {
  return api.post('/timeline-align', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    onUploadProgress: (progressEvent) => {
      if (onProgress) {
        const percentCompleted = Math.round(
          (progressEvent.loaded * 100) / progressEvent.total
        )
        onProgress(percentCompleted)
      }
    }
  })
}

// 处理时间轴对齐
export function processTimelineAlign(taskId) {
  return api.post(`/process-align/${taskId}`)
}

// ========== 迭代调整剪辑API ==========

// 迭代调整上传
export function uploadIterativeAdjust(formData, onProgress) {
  return api.post('/iterative-adjust', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    onUploadProgress: (progressEvent) => {
      if (onProgress) {
        const percentCompleted = Math.round(
          (progressEvent.loaded * 100) / progressEvent.total
        )
        onProgress(percentCompleted)
      }
    }
  })
}

// 查询迭代调整状态
export function getIterativeAdjustStatus(taskId) {
  return api.get(`/iterative-adjust/status/${taskId}`)
}

// 下载迭代调整文件
export function downloadIterativeAdjustFile(taskId, fileType) {
  return api.get(`/iterative-adjust/download/${taskId}?type=${fileType}`, {
    responseType: 'blob'
  }).then(response => {
    // 从响应头获取文件名
    const contentDisposition = response.headers['content-disposition']
    let filename = 'download'
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
      if (filenameMatch && filenameMatch[1]) {
        filename = filenameMatch[1].replace(/['"]/g, '')
      }
    }

    // 创建下载链接
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', filename)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)

    return response
  })
}

// 删除迭代调整任务
export function deleteIterativeAdjustTask(taskId) {
  return api.delete(`/iterative-adjust/task/${taskId}`)
}

// ========== 软硬字幕视频生成API ==========

// 生成软硬字幕视频
export function generateSubtitleVideos(formData, onProgress) {
  return api.post('/subtitle-generate', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    onUploadProgress: (progressEvent) => {
      if (onProgress) {
        const percentCompleted = Math.round(
          (progressEvent.loaded * 100) / progressEvent.total
        )
        onProgress(percentCompleted)
      }
    }
  })
}

// 查询字幕生成状态
export function getSubtitleGenerateStatus(taskId) {
  return api.get(`/subtitle-generate/status/${taskId}`)
}

// 下载字幕生成结果
export function downloadSubtitleVideo(taskId, type = 'soft') {
  return api.get(`/subtitle-generate/download/${taskId}/${type}`, {
    responseType: 'blob'
  }).then(response => {
    // 从响应头获取文件名
    const contentDisposition = response.headers['content-disposition']
    let filename = type === 'soft' ? 'soft_subtitle.mp4' : 'hard_subtitle.mp4'
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
      if (filenameMatch && filenameMatch[1]) {
        filename = filenameMatch[1].replace(/['"]/g, '')
      }
    }

    // 创建下载链接
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', filename)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)

    return response
  })
}

// 删除字幕生成任务
export function deleteSubtitleGenerateTask(taskId) {
  return api.delete(`/subtitle-generate/task/${taskId}`)
}

// ========== 字幕音频分割API ==========

// 上传文件进行音频分割
export function splitAudioBySubtitles(formData, onProgress) {
  return api.post('/subtitle-audio-split', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    onUploadProgress: (progressEvent) => {
      if (onProgress) {
        const percentCompleted = Math.round(
          (progressEvent.loaded * 100) / progressEvent.total
        )
        onProgress(percentCompleted)
      }
    }
  })
}

// 查询音频分割状态
export function getAudioSplitStatus(taskId) {
  return api.get(`/subtitle-audio-split/status/${taskId}`)
}

// 下载音频分割结果
export function downloadAudioSplitResult(taskId) {
  return api.get(`/subtitle-audio-split/download/${taskId}`, {
    responseType: 'blob'
  }).then(response => {
    // 从响应头获取文件名
    const contentDisposition = response.headers['content-disposition']
    let filename = `audio_split_${taskId}.zip`
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
      if (filenameMatch && filenameMatch[1]) {
        filename = filenameMatch[1].replace(/['"]/g, '')
      }
    }

    // 创建下载链接
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', filename)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)

    return response
  })
}

// 删除音频分割任务
export function deleteAudioSplitTask(taskId) {
  return api.delete(`/subtitle-audio-split/task/${taskId}`)
}

// ========== 音轨合成API ==========

// 上传文件进行音轨合成
export function uploadAudioMix(formData, onProgress) {
  return api.post('/audio-mix', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    onUploadProgress: (progressEvent) => {
      if (onProgress) {
        const percentCompleted = Math.round(
          (progressEvent.loaded * 100) / progressEvent.total
        )
        onProgress(percentCompleted)
      }
    }
  })
}

// 查询音轨合成状态
export function getAudioMixStatus(taskId) {
  return api.get(`/audio-mix/status/${taskId}`)
}

// 下载音轨合成结果
export function downloadAudioMixResult(taskId) {
  return api.get(`/audio-mix/download/${taskId}`, {
    responseType: 'blob'
  }).then(response => {
    // 从响应头获取文件名
    const contentDisposition = response.headers['content-disposition']
    let filename = `final_audio_${taskId}.mp3`
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
      if (filenameMatch && filenameMatch[1]) {
        filename = filenameMatch[1].replace(/['"]/g, '')
      }
    }

    // 创建下载链接
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', filename)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)

    return response
  })
}

// 删除音轨合成任务
export function deleteAudioMixTask(taskId) {
  return api.delete(`/audio-mix/task/${taskId}`)
}

export default api
