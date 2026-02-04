# 🏠 本地模式 - 自动在本地生成视频

## 🎯 方案说明

将Web应用改为**本地处理模式**，点击"开始生成"后，视频在您的本地电脑上生成，无需上传到服务器。

## 🚀 使用步骤

### 1. 启动本地后端服务

```bash
cd /Users/ruite_ios/Desktop/aiShortVideo/videorecomp/videodown/videorecomp/backend

python local_server.py
```

服务会启动在：`http://localhost:5001`

### 2. 启动前端服务

```bash
cd /Users/ruite_ios/Desktop/aiShortVideo/videorecomp/videodown/videorecomp/frontend

npm run dev
```

前端会启动在：`http://localhost:3002`

### 3. 使用Web界面生成视频

1. 打开浏览器访问：`http://localhost:3002`
2. 进入"重新生成视频"页面
3. 上传原视频、新字幕（配音文件可选）
4. 配置字幕样式
5. 点击"开始生成"
6. **视频会在您的本地电脑上自动生成**
7. 完成后下载两个视频（软字幕+硬字幕）

## 📂 生成的视频保存位置

```
/Users/ruite_ios/Desktop/aiShortVideo/videorecomp/videodown/
└── output/
    ├── soft_subtitle_video.mp4
    └── hard_subtitle_video.mp4
```

## 💡 优势

✅ **完全本地处理** - 视频文件不上传到任何服务器
✅ **保护隐私** - 所有文件都在您的电脑上
✅ **速度快** - 无网络传输延迟
✅ **无文件大小限制** - 不受服务器上传限制
✅ **自动保存** - 视频自动保存在本地output目录

## ⚙️ 工作原理

```
浏览器
  ↓ 上传文件
本地后端 (localhost:5001)
  ↓ 接收文件
  ↓ 在本地运行FFmpeg
  ↓ 生成软字幕视频
  ↓ 生成硬字幕视频
  ↓ 保存到本地output目录
  ↓ 返回下载链接
浏览器
  ↓ 下载视频
```

## 🔧 技术实现

### 前端
- 保持现有Web界面不变
- 文件上传到本地后端（localhost:5001）

### 后端
- 接收上传的文件
- 保存到本地临时目录
- 调用本地FFmpeg生成视频
- 保存到本地output目录
- 提供下载链接

### 关键改进
- 所有视频处理都在本地完成
- 文件不离开您的电脑
- FFmpeg直接处理，速度快

## 📝 配置说明

### 输出目录

在 `local_server.py` 中配置：

```python
OUTPUT_DIR = '/Users/ruite_ios/Desktop/aiShortVideo/videorecomp/videodown/output'
```

### 字幕样式

在Web界面中配置：
- 字体大小
- 字体颜色
- 加粗/斜体
- 描边/阴影

## ⚠️ 注意事项

1. **FFmpeg必须安装**
   ```bash
   # 检查FFmpeg
   ffmpeg -version

   # 安装FFmpeg
   brew install ffmpeg  # macOS
   ```

2. **磁盘空间**
   - 生成视频需要足够的磁盘空间
   - 硬字幕视频会占用较大空间
   - 建议至少预留视频大小3倍的空间

3. **处理时间**
   - 软字幕视频：快速（几秒钟）
   - 硬字幕视频：较慢（需要重新编码）

## 🎬 立即使用

### 1. 创建本地服务器脚本

```python
# local_server.py
# 本地视频处理服务器 - 所有处理都在本地完成
```

### 2. 启动服务

```bash
# 启动后端
cd /Users/ruite_ios/Desktop/aiShortVideo/videorecomp/videodown/videorecomp/backend
python local_server.py

# 启动前端（另一个终端）
cd /Users/ruite_ios/Desktop/aiShortVideo/videorecomp/videodown/videorecomp/frontend
npm run dev
```

### 3. 使用Web界面

访问 `http://localhost:3002/video-recomp`，上传文件，点击生成！

---

## 🔜 下一步

我现在为您创建 `local_server.py` 本地服务器脚本。是否继续？
