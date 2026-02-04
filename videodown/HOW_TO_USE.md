# 如何使用 - 详细步骤说明

## 第一步：准备文件

将你的三个文件放到当前目录：

```
videodown/
├── your_video.mp4          # 你的原视频
├── original_chinese.srt    # 原中文字幕
└── new_english.srt         # 新英文字幕
```

## 第二步：快速测试

先测试字幕分析功能：

```bash
# 1. 确保你在正确的目录
cd /Users/ruite_ios/Desktop/aiShortVideo/videorecomp/videodown

# 2. 使用示例字幕测试
python test_subtitle_analysis.py

# 3. 查看分析结果
cat output/test_analysis_report.json
```

如果成功，你会看到类似输出：
```
加载字幕文件...
原字幕: 54 条
新字幕: 54 条

分析时间戳差异...
...
✅ 分析报告已保存到: output/test_analysis_report.json
```

## 第三步：处理你的视频

### 方法A：使用快速开始工具（最简单）

```bash
python quick_start_example.py your_video.mp4 original_chinese.srt new_english.srt
```

这个命令会：
1. ✅ 分析字幕时间差异
2. ✅ 根据新字幕剪辑视频
3. ✅ 嵌入新字幕
4. ✅ 保存到 output/ 目录

### 方法B：分步处理（更灵活）

```bash
# 步骤1：分析字幕时间差异
python analyze_subtitle_timings.py original_chinese.srt new_english.srt

# 步骤2：根据新字幕剪辑视频
python reclip_video_by_subtitles.py your_video.mp4 new_english.srt
```

### 方法C：使用bash脚本（最省事）

```bash
# 1. 编辑 run_example.sh，修改文件路径
nano run_example.sh

# 修改这几行：
# VIDEO_FILE="your_video.mp4"           # 改成你的视频文件名
# ORIGINAL_SRT="original_chinese.srt"   # 改成你的原字幕文件名
# NEW_SRT="new_english.srt"             # 改成你的新字幕文件名

# 2. 保存后运行
./run_example.sh
```

## 第四步：查看结果

处理完成后，检查 `output/` 目录：

```bash
# 查看输出文件
ls -lh output/

# 你会看到：
# reclipped_video.mp4       - 剪辑后的视频（不带字幕）
# final_with_subtitle.mp4   - 带新字幕的最终视频 ⭐推荐使用这个
# subtitle_analysis_report.json - 分析报告
```

## 第五步：验证结果

使用视频播放器打开 `output/final_with_subtitle.mp4`，检查：

- ✅ 字幕出现的时间是否与画面匹配
- ✅ 声音是否与字幕同步
- ✅ 视频过渡是否流畅

## 常见问题解决

### 问题1：提示找不到文件

```bash
❌ 文件不存在: your_video.mp4
```

**解决方法**：
```bash
# 检查文件是否存在
ls -la *.mp4
ls -la *.srt

# 使用绝对路径或相对路径
python quick_start_example.py ./your_video.mp4 ./original.srt ./new.srt
```

### 问题2：提示找不到Python或ffmpeg

```bash
❌ python: command not found
❌ ffmpeg: command not found
```

**解决方法**：
```bash
# 检查Python
python3 --version

# 检查ffmpeg
ffmpeg -version

# 如果ffmpeg未安装：
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg
```

### 问题3：视频有卡顿或不流畅

**解决方法**：调整合并间隙参数

```bash
# 增大合并间隙到1秒
python reclip_video_by_subtitles.py your_video.mp4 new.srt -m 1.0

# 或更大到2秒
python reclip_video_by_subtitles.py your_video.mp4 new.srt -m 2.0
```

### 问题4：字幕与画面不同步

**解决方法**：

1. 先检查分析报告：
```bash
cat output/subtitle_analysis_report.json
```

2. 查看时间偏移统计，如果偏移很大（比如>1秒），可能需要：
   - 检查新字幕的时间戳是否正确
   - 使用字幕编辑工具调整新字幕时间
   - 或者只剪辑视频，不使用原字幕

## 实际使用示例

### 示例1：处理单个视频

```bash
# 假设你有这些文件：
# - movie.mp4
# - movie_chinese.srt
# - movie_english.srt

python quick_start_example.py movie.mp4 movie_chinese.srt movie_english.srt
```

### 示例2：批量处理多个视频

创建一个批处理脚本：

```bash
#!/bin/bash
# batch_process.sh

for video in *.mp4; do
    base="${video%.mp4}"
    original_srt="${base}_chinese.srt"
    new_srt="${base}_english.srt"

    if [ -f "$original_srt" ] && [ -f "$new_srt" ]; then
        echo "处理: $video"
        python quick_start_example.py "$video" "$original_srt" "$new_srt"
    fi
done
```

### 示例3：只剪辑视频，不嵌入字幕

```bash
python reclip_video_by_subtitles.py your_video.mp4 new.srt --no-subtitle
```

### 示例4：使用硬字幕（适合社交媒体）

```bash
python reclip_video_by_subtitles.py your_video.mp4 new.srt --hard-subtitle
```

## 进阶技巧

### 1. 只分析不处理

```bash
python analyze_subtitle_timings.py original.srt new.srt
```

查看 `subtitle_analysis_report.json` 了解：
- 每条字幕的时间偏移
- 平均偏移量
- 是否需要调整

### 2. 手动调整字幕后再处理

如果分析发现时间偏移很大：

1. 使用字幕编辑工具（如Subtitle Edit）调整新字幕时间
2. 保存调整后的字幕
3. 重新运行剪辑工具

### 3. 使用Python脚本集成到你的项目

```python
from reclip_video_by_subtitles import VideoReclipper

# 创建剪辑器
clipper = VideoReclipper(
    video_path="video.mp4",
    new_subtitle_path="new.srt",
    output_dir="output"
)

# 执行剪辑
results = clipper.process(
    merge_gap=0.5,
    embed_subtitle=True
)

# 检查结果
if 'video_with_subtitle' in results:
    print(f"成功！输出文件: {results['video_with_subtitle']}")
```

## 检查清单

使用前确认：

- [ ] 已安装 Python 3.12
- [ ] 已安装 ffmpeg
- [ ] 已安装 Python 依赖：`pip install pysrt chardet`
- [ ] 视频文件路径正确
- [ ] 原字幕文件路径正确
- [ ] 新字幕文件路径正确
- [ ] 有足够的磁盘空间（约2倍视频大小）

## 总结

最简单的使用流程：

```bash
# 1. 准备文件
cp your_video.mp4 /Users/ruite_ios/Desktop/aiShortVideo/videorecomp/videodown/
cp your_original.srt /Users/ruite_ios/Desktop/aiShortVideo/videorecomp/videodown/
cp your_new.srt /Users/ruite_ios/Desktop/aiShortVideo/videorecomp/videodown/

# 2. 运行工具
cd /Users/ruite_ios/Desktop/aiShortVideo/videorecomp/videodown
python quick_start_example.py your_video.mp4 your_original.srt your_new.srt

# 3. 查看结果
open output/
```

就这么简单！
