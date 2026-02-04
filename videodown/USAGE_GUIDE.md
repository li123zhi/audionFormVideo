# 根据字幕重新剪辑视频 - 完整使用指南

## 问题概述

你有以下文件：
- 原视频文件（带中文配音和画面）
- 原中文字幕（对应原视频时间轴）
- 新英文字幕（时间戳可能与原字幕不同）

**目标**：重新剪辑原视频，使新视频与新英文字幕达到更好的声音、画面与字幕一致性。

## 解决方案

我为你创建了三个工具：

### 1. analyze_subtitle_timings.py - 字幕时间分析工具

**功能**：对比两个字幕文件的时间戳，分析差异

**使用方法**：
```bash
python analyze_subtitle_timings.py <原字幕.srt> <新字幕.srt> [视频文件.mp4]
```

**示例**：
```bash
# 只分析字幕，生成报告
python analyze_subtitle_timings.py example_original.srt example_new.srt

# 分析字幕并生成FFmpeg命令
python analyze_subtitle_timings.py example_original.srt example_new.srt video.mp4
```

**输出**：
- 控制台显示时间偏移统计
- `subtitle_analysis_report.json` - 详细分析报告
- FFmpeg命令列表（如果提供视频文件）

### 2. reclip_video_by_subtitles.py - 视频重新剪辑工具

**功能**：根据新字幕的时间戳自动重新剪辑视频

**使用方法**：
```bash
python reclip_video_by_subtitles.py <视频文件.mp4> <新字幕.srt> [选项]
```

**选项**：
- `-o, --output DIR` : 输出目录（默认：output）
- `-m, --merge-gap SEC` : 合并相邻片段的间隙阈值秒数（默认：0.5）
- `--no-subtitle` : 不嵌入字幕
- `--hard-subtitle` : 使用硬字幕（烧录到画面）

**示例**：
```bash
# 基本用法
python reclip_video_by_subtitles.py video.mp4 example_new.srt

# 自定义输出目录和合并阈值
python reclip_video_by_subtitles.py video.mp4 example_new.srt -o my_output -m 1.0

# 只剪辑视频，不嵌入字幕
python reclip_video_by_subtitles.py video.mp4 example_new.srt --no-subtitle

# 使用硬字幕
python reclip_video_by_subtitles.py video.mp4 example_new.srt --hard-subtitle
```

**输出**：
- `reclipped_video.mp4` - 剪辑后的视频（不带字幕）
- `final_with_subtitle.mp4` - 带新字幕的最终视频（软字幕）

### 3. quick_start_example.py - 快速开始示例

**功能**：自动化执行完整流程（分析 + 剪辑）

**使用方法**：
```bash
python quick_start_example.py <原视频.mp4> <原字幕.srt> <新字幕.srt>
```

**示例**：
```bash
python quick_start_example.py video.mp4 example_original.srt example_new.srt
```

**输出**：
- 自动执行分析、剪辑、嵌入字幕等所有步骤
- 所有输出文件保存在 `output/` 目录

## 快速开始

### 方法1：使用示例文件测试

```bash
# 1. 测试字幕分析
python test_subtitle_analysis.py

# 2. 查看分析报告
cat output/test_analysis_report.json
```

### 方法2：处理你自己的视频

```bash
# 1. 分析字幕时间差异
python analyze_subtitle_timings.py your_original.srt your_new.srt

# 2. 根据新字幕剪辑视频
python reclip_video_by_subtitles.py your_video.mp4 your_new.srt

# 3. 或者使用快速开始工具（自动完成所有步骤）
python quick_start_example.py your_video.mp4 your_original.srt your_new.srt
```

## 工作原理

### 1. 字幕时间分析

工具会对比每条字幕的：
- **开始时间偏移**：新字幕开始时间 - 原字幕开始时间
- **结束时间偏移**：新字幕结束时间 - 原字幕结束时间
- **持续时间偏移**：新字幕持续时间 - 原字幕持续时间

### 2. 视频剪辑流程

```
原视频 → 根据新字幕时间戳提取片段 → 合并相邻片段 → 拼接成新视频 → 嵌入字幕
```

### 3. 为什么要合并相邻片段？

如果字幕之间的间隙很小（比如0.5秒），直接剪辑会导致视频看起来卡顿。通过合并相邻片段，可以让视频更加流畅。

## 参数调优建议

### merge_gap（合并间隙阈值）

- **0.1-0.3秒**：几乎不合并，保持精确的字幕时间
  - 适用于：节奏紧凑的对话

- **0.5秒（默认）**：平衡选择
  - 适用于：大多数场景

- **1.0-2.0秒**：积极合并
  - 适用于：有自然停顿的视频
  - 优点：视频更流畅
  - 缺点：可能会保留一些不需要的画面

