# 视频重新生成工具 - Web应用

基于Vue 3 + Flask的Web应用，提供视频重新生成的在线服务。

## 系统架构

```
┌─────────────────┐         ┌─────────────────┐
│                 │         │                 │
│  Vue 3 前端     │◄────────┤  Flask 后端API  │
│  (Port: 3000)   │  HTTP   │  (Port: 5000)   │
│                 │         │                 │
└─────────────────┘         └────────┬────────┘
                                     │
                                     ▼
                            ┌─────────────────┐
                            │  视频处理模块    │
                            │  (MoviePy)      │
                            └─────────────────┘
```

## 功能特性

### 前端 (Vue 3)
- 拖拽上传文件
- 实时进度显示
- 任务状态管理
- 在线下载生成的视频
- 响应式设计

### 后端 (Flask)
- RESTful API
- 多线程视频处理
- 任务队列管理
- CORS跨域支持
- 文件上传下载

## 快速开始

### 1. 后端设置

```bash
cd backend

# 运行设置脚本
chmod +x setup.sh
./setup.sh

# 激活虚拟环境
source venv/bin/activate

# 启动API服务
python app.py
```

API服务将在 `http://localhost:5000` 启动

### 2. 前端设置

**新开一个终端窗口：**

```bash
cd frontend

# 运行设置脚本
chmod +x setup.sh
./setup.sh

# 启动开发服务器
npm run dev
```

前端应用将在 `http://localhost:3000` 启动

### 3. 使用应用

1. 在浏览器打开 `http://localhost:3000`
2. 上传原视频、字幕文件(SRT)和配音文件(ZIP)
3. 点击"开始处理"
4. 等待处理完成
5. 下载生成的视频（软字幕和硬字幕版本）

## API文档

### 健康检查
```
GET /api/health
```

### 上传文件
```
POST /api/upload
Content-Type: multipart/form-data

Body:
- video: 视频文件
- srt: SRT字幕文件
- audio: ZIP配音文件

Response:
{
  "task_id": "uuid",
  "message": "文件上传成功"
}
```

### 开始处理
```
POST /api/process/{task_id}

Response:
{
  "status": "processing",
  "message": "开始处理视频"
}
```

### 获取任务状态
```
GET /api/status/{task_id}

Response:
{
  "status": "processing",  // uploaded, processing, completed, failed
  "progress": 50,
  "message": "正在处理视频...",
  "error": null
}
```

### 下载视频
```
GET /api/download/{task_id}/{type}
type: soft 或 hard

Response: video/mp4 文件
```

### 取消任务
```
DELETE /api/task/{task_id}
```

## 项目结构

```
videorecomp/
├── frontend/              # Vue前端
│   ├── src/
│   │   ├── components/    # 组件
│   │   ├── services/      # API服务
│   │   ├── views/         # 页面
│   │   ├── App.vue        # 根组件
│   │   └── main.js        # 入口文件
│   ├── package.json
│   ├── vite.config.js
│   └── setup.sh
│
├── backend/               # Flask后端
│   ├── uploads/           # 上传文件
│   ├── downloads/         # 生成文件
│   ├── tasks/             # 任务文件
│   ├── app.py             # API服务
│   ├── requirements.txt
│   └── setup.sh
│
└── src/                   # 核心处理模块
    └── video_processor.py
```

## 环境要求

### 后端
- Python 3.12+
- FFmpeg

### 前端
- Node.js 18+
- npm 9+

## 部署说明

### 生产环境部署

#### 后端部署

```bash
cd backend

# 使用gunicorn部署
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

#### 前端部署

```bash
cd frontend

# 构建生产版本
npm run build

# dist目录包含静态文件
# 可使用nginx或其他Web服务器托管
```

### Docker部署 (可选)

创建 `Dockerfile`:

**后端 Dockerfile:**
```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ .
COPY src/ ../src/

RUN apt-get update && apt-get install -y ffmpeg

EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

**前端 Dockerfile:**
```dockerfile
FROM node:18-alpine as builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
```

## 配置说明

### 后端配置 (app.py)

```python
MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 最大文件大小 500MB
UPLOAD_FOLDER = 'uploads'               # 上传目录
DOWNLOAD_FOLDER = 'downloads'           # 下载目录
```

### 前端配置 (vite.config.js)

```javascript
server: {
  port: 3000,              # 前端端口
  proxy: {
    '/api': {
      target: 'http://localhost:5000',  # 后端API地址
      changeOrigin: true
    }
  }
}
```

## 常见问题

### Q: 文件上传失败
A: 检查文件大小是否超过500MB，检查后端服务是否运行

### Q: 视频处理卡住
A: 查看后端日志，可能是FFmpeg未安装或视频格式问题

### Q: 下载文件为空
A: 确保任务已完成，检查后端downloads目录

### Q: CORS错误
A: 确保后端Flask-CORS已正确配置

## 技术栈

### 前端
- Vue 3 - 渐进式框架
- Vite - 构建工具
- Element Plus - UI组件库
- Axios - HTTP客户端

### 后端
- Flask - Web框架
- Flask-CORS - 跨域支持
- MoviePy - 视频处理
- pysrt - 字幕处理

## 开发

### 前端开发

```bash
cd frontend
npm run dev     # 开发模式
npm run build   # 构建生产版本
```

### 后端开发

```bash
cd backend
source venv/bin/activate
python app.py   # 开发模式（debug=True）
```

## 许可证

MIT License
