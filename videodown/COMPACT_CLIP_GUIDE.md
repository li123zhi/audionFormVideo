# 🎬 紧凑剪辑功能 - 累积偏移算法

## 📖 功能说明

**紧凑剪辑**是一种新的视频剪辑算法，通过对比原字幕和新字幕的时间差异，累积计算偏移量，自动减掉不必要的时间，生成更紧凑的视频。

### 与普通剪辑的区别

| 特性 | 普通剪辑 | 紧凑剪辑 |
|-----|---------|---------|
| 算法 | 简单提取+拼接 | 累积偏移算法 |
| 视频时长 | 保留所有片段 | 精简去除多余部分 |
| 时间节省 | 无 | 显著减少 |
| 适用场景 | 通用 | 需要精简视频时 |

### 算法原理

```
原字幕1: 0-5秒
新字幕1: 0-4秒
差值: 1秒（新字幕短了1秒）

↓ 累积偏移 = 1秒

原字幕2: 6-10秒（原开始时间）
考虑偏移后: 实际在5-9秒的位置找对应内容

新字幕2: 4-8秒（已考虑前面剪掉的1秒）

↓ 如果新字幕2仍然较短，继续累积偏移

原字幕3: 11-15秒
考虑偏移后: 实际在9-13秒的位置找

... 以此类推
```

**关键点**：
- 每次剪辑都会影响后续所有字幕的时间
- 使用累积偏移量动态调整查找位置
- 最终视频更紧凑，时长更短

### 效果示例

假设原视频100秒，新字幕90秒：
- **普通剪辑**: 可能仍接近100秒（保留大部分内容）
- **紧凑剪辑**: 约90秒（减去约10秒多余内容）

节省比例可达10-30%！

---

## 🚀 使用方法

### 方式1：Web界面（推荐）

1. **打开"重新生成视频"页面**
2. **上传文件**：
   - 原视频
   - 原字幕
   - 新字幕
   - 配音ZIP

3. **启用"紧凑剪辑"模式**：
   ```
   ☑ 自动剪辑视频
     剪辑模式: ○ 普通  ● 紧凑（累积偏移）
   ```

4. **开始处理**
5. **查看结果**：
   - 节省的时间
   - 紧凑比例
   - 处理日志

### 方式2：API调用

```javascript
// 1. 上传文件
const formData = new FormData()
formData.append('video', videoFile)
formData.append('original_srt', originalSrtFile)
formData.append('new_srt', newSrtFile)
formData.append('use_precise', 'false')

const response = await uploadCompactClip(formData)
const taskId = response.data.task_id

// 2. 开始处理
await processCompactClip(taskId)

// 3. 轮询状态
const status = await getTaskStatus(taskId)
console.log(status.stats)
// {
//   time_saved: 12.5,  // 节省12.5秒
//   original_total_duration: 100.0,
//   new_total_duration: 87.5,
//   compact_ratio: 0.125  // 12.5%
// }
```

### 方式3：命令行工具

```bash
python compact_video_processor.py \
    video.mp4 \
    original.srt \
    new.srt
```

---

## 📊 处理日志

每次处理都会生成详细的日志：

```json
{
  "total_subtitles": 54,
  "matched_subtitles": 54,
  "final_cumulative_offset": -12.5,
  "original_total_duration": 100.0,
  "new_total_duration": 87.5,
  "time_saved": 12.5,
  "processing_log": [
    {
      "index": 1,
      "new_text": "快 快点划",
      "original_time": "0.70-1.87",
      "new_time_adjusted": "0.70-1.89",
      "duration_diff": "+0.02s",
      "cumulative_offset": "-0.02s"
    },
    {
      "index": 2,
      "new_text": "只要离开这片湖",
      "original_time": "2.03-3.07",
      "new_time_adjusted": "1.89-3.23",
      "duration_diff": "+0.16s",
      "cumulative_offset": "-0.18s"
    }
    // ... 更多字幕条目
  ]
}
```

### 字段说明

- `index`: 字幕序号
- `new_text`: 新字幕文本（前50字符）
- `original_time`: 原字幕时间
- `new_time_adjusted`: 调整后的新字幕时间
- `duration_diff`: 时长差值（+表示新字幕更长，-表示更短）
- `cumulative_offset`: 累积偏移量

---

## ⚙️ 算法详解

### 核心逻辑

```python
cumulative_offset = 0.0  # 初始化累积偏移

for each new_subtitle in new_subtitles:
    # 1. 找到匹配的原字幕（考虑累积偏移）
    target_start = new_subtitle.start + cumulative_offset
    original_subtitle = find_match(target_start)

    # 2. 计算时长差
    duration_diff = new_subtitle.duration - original_subtitle.duration

    # 3. 提取原字幕片段
    segments.append((original_subtitle.start, original_subtitle.end))

    # 4. 更新累积偏移
    cumulative_offset -= duration_diff
```

