# 字幕音频分割功能说明

## 功能概述

根据SRT字幕文件将音频分割成多个MP3文件，每个字幕对应一个音频片段，字幕之间的间隙使用静音填充。

## 使用方式

### API端点

#### 1. 上传并开始分割

**POST** `/api/subtitle-audio-split`

**请求参数:**
- `video`: 视频文件（可选，用于提取音频）
- `audio`: 音频文件（可选，如果提供则直接使用）
- `srt`: 字幕文件（必需）
- `use_silence`: 是否使用静音填充间隙（默认true）

**响应:**
```json
{
  "task_id": "uuid",
  "status": "processing",
  "message": "任务已创建，正在处理"
}
```

**注意:** 必须提供视频文件或音频文件之一

#### 2. 查询任务状态

**GET** `/api/subtitle-audio-split/status/{task_id}`

**响应:**
```json
{
  "task_id": "uuid",
  "status": "completed",
  "progress": 100,
  "message": "处理完成",
  "audio_files": [
    {
      "index": 1,
      "filename": "subtitle_001_0.500-3.200.mp3",
      "start": 0.5,
      "end": 3.2,
      "text": "字幕文本内容",
      "path": "/path/to/file.mp3"
    }
  ],
  "output_dir": "/path/to/output"
}
```

#### 3. 下载结果

**GET** `/api/subtitle-audio-split/download/{task_id}`

返回一个ZIP压缩包，包含所有生成的音频文件：
- 每个字幕对应的MP3文件（命名格式：`subtitle_XXX_start-end.mp3`）
- 静音片段文件（如果在`silences/`子目录中）

#### 4. 删除任务

**DELETE** `/api/subtitle-audio-split/task/{task_id}`

## 功能特性

### 1. 音频源支持
- ✅ 从视频文件中提取音频
- ✅ 直接使用音频文件（MP3、WAV等）
- ✅ 自动检测并处理

### 2. 字幕解析
- ✅ 解析SRT格式字幕文件
- ✅ 提取时间戳和文本
- ✅ 支持多条字幕

### 3. 音频分割
- ✅ 根据字幕时间戳精确分割
- ✅ 使用ffmpeg进行高质量处理
- ✅ 保持原始音频质量

### 4. 静音填充
- ✅ 自动计算字幕间隙
- ✅ 生成对应时长的静音MP3
- ✅ 可选功能（通过`use_silence`参数控制）

### 5. 文件组织
- ✅ 每个字幕对应一个MP3文件
- ✅ 命名格式：`subtitle_001_0.500-3.200.mp3`
- ✅ 静音文件放在`silences/`子目录
- ✅ 所有文件打包为ZIP下载

## 文件命名规则

### 字幕音频文件
```
subtitle_{序号:03d}_{开始时间:.3f}-{结束时间:.3f}.mp3
```

示例：
```
subtitle_001_0.500-3.200.mp3
subtitle_002_3.500-6.800.mp3
subtitle_003_7.000-10.500.mp3
```

### 静音文件
```
silence_{序号:03d}_{开始时间:.3f}-{结束时间:.3f}.mp3
```

示例：
```
silence_001_3.200-3.500.mp3
silence_002_6.800-7.000.mp3
```

## 技术实现

### 1. 从视频提取音频
```bash
ffmpeg -i video.mp4 -vn -acodec libmp3lame -q:a 2 audio.mp3
```

### 2. 分割音频片段
```bash
ffmpeg -ss {start_time} -t {duration} -i audio.mp3 -acodec copy segment.mp3
```

### 3. 生成静音
```bash
ffmpeg -f lavfi -i anullsrc=r=44100:cl=mono -t {duration} -acodec libmp3lame -q:a 2 silence.mp3
```

## 使用场景

1. **配音制作**
   - 将长音频按字幕分割成短片段
   - 便于逐句编辑和替换

2. **音频教学**
   - 将教学内容按字幕分割
   - 生成对应的音频片段供学习使用

3. **无障碍制作**
   - 为视频生成音频描述
   - 按段落组织音频内容

4. **音频分析**
   - 分析每段字幕对应的音频
   - 进行语音识别或情感分析

## 前端集成

前端需要调用以下API函数（已在 `api.js` 中实现）：

```javascript
import { splitAudioBySubtitles, getAudioSplitStatus, downloadAudioSplitResult } from '../services/api'

// 1. 上传并开始分割
const formData = new FormData()
formData.append('srt', srtFile)
formData.append('video', videoFile) // 或 audioFile
formData.append('use_silence', 'true')

const response = await splitAudioBySubtitles(formData)
const taskId = response.task_id

// 2. 轮询任务状态
const status = await getAudioSplitStatus(taskId)
console.log(status.progress, status.message)

// 3. 下载结果
await downloadAudioSplitResult(taskId)
```

## 注意事项

1. **文件大小**: 大型视频文件可能需要较长的处理时间
2. **格式支持**: 支持常见的视频和音频格式
3. **时间精度**: 音频分割精度为毫秒级
4. **质量设置**: 音频质量设置为 `-q:a 2`（高质量MP3）
5. **并发处理**: 支持多个任务同时处理

## 后续改进方向

- [ ] 支持批量处理多个字幕文件
- [ ] 添加音频格式转换选项
- [ ] 支持自定义输出格式（WAV、AAC等）
- [ ] 添加音频质量设置
- [ ] 支持字幕时间轴偏移调整
- [ ] 生成音频片段的预览功能