### 软字幕 vs 硬字幕

| 特性 | 软字幕 | 硬字幕 |
|------|--------|--------|
| 播放器支持 | 需要支持字幕轨道 | 所有播放器 |
| 字幕开关 | 可以开关 | 无法关闭 |
| 文件大小 | 较小 | 较大 |
| 适用场景 | 本地播放、YouTube | 社交媒体分享 |
| 推荐程度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

## 常见问题

### Q1: 剪辑后的视频有黑屏或卡顿？

**A**: 尝试增大 `merge_gap` 参数：
```bash
python reclip_video_by_subtitles.py video.mp4 new.srt -m 1.5
```

### Q2: 如何验证时间同步是否正确？

**A**: 使用视频播放器（如VLC）打开输出文件，检查：
1. 字幕出现的时间是否与对应的画面一致
2. 字幕持续时间是否合适
3. 画面切换是否与字幕同步

### Q3: 能否同时使用原字幕和新字幕？

**A**: 可以！运行两次工具，然后使用FFmpeg合并字幕轨道：

```bash
# 第一次：生成带原字幕的视频
python reclip_video_by_subtitles.py video.mp4 original.srt -o output1

# 第二次：生成带新字幕的视频
python reclip_video_by_subtitles.py video.mp4 new.srt -o output2

# 使用FFmpeg合并字幕轨道（这里需要手动操作）
```

### Q4: 处理大视频时内存不足？

**A**: 工具使用FFmpeg的流式处理，内存占用应该较小。如果仍有问题：
1. 确保关闭其他占用内存的程序
2. 检查磁盘空间（需要约2倍视频大小的临时空间）

### Q5: 新字幕时间戳完全不同怎么办？

**A**: 如果新字幕的时间戳与原视频完全不匹配，你需要：
1. 先调整新字幕的时间戳（使用字幕编辑工具如Subtitle Edit）
2. 或者提供原字幕，让工具计算时间偏移

## 高级用法

### 在Python代码中使用

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
    merge_gap=0.5,        # 合并0.5秒以内的间隙
    embed_subtitle=True,  # 嵌入字幕
    hard_subtitle=False   # 使用软字幕
)

# 使用结果
reclipped_video = results['reclipped_video']
final_video = results['video_with_subtitle']

print(f"剪辑后的视频: {reclipped_video}")
print(f"最终视频: {final_video}")
```

### 批量处理多个视频

```python
from pathlib import Path
from reclip_video_by_subtitles import VideoReclipper

videos_dir = Path("videos")
subtitles_dir = Path("subtitles")
output_dir = Path("output")

for video_file in videos_dir.glob("*.mp4"):
    # 查找对应的字幕文件
    subtitle_file = subtitles_dir / f"{video_file.stem}.srt"

    if subtitle_file.exists():
        print(f"处理: {video_file.name}")

        clipper = VideoReclipper(
            video_path=str(video_file),
            new_subtitle_path=str(subtitle_file),
            output_dir=str(output_dir / video_file.stem)
        )

        results = clipper.process()
        print(f"  ✅ 完成: {results.get('video_with_subtitle')}")
```

## 依赖安装

```bash
# Python依赖
pip install pysrt chardet

# 系统依赖：FFmpeg
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows：从 https://ffmpeg.org/download.html 下载
```

## 技术细节

### 时间戳处理

- SRT字幕时间戳格式：`HH:MM:SS,mmm`
- 工具内部转换为：秒（浮点数）
- 精度：毫秒级

### 视频剪辑方法

使用FFmpeg的 `-c copy` 选项：
- 不重新编码，速度快
- 保持原视频质量
- 但可能导致时间戳不精确（±1-2秒）

如果需要精确剪辑（±0.1秒），需要重新编码：
```python
# 修改 extract_video_segments 方法中的命令
cmd = [
    'ffmpeg', '-y',
    '-ss', str(start),
    '-i', self.video_path,
    '-t', str(duration),
    '-c:v', 'libx264',  # 重新编码视频
    '-c:a', 'aac',      # 重新编码音频
    str(output_file)
]
```

## 总结

根据你的需求（通过原字幕和新字幕重新剪辑视频），推荐使用以下流程：

1. **先分析**：使用 `analyze_subtitle_timings.py` 了解时间差异
2. **再剪辑**：使用 `reclip_video_by_subtitles.py` 自动剪辑视频
3. **验证结果**：用视频播放器检查同步效果
4. **调整参数**：根据效果调整 `merge_gap` 参数

如果需要帮助，查看：
- `README_VIDEO_RECLIP.md` - 详细文档
- `test_subtitle_analysis.py` - 测试示例
- `quick_start_example.py` - 完整示例

祝你使用顺利！
