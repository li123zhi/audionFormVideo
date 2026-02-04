# 🎬 本地生成软硬字幕视频工具

## 📝 功能说明

这个命令行工具可以直接在本地生成带字幕的视频，无需通过Web界面。

### 两种字幕视频

1. **软字幕视频** - 字幕嵌入到视频容器中
   - ✅ 播放时可随时开关字幕
   - ✅ 字幕清晰，不受视频编码影响
   - ✅ 文件较小
   - ✅ 兼容性好（大部分播放器支持）

2. **硬字幕视频** - 字幕烧录到画面上
   - ✅ 字幕永远显示，无法关闭
   - ✅ 适用于不支持软字幕的平台
   - ⚠️ 需要重新编码，会降低视频质量
   - ⚠️ 文件较大，生成时间较长

---

## 🚀 使用方法

### 基本用法

```bash
cd /Users/ruite_ios/Desktop/aiShortVideo/videorecomp/videodown

python generate_subtitle_videos.py \
    your_video.mp4 \
    your_subtitle.srt
```

### 指定输出目录

```bash
python generate_subtitle_videos.py \
    your_video.mp4 \
    your_subtitle.srt \
    ./output
```

---

## 📂 输出文件

在输出目录中会生成两个文件：

```
output/
├── your_video_soft_subtitle.mp4   # 软字幕视频
└── your_video_hard_subtitle.mp4   # 硬字幕视频
```

---

## ⚙️ 字幕样式配置

编辑 `generate_subtitle_videos.py` 中的 `subtitle_config` 字典：

```python
subtitle_config = {
    'fontSize': 24,           # 字体大小 (12-48)
    'fontColor': '#FFFFFF',    # 字体颜色 (十六进制)
    'bold': False,             # 是否加粗
    'italic': False,           # 是否斜体
    'outline': True,           # 是否描边
    'shadow': True             # 是否阴影
}
```

### 常用颜色

- `#FFFFFF` - 白色（默认）
- `#FFFF00` - 黄色
- `#000000` - 黑色
- `#FF0000` - 红色

---

## 💡 使用建议

### 何时使用软字幕视频？

✅ 推荐在以下情况使用软字幕视频：
- 在电脑、手机、平板上播放
- 需要保留字幕开关功能
- 需要高质量视频
- 文件大小敏感

### 何时使用硬字幕视频？

✅ 推荐在以下情况使用硬字幕视频：
- 上传到不支持字幕的平台（如抖音、快手）
- 确保字幕始终显示
- 分享给不懂开关字幕的人

---

## 🔧 技术说明

### 软字幕实现原理

使用 FFmpeg 将字幕文件嵌入到视频容器中：
```bash
ffmpeg -i video.mp4 -i subtitle.srt \
  -c copy -c:s mov_text \
  -map 0:v:0 -map 0:a:0 -map 1:s:0 \
  output_soft.mp4
```

### 硬字幕实现原理

使用 FFmpeg 的 subtitles 滤镜将字幕烧录到画面：
```bash
ffmpeg -i video.mp4 \
  -vf "subtitles=subtitle.srt" \
  -c:v libx264 -preset medium -crf 23 \
  -c:a copy output_hard.mp4
```

---

## ⚠️ 注意事项

1. **FFmpeg 必须安装**
   ```bash
   # macOS
   brew install ffmpeg

   # Ubuntu/Debian
   sudo apt install ffmpeg

   # Windows
   # 从 https://ffmpeg.org/download.html 下载
   ```

2. **处理时间**
   - 软字幕：快速（几乎即时完成）
   - 硬字幕：较慢（需要重新编码，可能需要原视频时长的30%-50%）

3. **视频质量**
   - 软字幕：保持原视频质量
   - 硬字幕：轻微质量损失（可通过调整 `-crf` 参数控制）

4. **文件大小**
   - 软字幕：字幕文件很小，几乎不影响文件大小
   - 硬字幕：文件大小可能与原视频相当

---

## 📊 示例输出

```
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║        本地视频字幕工具 - 生成软硬字幕视频                ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

📂 输出目录: output
🎬 视频名称: sample_video

🎬 正在生成软字幕视频...
   输入视频: sample_video.mp4
   字幕文件: subtitle.srt
   输出视频: output/sample_video_soft_subtitle.mp4
   ✅ 软字幕视频生成成功！时长: 120.50秒

🎬 正在生成硬字幕视频...
   输入视频: sample_video.mp4
   字幕文件: subtitle.srt
   输出视频: output/sample_video_hard_subtitle.mp4
   字幕样式: FontSize=24,FontColor=FFFFFF,BorderStyle=1...
   ✅ 硬字幕视频生成成功！时长: 120.50秒

============================================================
处理完成！
============================================================

📁 输出文件:
   ✅ 软字幕视频: output/sample_video_soft_subtitle.mp4
   ✅ 硬字幕视频: output/sample_video_hard_subtitle.mp4

💡 使用建议:
   - 软字幕视频：推荐使用，兼容性好，可开关字幕
   - 硬字幕视频：用于不支持软字幕的平台
   - 两个视频可以同时保留，根据需要选择使用
```

---

## 🎯 快速开始

### 1. 准备文件

确保你有：
- 原视频文件（mp4, avi, mov等）
- SRT字幕文件

### 2. 运行脚本

```bash
python generate_subtitle_videos.py \
    my_video.mp4 \
    my_subtitle.srt
```

### 3. 查看结果

```bash
# 查看生成的文件
ls -lh output/

# 播放软字幕视频
open output/my_video_soft_subtitle.mp4

# 播放硬字幕视频
open output/my_video_hard_subtitle.mp4
```

---

## 🛠️ 高级配置

### 调整硬字幕质量

修改脚本中的 `-crf` 参数（默认23）：
- 更低质量（文件更小）：`-crf 28`
- 更高质量（文件更大）：`-crf 18`

### 调整硬字幕编码速度

修改脚本中的 `-preset` 参数（默认medium）：
- 更快编码：`-preset fast`
- 更慢编码但更好压缩：`-preset slow`

---

## ❓ 常见问题

### Q1: 生成失败怎么办？

A: 检查：
1. FFmpeg是否正确安装：`ffmpeg -version`
2. 文件路径是否正确
3. SRT文件格式是否正确

### Q2: 硬字幕生成很慢？

A: 正常现象，硬字幕需要重新编码整个视频。可以：
1. 使用更快的preset：`-preset fast`
2. 降低质量以换取速度：`-crf 28`

### Q3: 字幕显示不全？

A: 可能是字体问题。可以：
1. 调整字体大小
2. 确保SRT文件编码为UTF-8

### Q4: 软字幕在某些播放器不显示？

A: 尝试：
1. 使用VLC Media Player播放
2. 使用IINA播放器（macOS）
3. 使用PotPlayer（Windows）

---

## 📞 获取帮助

如有问题，请检查：
1. FFmpeg版本：`ffmpeg -version`
2. 文件权限：`ls -la`
3. 错误日志：查看脚本输出的错误信息
