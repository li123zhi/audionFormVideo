<template>
  <div class="video-recomp-page">
    <el-page-header @back="goBack" class="page-header">
      <template #content>
        <div class="page-title">
          <el-icon><Video-Camera /></el-icon>
          <span>视频处理工具</span>
        </div>
      </template>
    </el-page-header>

    <div class="video-processor">
      <el-tabs v-model="activeTab" class="function-tabs">
        <!-- 字幕视频生成 -->
        <el-tab-pane label="字幕视频生成" name="subtitle">
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
            <el-form-item label="原视频" required>
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

            <!-- 新字幕文件上传 -->
            <el-form-item label="新字幕文件" required>
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

            <!-- 原字幕文件上传（可选） -->
            <el-form-item label="原字幕文件">
              <el-upload
                ref="originalSrtUpload"
                class="upload-demo"
                drag
                :auto-upload="false"
                :limit="1"
                :on-change="(file) => handleFileChange(file, 'originalSrt')"
                :on-remove="() => handleFileRemove('originalSrt')"
                accept=".srt"
              >
                <el-icon class="el-icon--upload"><Document /></el-icon>
                <div class="el-upload__text">
                  拖拽原SRT文件到此处或 <em>点击上传</em>
                </div>
                <template #tip>
                  <div class="el-upload__tip">
                    原始字幕文件（可选），如果提供则生成原字幕版本的视频
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
                    ZIP文件包含多个音频片段，将按顺序拼接（可选）
                  </div>
                </template>
              </el-upload>
            </el-form-item>

            <!-- 功能选项 -->
            <el-divider content-position="left">功能选项</el-divider>

            <el-form-item label="AI音频分离">
              <el-switch
                v-model="processingOptions.enableAISeparation"
                active-text="启用"
                inactive-text="禁用"
              />
              <div class="el-upload__tip">
                从原视频中分离人声和伴奏，然后与配音混合（需要较长时间）
              </div>
            </el-form-item>

            <el-form-item label="生成不带字幕视频">
              <el-switch
                v-model="processingOptions.generateNoSubtitle"
                active-text="生成"
                inactive-text="不生成"
              />
              <div class="el-upload__tip">
                生成不带字幕的版本，包含新音频
              </div>
            </el-form-item>

            <!-- 字幕样式选项 -->
            <el-form-item label="字幕样式">
              <el-checkbox v-model="subtitleConfig.bold">加粗</el-checkbox>
              <el-checkbox v-model="subtitleConfig.italic">斜体</el-checkbox>
              <el-checkbox v-model="subtitleConfig.outline">描边</el-checkbox>
              <el-checkbox v-model="subtitleConfig.shadow">阴影</el-checkbox>
            </el-form-item>

            <el-form-item label="字体大小">
              <el-slider
                v-model="subtitleConfig.fontSize"
                :min="12"
                :max="48"
                :step="2"
                show-input
              />
            </el-form-item>

            <el-form-item label="字体颜色">
              <el-color-picker v-model="subtitleConfig.fontColor" show-alpha />
              <span style="margin-left: 10px;">{{ subtitleConfig.fontColor }}</span>
            </el-form-item>

            <el-form-item label="底部边距">
              <el-slider
                v-model="subtitleConfig.bottomMargin"
                :min="20"
                :max="200"
                :step="10"
                show-input
              />
              <div class="el-upload__tip">字幕距离视频底部的像素距离</div>
            </el-form-item>

            <el-form-item label="字幕宽度">
              <el-slider
                v-model="subtitleConfig.maxWidthRatio"
                :min="50"
                :max="100"
                :step="5"
                show-input
                :format-tooltip="(val) => val + '%'"
              />
              <div class="el-upload__tip">字幕最大宽度占视频宽度的百分比</div>
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
            {{ uploading ? '上传中...' : '开始生成' }}
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

      <!-- 处理进度 -->
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
            <el-step title="处理音频" :description="processProgress + '%'"></el-step>
            <el-step title="生成视频" :description="burnProgress + '%'"></el-step>
            <el-step title="完成"></el-step>
          </el-steps>

          <!-- 步骤详情 -->
          <div v-if="processingSteps.length > 0" style="margin-top: 30px;">
            <h4 style="margin-bottom: 15px;">处理步骤</h4>
            <el-timeline>
              <el-timeline-item
                v-for="step in processingSteps"
                :key="step.id"
                :type="getStepStatusType(step.status)"
                :icon="getStepIcon(step.status)"
                :color="getStepColor(step.status)"
              >
                <div class="step-item">
                  <div class="step-header">
                    <span class="step-name">{{ step.name }}</span>
                    <el-tag
                      :type="getStepTagType(step.status)"
                      size="small"
                      effect="plain"
                    >
                      {{ getStepStatusText(step.status) }}
                    </el-tag>
                  </div>
                  <div class="step-message">{{ step.message }}</div>
                </div>
              </el-timeline-item>
            </el-timeline>
          </div>

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
            <span>生成完成</span>
          </div>
        </template>

        <div class="result-content">
          <el-alert
            title="视频生成成功！"
            type="success"
            :closable="false"
            show-icon
          >
            <template #default>
              <p>已生成多个文件，请点击下方按钮下载</p>
            </template>
          </el-alert>

          <el-descriptions :column="1" border class="result-info">
            <el-descriptions-item label="任务ID">
              {{ taskId }}
            </el-descriptions-item>

            <!-- 视频文件 -->
            <el-descriptions-item label="视频文件">
              <div style="display: flex; flex-direction: column; gap: 8px;">
                <el-button type="success" size="small" @click="downloadFile('no_subtitle')" v-if="generatedFiles.no_subtitle">
                  <el-icon><Download /></el-icon>
                  下载不带字幕视频
                </el-button>
                <el-button type="primary" size="small" @click="downloadFile('new_soft_subtitle')" v-if="generatedFiles.new_soft_subtitle">
                  <el-icon><Download /></el-icon>
                  下载新字幕软字幕视频
                </el-button>
                <el-button type="warning" size="small" @click="downloadFile('new_hard_subtitle')" v-if="generatedFiles.new_hard_subtitle">
                  <el-icon><Download /></el-icon>
                  下载新字幕硬字幕视频
                </el-button>
                <el-button type="info" size="small" @click="downloadFile('original_soft_subtitle')" v-if="generatedFiles.original_soft_subtitle">
                  <el-icon><Download /></el-icon>
                  下载原字幕软字幕视频
                </el-button>
                <el-button type="warning" size="small" @click="downloadFile('original_hard_subtitle')" v-if="generatedFiles.original_hard_subtitle">
                  <el-icon><Download /></el-icon>
                  下载原字幕硬字幕视频
                </el-button>
              </div>
            </el-descriptions-item>

            <!-- 音频文件 -->
            <el-descriptions-item label="音频文件" v-if="hasAudioFiles">
              <div style="display: flex; flex-direction: column; gap: 8px;">
                <el-button type="info" size="small" @click="downloadFile('merged_audio')" v-if="generatedFiles.merged_audio">
                  <el-icon><Download /></el-icon>
                  下载合并配音音频
                </el-button>
                <el-button type="info" size="small" @click="downloadFile('mixed_audio')" v-if="generatedFiles.mixed_audio">
                  <el-icon><Download /></el-icon>
                  下载伴奏混合音频
                </el-button>
                <el-button type="info" size="small" @click="downloadFile('vocals')" v-if="generatedFiles.vocals">
                  <el-icon><Download /></el-icon>
                  下载人声
                </el-button>
                <el-button type="info" size="small" @click="downloadFile('no_vocals')" v-if="generatedFiles.no_vocals">
                  <el-icon><Download /></el-icon>
                  下载伴奏
                </el-button>
              </div>
            </el-descriptions-item>
          </el-descriptions>

          <div class="result-actions">
            <el-button @click="handleReset">
              <el-icon><RefreshRight /></el-icon>
              重新生成
            </el-button>
          </div>
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
          <h4>📝 功能说明</h4>
          <ul>
            <li><strong>原视频</strong>：需要添加字幕的视频文件（必需）</li>
            <li><strong>新字幕文件</strong>：SRT格式的字幕文件（必需）</li>
            <li><strong>配音文件</strong>：ZIP格式的音频片段压缩包（可选）</li>
          </ul>

          <h4>🎬 生成内容</h4>
          <ul>
            <li><strong>软字幕视频</strong>：字幕嵌入到视频容器中，播放时可开关</li>
            <li><strong>硬字幕视频</strong>：字幕烧录到画面上，无法关闭</li>
            <li><strong>配音文件</strong>：如果上传，会将配音替换到视频中</li>
          </ul>

          <h4>💡 使用建议</h4>
          <ul>
            <li>推荐使用软字幕视频，灵活性更高</li>
            <li>硬字幕视频适合在不支持外挂字幕的平台播放</li>
            <li>配音文件可选，如果不上传则保留原视频音频</li>
          </ul>

          <h4>⚙️ 字幕样式</h4>
          <ul>
            <li>可以自定义字幕的字体、大小、颜色等样式</li>
            <li>样式仅在硬字幕视频中生效</li>
            <li>软字幕视频使用默认样式</li>
          </ul>
        </div>
      </el-card>
        </el-tab-pane>

        <!-- 音频分割 -->
        <el-tab-pane label="音频分割" name="audio-split">
          <el-card class="main-card">
            <template #header>
              <div class="card-header">
                <el-icon><Headset /></el-icon>
                <span>根据字幕分割音频</span>
              </div>
            </template>

            <!-- 上传区域 -->
            <div class="upload-section">
              <el-form label-width="120px">
                <!-- 字幕文件上传 -->
                <el-form-item label="字幕文件" required>
                  <el-upload
                    ref="srtUpload2"
                    class="upload-demo"
                    drag
                    :auto-upload="false"
                    :limit="1"
                    :on-change="(file) => handleAudioSplitFileChange(file, 'srt')"
                    :on-remove="() => handleAudioSplitFileRemove('srt')"
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

                <!-- 视频/音频文件上传 -->
                <el-form-item label="视频/音频" required>
                  <el-upload
                    ref="mediaUpload"
                    class="upload-demo"
                    drag
                    :auto-upload="false"
                    :limit="1"
                    :on-change="(file) => handleAudioSplitFileChange(file, 'media')"
                    :on-remove="() => handleAudioSplitFileRemove('media')"
                    accept="video/*,audio/*"
                  >
                    <el-icon class="el-icon--upload"><Folder-Opened /></el-icon>
                    <div class="el-upload__text">
                      拖拽视频或音频文件到此处或 <em>点击上传</em>
                    </div>
                    <template #tip>
                      <div class="el-upload__tip">
                        支持视频文件（MP4等）或音频文件（MP3等）（必需）
                      </div>
                    </template>
                  </el-upload>
                </el-form-item>

                <!-- 选项 -->
                <el-form-item label="生成静音">
                  <el-checkbox v-model="audioSplitConfig.useSilence">
                    在字幕间隙生成静音文件
                  </el-checkbox>
                  <div class="el-upload__tip">生成字幕之间的静音片段，便于完整还原时间轴</div>
                </el-form-item>
              </el-form>
            </div>

            <!-- 操作按钮 -->
            <div class="action-buttons">
              <el-button
                type="primary"
                size="large"
                :disabled="!canStartAudioSplit"
                :loading="audioSplitting.uploading"
                @click="handleAudioSplit"
              >
                <el-icon><Video-Camera /></el-icon>
                {{ audioSplitting.uploading ? '处理中...' : '开始分割' }}
              </el-button>
            </div>

            <!-- 进度显示 -->
            <el-card v-if="audioSplitting.processing" class="progress-card" style="margin-top: 20px;">
              <template #header>
                <div class="card-header">
                  <el-icon><Loading /></el-icon>
                  <span>处理进度</span>
                </div>
              </template>

              <div class="progress-content">
                <el-progress :percentage="audioSplitting.progress" :status="audioSplitting.status" />
                <div class="status-text">
                  <p>{{ audioSplitting.message }}</p>
                </div>
              </div>
            </el-card>

            <!-- 结果下载 -->
            <el-card v-if="audioSplitting.completed" class="result-card" style="margin-top: 20px;">
              <template #header>
                <div class="card-header">
                  <el-icon><Circle-Check /></el-icon>
                  <span>分割完成</span>
                </div>
              </template>

              <div class="result-content">
                <el-alert
                  title="音频分割成功！"
                  type="success"
                  :closable="false"
                  show-icon
                >
                  <template #default>
                    <p>已生成 {{ audioSplitting.fileCount }} 个音频文件，点击下方按钮下载</p>
                  </template>
                </el-alert>

                <el-descriptions :column="1" border class="result-info">
                  <el-descriptions-item label="任务ID">
                    {{ audioSplitting.taskId }}
                  </el-descriptions-item>
                  <el-descriptions-item label="音频文件">
                    <el-button type="success" @click="handleDownloadAudioSplit">
                      <el-icon><Download /></el-icon>
                      下载所有音频（ZIP）
                    </el-button>
                    <div class="el-upload__tip">包含所有字幕音频和静音文件</div>
                  </el-descriptions-item>
                </el-descriptions>

                <div class="result-actions">
                  <el-button @click="handleAudioSplitReset">
                    <el-icon><RefreshRight /></el-icon>
                    重新分割
                  </el-button>
                </div>
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
                <h4>📝 功能说明</h4>
                <ul>
                  <li><strong>字幕文件</strong>：SRT格式的字幕文件（必需）</li>
                  <li><strong>视频/音频</strong>：提供视频或音频文件（必需）</li>
                  <li><strong>生成静音</strong>：在字幕间隙生成静音文件（可选）</li>
                </ul>

                <h4>🎬 输出内容</h4>
                <ul>
                  <li><strong>字幕音频</strong>：每个字幕对应一个MP3文件</li>
                  <li><strong>静音文件</strong>：字幕之间的间隙用静音填充</li>
                  <li><strong>命名规则</strong>：subtitle_001_0.500-3.200.mp3</li>
                </ul>

                <h4>💡 使用场景</h4>
                <ul>
                  <li>配音制作：将长音频分割成短片段便于编辑</li>
                  <li>音频教学：按字幕组织音频内容</li>
                  <li>无障碍制作：为视频生成音频描述</li>
                </ul>
              </div>
            </el-card>
          </el-card>
        </el-tab-pane>

        <!-- 音轨合成 -->
        <el-tab-pane label="音轨合成" name="audio-mix">
          <el-card class="main-card">
            <template #header>
              <div class="card-header">
                <el-icon><Headset /></el-icon>
                <span>分离人声伴奏并合成配音音轨</span>
              </div>
            </template>

            <!-- 上传区域 -->
            <div class="upload-section">
              <el-form label-width="140px">
                <!-- 视频文件上传 -->
                <el-form-item label="原视频文件" required>
                  <el-upload
                    ref="videoUpload3"
                    class="upload-demo"
                    drag
                    :auto-upload="false"
                    :limit="1"
                    :on-change="(file) => handleAudioMixFileChange(file, 'video')"
                    :on-remove="() => handleAudioMixFileRemove('video')"
                    accept="video/*"
                  >
                    <el-icon class="el-icon--upload"><Video-Camera /></el-icon>
                    <div class="el-upload__text">
                      拖拽视频文件到此处或 <em>点击上传</em>
                    </div>
                    <template #tip>
                      <div class="el-upload__tip">
                        支持MP4、AVI、MOV等格式（用于分离人声和伴奏）
                      </div>
                    </template>
                  </el-upload>
                </el-form-item>

                <!-- 字幕文件上传 -->
                <el-form-item label="字幕文件" required>
                  <el-upload
                    ref="srtUpload3"
                    class="upload-demo"
                    drag
                    :auto-upload="false"
                    :limit="1"
                    :on-change="(file) => handleAudioMixFileChange(file, 'srt')"
                    :on-remove="() => handleAudioMixFileRemove('srt')"
                    accept=".srt"
                  >
                    <el-icon class="el-icon--upload"><Document /></el-icon>
                    <div class="el-upload__text">
                      拖拽SRT文件到此处或 <em>点击上传</em>
                    </div>
                    <template #tip>
                      <div class="el-upload__tip">
                        SRT字幕文件（用于按时间轴合并配音音轨）
                      </div>
                    </template>
                  </el-upload>
                </el-form-item>

                <!-- 配音音频文件夹上传 -->
                <el-form-item label="配音音频文件夹">
                  <el-upload
                    ref="dubbingUpload"
                    class="upload-demo"
                    drag
                    :auto-upload="false"
                    :limit="1"
                    :on-change="(file) => handleAudioMixFileChange(file, 'dubbing')"
                    :on-remove="() => handleAudioMixFileRemove('dubbing')"
                    accept=".zip"
                  >
                    <el-icon class="el-icon--upload"><Folder-Opened /></el-icon>
                    <div class="el-upload__text">
                      拖拽配音音频ZIP到此处或 <em>点击上传</em>
                    </div>
                    <template #tip>
                      <div class="el-upload__tip">
                        包含多个MP3配音文件的ZIP压缩包（可选，如果不上传则只分离人声伴奏）
                      </div>
                    </template>
                  </el-upload>
                </el-form-item>

                <!-- 操作按钮 -->
                <el-form-item>
                  <el-button
                    type="primary"
                    size="large"
                    :loading="audioMixProcessing"
                    :disabled="!canStartAudioMix"
                    @click="handleAudioMix"
                  >
                    <el-icon v-if="!audioMixProcessing"><Video-Play /></el-icon>
                    {{ audioMixProcessing ? '处理中...' : '开始处理' }}
                  </el-button>

                  <el-button
                    v-if="audioMixCompleted"
                    type="success"
                    size="large"
                    @click="downloadAudioMixResult"
                  >
                    <el-icon><Download /></el-icon>
                    下载结果
                  </el-button>

                  <el-button
                    v-if="audioMixProcessing || audioMixCompleted"
                    type="danger"
                    size="large"
                    @click="resetAudioMix"
                  >
                    <el-icon><Refresh-Left /></el-icon>
                    重新开始
                  </el-button>

                  <el-button
                    v-if="audioMixProcessing"
                    type="warning"
                    size="large"
                    @click="cancelAudioMix"
                  >
                    <el-icon><Close-Bold /></el-icon>
                    取消任务
                  </el-button>
                </el-form-item>
              </el-form>
            </div>

            <!-- 处理结果 -->
            <div v-if="audioMixProcessing || audioMixCompleted" class="result-section">
              <el-card class="result-card">
                <template #header>
                  <div class="card-header">
                    <el-icon><Data-Analysis /></el-icon>
                    <span>处理进度</span>
                  </div>
                </template>

                <!-- 进度条 -->
                <div v-if="audioMixProcessing" class="progress-wrapper">
                  <el-progress
                    :percentage="audioMixProgress"
                    :status="audioMixProgressStatus"
                    :stroke-width="26"
                  >
                    <span class="progress-text">{{ audioMixProgress }}%</span>
                  </el-progress>
                  <div class="progress-message">{{ audioMixStatusMessage }}</div>

                  <!-- 详细步骤列表 -->
                  <div class="steps-list" style="margin-top: 20px;">
                    <el-timeline>
                      <el-timeline-item
                        v-for="step in audioMixTaskDetails.steps || []"
                        :key="step.id"
                        :type="getStepStatusType(step.status)"
                        :icon="getStepIcon(step.status)"
                        :color="getStepColor(step.status)"
                      >
                        <div class="step-item">
                          <div class="step-header">
                            <span class="step-name">{{ step.name }}</span>
                            <el-tag
                              :type="getStepTagType(step.status)"
                              size="small"
                              effect="plain"
                            >
                              {{ getStepStatusText(step.status) }}
                            </el-tag>
                          </div>
                          <div class="step-message">{{ step.message }}</div>
                        </div>
                      </el-timeline-item>
                    </el-timeline>
                  </div>
                </div>

                <!-- 完成状态 -->
                <div v-if="audioMixCompleted" class="success-section">
                  <el-result
                    icon="success"
                    title="音轨合成完成"
                    :sub-title="`处理时长: ${audioMixProcessingTime}秒`"
                  >
                    <template #extra>
                      <el-descriptions :column="1" border>
                        <el-descriptions-item label="任务ID">{{ audioMixTaskId }}</el-descriptions-item>
                        <el-descriptions-item label="原视频">{{ audioMixFiles.video?.name }}</el-descriptions-item>
                        <el-descriptions-item label="字幕文件">{{ audioMixFiles.srt?.name }}</el-descriptions-item>
                        <el-descriptions-item label="配音文件">{{ audioMixFiles.dubbing?.name || '无' }}</el-descriptions-item>
                        <el-descriptions-item label="人声分离">{{ audioMixTaskDetails.skip_separation ? '跳过（使用提供文件）' : '完成' }}</el-descriptions-item>
                        <el-descriptions-item label="配音合并">{{ audioMixFiles.dubbing ? '完成' : '跳过' }}</el-descriptions-item>
                        <el-descriptions-item label="最终音轨">已生成</el-descriptions-item>
                      </el-descriptions>

                      <!-- 完成的步骤列表 -->
                      <div class="completed-steps" style="margin-top: 24px;">
                        <h4 style="margin-bottom: 16px;">处理步骤</h4>
                        <el-timeline>
                          <el-timeline-item
                            v-for="step in audioMixTaskDetails.steps || []"
                            :key="step.id"
                            type="success"
                            icon="CircleCheck"
                          >
                            <div class="step-item">
                              <div class="step-header">
                                <span class="step-name">{{ step.name }}</span>
                                <el-tag type="success" size="small" effect="plain">完成</el-tag>
                              </div>
                              <div class="step-message">{{ step.message }}</div>
                            </div>
                          </el-timeline-item>
                        </el-timeline>
                      </div>
                    </template>
                  </el-result>
                </div>

                <!-- 说明 -->
                <div class="info-section">
                  <el-alert
                    title="音轨合成说明"
                    type="info"
                    :closable="false"
                  >
                    <template #default>
                      <ul>
                        <li><strong>人声分离：</strong>使用demucs从原视频中分离出人声和伴奏</li>
                        <li><strong>配音合并：</strong>按字幕时间轴将多个配音文件合并，间隙填充静音</li>
                        <li><strong>音轨混合：</strong>将人声、配音、伴奏按比例混合成最终音轨</li>
                        <li><strong>输出文件：</strong>最终输出MP3格式的混合音轨文件</li>
                      </ul>
                    </template>
                  </el-alert>
                </div>
              </el-card>
            </div>
          </el-card>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  VideoCamera,
  Film,
  UploadFilled,
  Document,
  FolderOpened,
  Loading,
  CircleCheck,
  Download,
  Close,
  RefreshRight,
  InfoFilled,
  Headset,
  VideoPlay,
  RefreshLeft,
  CloseBold,
  DataAnalysis,
  Clock,
  CircleClose
} from '@element-plus/icons-vue'
import {
  generateSubtitleVideos,
  getSubtitleGenerateStatus,
  downloadSubtitleVideo,
  splitAudioBySubtitles,
  getAudioSplitStatus,
  downloadAudioSplitResult,
  uploadAudioMix,
  getAudioMixStatus,
  downloadAudioMixResult as downloadAudioMixResultApi,
  deleteAudioMixTask
} from '../services/api'