### 匹配算法

使用综合得分匹配原字幕：
- **时间接近度** (70%权重): 考虑累积偏移后的时间差距
- **文本相似度** (30%权重): 字幕文本的相似程度

```python
score = time_score * 0.7 + text_similarity * 0.3
```

### 优势

1. **智能**: 自动识别字幕对应关系
2. **精确**: 考虑累积偏移，逐条调整
3. **高效**: 一次性处理，无需多次迭代
4. **可追溯**: 详细日志记录每条字幕的处理

---

## 💡 使用建议

### 什么时候使用紧凑剪辑？

✅ **推荐使用**：
- 新字幕比原字幕短很多
- 需要精简视频时长
- 配音节奏较快
- 社交媒体短视频（要求紧凑）

❌ **不推荐使用**：
- 字幕时间差异很大（无法匹配）
- 需要保留所有原视频内容
- 新字幕比原字幕更长（会增加时长）

### 参数选择

| 精确模式 | 速度 | 精度 | 推荐场景 |
|---------|------|------|---------|
| 关闭 | ⚡⚡⚡ 快 | ±1-2秒 | 大多数情况 |
| 开启 | ⚡ 慢 | ±0.1秒 | 需要高精度时 |

---

## 🔍 对比示例

### 示例1：短视频精简

**原视频**: 60秒
**原字幕**: 30条，总时长60秒
**新字幕**: 30条，总时长45秒（配音更快）

**普通剪辑**:
- 提取30个片段
- 拼接后约58秒（保留了片段间的间隙）

**紧凑剪辑**:
- 累积计算偏移
- 拼接后约45秒（去除所有多余间隙）
- **节省时间**: 15秒（25%）

### 示例2：长视频缩编

**原视频**: 10分钟
**原字幕**: 300条，总时长600秒
**新字幕**: 300条，总时长480秒（缩编20%）

**紧凑剪辑效果**:
- 节省时间: 120秒（2分钟）
- 紧凑比例: 20%
- 最终时长: 8分钟

---

## 🎯 最佳实践

1. **先分析后处理**
   ```bash
   # 先分析字幕时间差异
   python analyze_subtitle_timings.py original.srt new.srt

   # 查看报告中的时长差异
   # 如果新字幕明显更短，使用紧凑剪辑
   ```

2. **测试处理**
   - 先用1-2个视频测试效果
   - 查看处理日志，确认匹配正确
   - 检查最终视频的流畅度

3. **调整参数**
   - 如果匹配不准确，启用精确模式
   - 如果有字幕没匹配上，查看日志分析原因

4. **保存日志**
   ```bash
   # 处理日志保存在输出目录
   ls output/compact_clip_*/processing_log.json
   ```

---

## 📝 API接口

### 上传文件
```http
POST /api/compact-clip
Content-Type: multipart/form-data

Body:
- video: 视频文件
- original_srt: 原字幕
- new_srt: 新字幕
- use_precise: false (可选)

Response:
{
  "task_id": "uuid",
  "message": "将使用累积偏移算法生成紧凑视频"
}
```

### 处理任务
```http
POST /api/process-compact/{task_id}

Response:
{
  "status": "processing",
  "message": "开始紧凑剪辑处理"
}
```

### 获取状态
```http
GET /api/status/{task_id}

Response:
{
  "status": "completed",
  "stats": {
    "time_saved": 12.5,
    "original_total_duration": 100.0,
    "new_total_duration": 87.5
  }
}
```

---

## 🐛 故障排除

### 问题1：节省时间为0或很少

**原因**: 新字幕和原字幕时长相近

**解决**: 这是正常的，如果时长差异小，节省的时间也会少

### 问题2：部分字幕未匹配

**原因**: 字幕文本差异太大，无法找到对应关系

**解决**:
- 查看处理日志，确认哪些字幕未匹配
- 检查字幕文本是否一致（只是时间不同）
- 考虑使用普通剪辑模式

### 问题3：视频不流畅

**原因**: 字幕匹配不准确，时间跳跃

**解决**:
- 启用精确模式提高匹配精度
- 检查原字幕和新字幕的文本是否对应

---

## 🎉 总结

紧凑剪辑通过**累积偏移算法**，智能地去除视频中多余的部分，生成更紧凑的视频：

✅ **节省时间**: 通常可节省10-30%的时长
✅ **保持流畅**: 智能匹配字幕对应关系
✅ **详细日志**: 每条字幕的处理都有记录
✅ **易于使用**: 一键处理，自动优化

**立即试用**：
```bash
cd videorecomp
./start-web.sh
# 打开 http://localhost:8080
# 选择"紧凑剪辑"模式
```
