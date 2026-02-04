# 视频重新剪辑工具使用指南

这个工具可以根据新字幕的时间戳重新剪辑原视频，达到更好的声音、画面与字幕同步效果。

## 工具说明

### 1. 字幕时间分析工具 (analyze_subtitle_timings.py)

用于分析原字幕和新字幕的时间戳差异，生成分析报告和FFmpeg命令。

**使用方法：**

```bash
python analyze_subtitle_timings.py <原字幕.srt> <新字幕.srt> [视频文件.mp4]
```

**示例：**

```bash
python analyze_subtitle_timings.py original_chinese.srt new_english.srt video.mp4
```

**功能：**
- 对比两个字幕文件的时间戳
- 分析开始时间偏移、持续时间偏移
- 生成视频剪辑片段建议
- 导出FFmpeg命令（如果提供视频文件）
- 生成JSON分析报告

### 2. 视频重新剪辑工具 (reclip_video_by_subtitles.py)

根据新字幕的时间戳自动重新剪辑视频。

**使用方法：**

```bash
python reclip_video_by_subtitles.py <视频文件.mp4> <新字幕.srt> [选项]
```

**选项：**
- `-o, --output`: 输出目录（默认：output）
- `-m, --merge-gap`: 合并相邻片段的间隙阈值，单位秒（默认：0.5）
- `--no-subtitle`: 不在视频中嵌入字幕
- `--hard-subtitle`: 使用硬字幕（烧录到画面）

**示例：**

```bash
# 基本用法：根据新字幕剪辑视频并嵌入软字幕
python reclip_video_by_subtitles.py video.mp4 new_subtitle.srt

# 自定义输出目录
python reclip_video_by_subtitles.py video.mp4 new_subtitle.srt -o my_output

# 合并间隙1秒以内的片段
python reclip_video_by_subtitles.py video.mp4 new_subtitle.srt -m 1.0

# 只剪辑视频，不嵌入字幕
python reclip_video_by_subtitles.py video.mp4 new_subtitle.srt --no-subtitle

# 嵌入硬字幕（烧录到画面）
python reclip_video_by_subtitles.py video.mp4 new_subtitle.srt --hard-subtitle
```

## 工作流程

### 推荐流程：

1. **分析字幕时间差异**
   ```bash
   python analyze_subtitle_timings.py original.srt new.srt
   ```
   查看分析报告，了解时间偏移情况

2. **重新剪辑视频**
   ```bash
   python reclip_video_by_subtitles.py video.mp4 new.srt -o output -m 0.5
   ```

3. **检查输出结果**
   - `reclipped_video.mp4`: 剪辑后的视频（不带字幕）
   - `final_with_subtitle.mp4`: 带新字幕的视频（软字幕）

## 输出文件说明

### analyze_subtitle_timings.py

- `subtitle_analysis_report.json`: 详细的分析报告，包含每条字幕的时间差异

### reclip_video_by_subtitles.py

- `reclipped_video.mp4`: 根据新字幕时间戳剪辑后的视频
- `final_with_subtitle.mp4`: 带新字幕的最终视频（软字幕，可开关）

## 依赖安装

```bash
pip install pysrt chardet
```

系统需要安装 FFmpeg：
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows
# 从 https://ffmpeg.org/download.html 下载
```

## 参数说明

### merge_gap (合并间隙阈值)

控制相邻片段是否合并：
- **0.5秒（默认）**: 大多数情况适用，保留自然的节奏
- **1.0秒或更大**: 适用于字幕之间有明显停顿的视频
- **0.1秒或更小**: 几乎不合并，保持每个字幕独立的片段

### 软字幕 vs 硬字幕

- **软字幕（默认）**:
  - 字幕作为独立轨道嵌入视频
  - 播放器可以开关字幕
  - 文件较小
  - 推荐用于大多数场景

- **硬字幕**:
  - 字幕烧录到画面中
  - 无法关闭，永久显示
  - 文件较大
  - 适用于社交媒体分享

## 常见问题

**Q: 为什么剪辑后的视频有黑屏或卡顿？**
A: 尝试调整 `merge_gap` 参数。过小的值会导致片段过多，建议增大到1.0-2.0秒。

**Q: 如何验证时间同步是否正确？**
A: 使用视频播放器打开输出文件，检查字幕与画面、声音是否同步。

**Q: 能否同时使用原字幕和新字幕？**
A: 可以运行两次工具，分别生成带不同字幕的版本，然后使用FFmpeg合并字幕轨道。

**Q: 处理大视频时内存不足？**
A: 工具使用FFmpeg的流式处理，内存占用较小。如仍有问题，可尝试先分段处理。

## 与现有项目的集成

如果你已经有一个视频处理项目（如videorecomp），可以这样集成：

```python
from reclip_video_by_subtitles import VideoReclipper

# 创建剪辑器
clipper = VideoReclipper(
    video_path="original_video.mp4",
    new_subtitle_path="new_subtitle.srt",
    output_dir="output"
)

# 执行剪辑
results = clipper.process(
    merge_gap=0.5,
    embed_subtitle=True,
    hard_subtitle=False
)

# 使用结果
reclipped_video = results['reclipped_video']
final_video = results['video_with_subtitle']
```

## 许可

本工具基于原videorecomp项目开发。