const router = useRouter()

// 当前激活的标签页
const activeTab = ref('subtitle')

// 文件存储
const files = ref({
  video: null,
  srt: null,
  originalSrt: null,  // 新增：原字幕文件
  audio: null
})

// 字幕配置
const subtitleConfig = ref({
  fontSize: 24,
  fontColor: '#FFFFFF',
  bold: false,
  italic: false,
  outline: true,
  shadow: true,
  bottomMargin: 50,
  maxWidthRatio: 90
})

// 处理选项
const processingOptions = ref({
  enableAISeparation: false,  // 是否启用AI音频分离
  generateNoSubtitle: true    // 是否生成不带字幕的视频
})

// 状态
const uploading = ref(false)
const processing = ref(false)
const completed = ref(false)
const taskId = ref(null)
const hasAudio = ref(false)

// 进度
const uploadProgress = ref(0)
const processProgress = ref(0)
const burnProgress = ref(0)
const currentStep = ref(0)
const statusMessage = ref('')

// 处理步骤列表
const processingSteps = ref([])

// 生成的文件
const generatedFiles = ref({
  no_subtitle: null,
  new_soft_subtitle: null,
  new_hard_subtitle: null,
  original_soft_subtitle: null,
  original_hard_subtitle: null,
  merged_audio: null,
  mixed_audio: null,
  vocals: null,
  no_vocals: null
})

