# 视频重新生成工具

一个用于将原视频、翻译字幕和新的配音文件合并生成新视频的工具。

## 功能特点

- 支持原视频与新的配音音频合并
- 支持SRT格式字幕（自动检测编码）
- 从ZIP文件中提取多个音频片段并按顺序拼接
- 生成硬字幕和软字幕两个版本
- 自动处理音频和视频同步

## 环境要求

- Python 3.12+
- FFmpeg（MoviePy会自动安装，但系统需要FFmpeg支持）

### 安装Python 3.12+

**macOS:**
```bash
brew install python@3.12
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.12 python3.12-venv
```

**Windows:**
从 [python.org](https://www.python.org/downloads/) 下载并安装Python 3.12+

## 快速开始

### 1. 环境设置

> **注意**: 如果之前已创建虚拟环境，请删除后重新创建：
> ```bash
> rm -rf venv
> ./setup.sh
> ```

```bash
# 运行设置脚本
chmod +x setup.sh
./setup.sh
```

或手动设置：

```bash
# 使用Python 3.12+创建虚拟环境
python3.12 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 准备输入文件

在 `input/` 目录下放置：

- `video.mp4` - 原视频文件
- `subtitles.srt` - 翻译后的SRT字幕文件
- `audio.zip` - 配音ZIP文件（包含多个mp3/mp4音频片段）

### 3. 运行程序

```bash
# 激活虚拟环境（如果尚未激活）
source venv/bin/activate

# 基本用法
python main.py -v input/video.mp4 -s input/subtitles.srt -a input/audio.zip

# 指定输出目录
python main.py -v input/video.mp4 -s input/subtitles.srt -a input/audio.zip -o my_output

# 查看帮助
python main.py -h
```

## 命令行参数

| 参数 | 说明 | 必需 |
|------|------|------|
| `-v, --video` | 原视频文件路径 | 是 |
| `-s, --srt` | SRT字幕文件路径 | 是 |
| `-a, --audio` | 配音ZIP文件路径 | 是 |
| `-o, --output` | 输出目录（默认: output） | 否 |
| `--keep-temp` | 保留临时文件（用于调试） | 否 |

## 输出说明

程序会在输出目录生成两个文件：

1. **output_soft_subtitle.mp4** - 软字幕版本
   - 字幕作为视觉层叠加在视频上
   - 可在大多数播放器中显示

2. **output_hard_subtitle.mp4** - 硬字幕版本
   - 字幕烧录到视频中
   - 适用于不支持软字幕的平台

## 项目结构

```
videorecomp/
├── src/
│   ├── __init__.py
│   └── video_processor.py    # 核心处理模块
├── input/                    # 输入文件目录
├── output/                   # 输出文件目录
├── tests/                    # 测试文件
├── main.py                   # 主程序入口
├── requirements.txt          # 依赖列表
├── setup.sh                  # 环境设置脚本
└── README.md                 # 本文件
```

## 配置说明

### 字幕文件格式

- 支持SRT格式
- 自动检测文件编码（UTF-8, GBK等）
- 字幕时间轴用于同步显示

### 配音文件格式

- 必须是ZIP格式
- 包含的音频文件按**文件名字母顺序**拼接
- 支持格式: mp3, mp4, m4a, aac, wav

示例ZIP内容结构：
```
audio.zip
├── segment_01.mp3
├── segment_02.mp3
└── segment_03.mp3
```

## 常见问题

### Q: 提示FFmpeg相关错误
A: 确保系统已安装FFmpeg:
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg
```

### Q: 音视频不同步
A: 检查字幕时间轴是否与原视频匹配，以及音频片段顺序是否正确

### Q: 字幕显示乱码
A: 程序会自动检测编码，如果仍有问题，请确保SRT文件使用UTF-8编码

## 技术栈

- **MoviePy** - 视频处理
- **pysrt** - SRT字幕解析
- **chardet** - 编码检测
- **tqdm** - 进度条显示

## 开发

### 运行测试

```bash
python -m pytest tests/
```

### 代码结构

- `SubtitleProcessor` - 字幕处理类
- `AudioMerger` - 音频合并类
- `VideoRecomposer` - 视频重新生成主类

## 许可证

MIT License