// 是否有音频文件
const hasAudioFiles = computed(() => {
  return generatedFiles.value.merged_audio ||
         generatedFiles.value.mixed_audio ||
         generatedFiles.value.vocals ||
         generatedFiles.value.no_vocals
})

// 检查是否可以上传
const canUpload = computed(() => {
  return files.value.video && files.value.srt && !uploading.value && !processing.value
})

// 处理文件选择
const handleFileChange = (file, type) => {
  files.value[type] = file.raw
}

// 处理文件移除
const handleFileRemove = (type) => {
  files.value[type] = null
}

// 上传并处理
const handleUpload = async () => {
  if (!canUpload.value) {
    ElMessage.warning('请先上传原视频和新字幕文件')
    return
  }

  try {
    uploading.value = true
    currentStep.value = 0
    uploadProgress.value = 0
    processProgress.value = 0
    burnProgress.value = 0
    statusMessage.value = '正在上传文件...'

    // 重置处理步骤和生成的文件
    processingSteps.value = []
    generatedFiles.value = {
      no_subtitle: null,
      new_soft_subtitle: null,
      new_hard_subtitle: null,
      original_soft_subtitle: null,
      original_hard_subtitle: null,
      merged_audio: null,
      mixed_audio: null,
      vocals: null,
      no_vocals: null
    }

    // 创建FormData
    const formData = new FormData()
    formData.append('video', files.value.video)
    formData.append('srt', files.value.srt)

    // 添加原字幕文件（如果提供）
    if (files.value.originalSrt) {
      formData.append('original_srt', files.value.originalSrt)
    }

    if (files.value.audio) {
      formData.append('audio', files.value.audio)
    }

    // 添加字幕配置（将 maxWidthRatio 从百分比转换为小数）
    const config = { ...subtitleConfig.value }
    config.maxWidthRatio = config.maxWidthRatio / 100
    formData.append('subtitle_config', JSON.stringify(config))

    // 添加处理选项
    formData.append('enable_ai_separation', processingOptions.value.enableAISeparation ? 'true' : 'false')
    formData.append('generate_no_subtitle', processingOptions.value.generateNoSubtitle ? 'true' : 'false')

    // 上传文件
    const response = await generateSubtitleVideos(formData, (progress) => {
      uploadProgress.value = progress
    })

    taskId.value = response.task_id
    hasAudio.value = !!files.value.audio

    ElMessage.success('任务创建成功，开始处理...')

    uploading.value = false
    processing.value = true
    currentStep.value = 1

    // 开始轮询任务状态
    pollTaskStatus()

  } catch (error) {
    console.error('上传失败:', error)
    ElMessage.error(error.message || '上传失败')
    uploading.value = false
  }
}

// 轮询任务状态
const pollTaskStatus = async () => {
  if (!taskId.value) return

  try {
    const status = await getSubtitleGenerateStatus(taskId.value)

    // 更新进度
    if (status.step === 'processing') {
      processProgress.value = status.progress || 0
      statusMessage.value = status.message || '正在处理...'
      currentStep.value = 1
    } else if (status.step === 'burning') {
      burnProgress.value = status.progress || 0
      statusMessage.value = status.message || '正在烧录字幕...'
      currentStep.value = 2
    } else {
      // 兼容旧的进度格式
      if (status.progress !== undefined) {
        if (currentStep.value === 1) {
          processProgress.value = status.progress
        } else if (currentStep.value === 2) {
          burnProgress.value = status.progress
        }
      }
    }

    // 更新处理步骤
    if (status.steps && Array.isArray(status.steps)) {
      processingSteps.value = status.steps
    }

    // 更新生成的文件
    if (status.files) {
      generatedFiles.value = {
        ...generatedFiles.value,
        ...status.files
      }
    }

    if (status.status === 'completed') {
      processing.value = false
      completed.value = true
      currentStep.value = 3
      statusMessage.value = '处理完成！'

      // 保存生成的文件
      if (status.files) {
        generatedFiles.value = status.files
      }

      ElMessage.success('视频生成成功！')
      return
    }

    if (status.status === 'failed') {
      processing.value = false
      ElMessage.error(status.error || '处理失败')
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

// 下载生成的文件
const downloadFile = async (fileType) => {
  if (!taskId.value) {
    ElMessage.warning('任务不存在')
    return
  }

  try {
    // 根据文件类型映射到后端的下载接口
    const fileTypeMap = {
      'no_subtitle': 'no_subtitle',
      'new_soft_subtitle': 'soft',
      'new_hard_subtitle': 'hard',
      'original_soft_subtitle': 'original_soft',
      'original_hard_subtitle': 'original_hard',
      'merged_audio': 'merged_audio',
      'mixed_audio': 'mixed_audio',
      'vocals': 'vocals',
      'no_vocals': 'no_vocals'
    }

    const downloadType = fileTypeMap[fileType]
    if (!downloadType) {
      ElMessage.error('不支持的文件类型')
      return
    }

    await downloadSubtitleVideo(taskId.value, downloadType)
    ElMessage.success('下载成功')
  } catch (error) {
    console.error('下载失败:', error)
    ElMessage.error(error.message || '下载失败')
  }
}

// 取消任务
const handleCancel = () => {
  // TODO: 实现取消任务功能
  ElMessage.info('取消任务功能开发中')
}

// 重置
const handleReset = () => {
  files.value = {
    video: null,
    srt: null,
    audio: null
  }
  uploading.value = false
  processing.value = false
  completed.value = false
  taskId.value = null
  hasAudio.value = false
  uploadProgress.value = 0
  processProgress.value = 0
  burnProgress.value = 0
  currentStep.value = 0
  statusMessage.value = ''
}

// ==================== 音频分割功能 ====================

// 音频分割文件存储
const audioSplitFiles = ref({
  srt: null,
  media: null
})

// 音频分割配置
const audioSplitConfig = ref({
  useSilence: true
})

// 音频分割状态
const audioSplitting = ref({
  uploading: false,
  processing: false,
  completed: false,
  progress: 0,
  message: '',
  status: '',
  taskId: null,
  fileCount: 0
})

// 检查是否可以开始音频分割
const canStartAudioSplit = computed(() => {
  return audioSplitFiles.value.srt && audioSplitFiles.value.media && !audioSplitting.value.uploading && !audioSplitting.value.processing
})

// 处理音频分割文件选择
const handleAudioSplitFileChange = (file, type) => {
  audioSplitFiles.value[type] = file.raw
}

// 处理音频分割文件移除
const handleAudioSplitFileRemove = (type) => {
  audioSplitFiles.value[type] = null
}

// 处理音频分割
const handleAudioSplit = async () => {
  if (!canStartAudioSplit.value) {
    ElMessage.warning('请先上传字幕文件和视频/音频文件')
    return
  }

  try {
    audioSplitting.value.uploading = true
    audioSplitting.value.progress = 0
    audioSplitting.value.message = '正在上传文件...'

    // 创建FormData
    const formData = new FormData()
    formData.append('srt', audioSplitFiles.value.srt)

    // 判断是视频还是音频
    if (audioSplitFiles.value.media.type.startsWith('video/')) {
      formData.append('video', audioSplitFiles.value.media)
    } else {
      formData.append('audio', audioSplitFiles.value.media)
    }

    formData.append('use_silence', audioSplitConfig.value.useSilence.toString())

    // 上传并开始处理
    const response = await splitAudioBySubtitles(formData, (progress) => {
      audioSplitting.value.progress = progress
    })

    audioSplitting.value.taskId = response.task_id
    audioSplitting.value.uploading = false
    audioSplitting.value.processing = true
    audioSplitting.value.message = '正在处理音频...'

    ElMessage.success('任务创建成功，开始处理...')

    // 开始轮询任务状态
    pollAudioSplitStatus()

  } catch (error) {
    console.error('音频分割失败:', error)
    ElMessage.error(error.message || '音频分割失败')
    audioSplitting.value.uploading = false
  }
}

// 轮询音频分割状态
const pollAudioSplitStatus = async () => {
  if (!audioSplitting.value.taskId) return

  try {
    const status = await getAudioSplitStatus(audioSplitting.value.taskId)

    audioSplitting.value.progress = status.progress || 0
    audioSplitting.value.message = status.message || '正在处理...'

    if (status.status === 'completed') {
      audioSplitting.value.processing = false
      audioSplitting.value.completed = true
      audioSplitting.value.progress = 100
      audioSplitting.value.status = 'success'
      audioSplitting.value.message = '处理完成！'
      audioSplitting.value.fileCount = status.audio_files?.length || 0

      ElMessage.success('音频分割成功！')
      return
    }

    if (status.status === 'failed') {
      audioSplitting.value.processing = false
      audioSplitting.value.status = 'exception'
      ElMessage.error(status.error || '处理失败')
      return
    }

    // 继续轮询
    setTimeout(pollAudioSplitStatus, 2000)

  } catch (error) {
    console.error('查询状态失败:', error)
    audioSplitting.value.processing = false
    ElMessage.error('查询状态失败')
  }
}

// 下载音频分割结果
const handleDownloadAudioSplit = async () => {
  if (!audioSplitting.value.taskId) {
    ElMessage.warning('任务不存在')
    return
  }

  try {
    await downloadAudioSplitResult(audioSplitting.value.taskId)
    ElMessage.success('下载成功')
  } catch (error) {
    console.error('下载失败:', error)
    ElMessage.error(error.message || '下载失败')
  }
}

// 重置音频分割
const handleAudioSplitReset = () => {
  audioSplitFiles.value = {
    srt: null,
    media: null
  }
  audioSplitting.value = {
    uploading: false,
    processing: false,
    completed: false,
    progress: 0,
    message: '',
    status: '',
    taskId: null,
    fileCount: 0
  }
}

// ==================== 音轨合成功能 ====================

// 音轨合成文件存储
const audioMixFiles = ref({
  video: null,
  srt: null,
  dubbing: null
})

// 音轨合成状态
const audioMixProcessing = ref(false)
const audioMixCompleted = ref(false)
const audioMixProgress = ref(0)
const audioMixProgressStatus = ref('')
const audioMixStatusMessage = ref('')
const audioMixTaskId = ref(null)
const audioMixStartTime = ref(null)
const audioMixTaskDetails = ref({})

// 计算属性：是否可以开始音轨合成
const canStartAudioMix = computed(() => {
  return audioMixFiles.value.video && audioMixFiles.value.srt && !audioMixProcessing.value
})

// 音轨合成处理时间
const audioMixProcessingTime = computed(() => {
  if (!audioMixStartTime.value) return 0
  return Math.round((Date.now() - audioMixStartTime.value) / 1000)
})

// 处理音轨合成文件选择
const handleAudioMixFileChange = (file, type) => {
  audioMixFiles.value[type] = file.raw
}

// 处理音轨合成文件移除
const handleAudioMixFileRemove = (type) => {
  audioMixFiles.value[type] = null
}

// 处理音轨合成
const handleAudioMix = async () => {
  if (!canStartAudioMix.value) {
    ElMessage.warning('请先上传视频文件和字幕文件')
    return
  }

  try {
    audioMixProcessing.value = true
    audioMixProgress.value = 0
    audioMixStatusMessage.value = '正在上传文件...'
    audioMixStartTime.value = Date.now()

    // 创建FormData
    const formData = new FormData()
    formData.append('video', audioMixFiles.value.video)
    formData.append('srt', audioMixFiles.value.srt)

    if (audioMixFiles.value.dubbing) {
      formData.append('dubbing_audio_dir', audioMixFiles.value.dubbing)
    }

    // 上传并开始处理
    const response = await uploadAudioMix(formData, (progress) => {
      audioMixProgress.value = progress
    })

    audioMixTaskId.value = response.data.task_id
    audioMixStatusMessage.value = '正在处理音轨合成...'

    ElMessage.success('任务创建成功，开始处理...')

    // 开始轮询任务状态
    pollAudioMixStatus()

  } catch (error) {
    console.error('音轨合成失败:', error)
    ElMessage.error(error.response?.data?.error || error.message || '音轨合成失败')
    audioMixProcessing.value = false
  }
}

// 轮询音轨合成状态
const pollAudioMixStatus = async () => {
  if (!audioMixTaskId.value) return

  try {
    const response = await getAudioMixStatus(audioMixTaskId.value)
    const status = response.data

    audioMixProgress.value = status.progress || 0
    audioMixStatusMessage.value = status.message || '正在处理...'
    audioMixTaskDetails.value = status

    if (status.status === 'completed') {
      audioMixProcessing.value = false
      audioMixCompleted.value = true
      audioMixProgress.value = 100
      audioMixProgressStatus.value = 'success'
      audioMixStatusMessage.value = '音轨合成完成！'
      ElMessage.success('音轨合成完成！')
    } else if (status.status === 'failed') {
      audioMixProcessing.value = false
      audioMixProgressStatus.value = 'exception'
      ElMessage.error(status.error || '音轨合成失败')
    } else {
      // 继续轮询
      setTimeout(pollAudioMixStatus, 2000)
    }

  } catch (error) {
    console.error('获取状态失败:', error)
    audioMixProcessing.value = false
    audioMixProgressStatus.value = 'exception'
    ElMessage.error('获取音轨合成状态失败')
  }
}

// 下载音轨合成结果
const downloadAudioMixResult = async () => {
  if (!audioMixTaskId.value) return

  try {
    await downloadAudioMixResultApi(audioMixTaskId.value)
    ElMessage.success('下载成功')
  } catch (error) {
    console.error('下载失败:', error)
    ElMessage.error(error.message || '下载失败')
  }
}

// 重置音轨合成
const resetAudioMix = () => {
  audioMixFiles.value = {
    video: null,
    srt: null,
    dubbing: null
  }
  audioMixProcessing.value = false
  audioMixCompleted.value = false
  audioMixProgress.value = 0
  audioMixProgressStatus.value = ''
  audioMixStatusMessage.value = ''
  audioMixTaskId.value = null
  audioMixStartTime.value = null
  audioMixTaskDetails.value = {}
}

// 取消音轨合成任务
const cancelAudioMix = async () => {
  if (!audioMixTaskId.value) return

  try {
    await deleteAudioMixTask(audioMixTaskId.value)
    ElMessage.success('任务已取消')
    resetAudioMix()
  } catch (error) {
    console.error('取消任务失败:', error)
    ElMessage.error('取消任务失败')
  }
}

// 步骤状态处理函数
const getStepStatusType = (status) => {
  const statusMap = {
    'pending': 'info',
    'processing': 'primary',
    'completed': 'success',
    'failed': 'danger'
  }
  return statusMap[status] || 'info'
}

const getStepIcon = (status) => {
  const iconMap = {
    'pending': Clock,
    'processing': Loading,
    'completed': CircleCheck,
    'failed': CircleClose
  }
  return iconMap[status] || Clock
}

const getStepColor = (status) => {
  const colorMap = {
    'pending': '#909399',
    'processing': '#409EFF',
    'completed': '#67C23A',
    'failed': '#F56C6C'
  }
  return colorMap[status] || '#909399'
}

const getStepTagType = (status) => {
  const typeMap = {
    'pending': 'info',
    'processing': 'primary',
    'completed': 'success',
    'failed': 'danger'
  }
  return typeMap[status] || 'info'
}

const getStepStatusText = (status) => {
  const textMap = {
    'pending': '等待中',
    'processing': '处理中',
    'completed': '已完成',
    'failed': '失败'
  }
  return textMap[status] || '未知'
}

// 返回
const goBack = () => {
  router.push('/')
}
</script>

<style scoped>
.video-recomp-page {
  padding: 20px;
  max-width: 1200px;
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

.video-processor {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.function-tabs {
  margin-top: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
}

.upload-section {
  margin-bottom: 20px;
}

.upload-demo {
  width: 100%;
}

:deep(.el-upload-dragger) {
  padding: 40px;
}

:deep(.el-icon--upload) {
  font-size: 67px;
  color: #409EFF;
}

.el-upload__text {
  font-size: 14px;
  color: #606266;
}

.el-upload__text em {
  color: #409EFF;
  font-style: normal;
}

.el-upload__tip {
  margin-top: 7px;
  font-size: 12px;
  color: #909399;
}

.action-buttons {
  display: flex;
  gap: 10px;
  justify-content: center;
  padding: 20px 0;
}

.progress-content {
  padding: 20px 0;
}

.status-text {
  margin-top: 20px;
  text-align: center;
}

.status-text p {
  font-size: 14px;
  color: #606266;
}

.result-content {
  padding: 10px 0;
}

.result-info {
  margin: 20px 0;
}

.result-actions {
  margin-top: 20px;
  text-align: center;
}

.info-content h4 {
  margin: 15px 0 10px 0;
  color: #409EFF;
}

.info-content ul {
  margin: 10px 0;
  padding-left: 20px;
}

.info-content li {
  margin: 8px 0;
  line-height: 1.6;
}

.info-content strong {
  color: #606266;
  font-weight: 600;
}

/* 步骤显示样式 */
.steps-list {
  padding: 10px 0;
}

.step-item {
  width: 100%;
}

.step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.step-name {
  font-size: 15px;
  font-weight: 500;
  color: #303133;
}

.step-message {
  font-size: 13px;
  color: #909399;
  line-height: 1.6;
}

.progress-wrapper {
  padding: 20px 0;
}

.progress-message {
  text-align: center;
  margin-top: 15px;
  font-size: 14px;
  color: #606266;
}

.progress-text {
  font-weight: 600;
  font-size: 16px;
}

.completed-steps {
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
}

.completed-steps h4 {
  margin: 0 0 16px 0;
  color: #303133;
  font-size: 16px;
  font-weight: 600;
}

.result-section {
  margin-top: 20px;
}

.result-card {
  border: 1px solid #ebeef5;
}

.success-section {
  padding: 20px 0;
}

.info-section {
  margin-top: 20px;
}
</style>
