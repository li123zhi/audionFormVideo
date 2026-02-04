#!/usr/bin/env python3.12
"""
本地视频处理服务器 - 在本地生成视频
所有视频处理都在本地完成，文件不上传到远程服务器
"""

import os
import sys
import uuid
import shutil
import subprocess
import json
import threading
import logging
import re
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

# Pillow and OpenCV for hard subtitle generation
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from video_processor import create_video_recomposer

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 本地配置
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'local_uploads')
OUTPUT_FOLDER = os.path.join(os.path.dirname(__file__), 'output')
TASKS_FOLDER = os.path.join(os.path.dirname(__file__), 'local_tasks')

MAX_CONTENT_LENGTH = 2 * 1024 * 1024 * 1024  # 2GB 最大文件大小

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# 确保目录存在
for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER, TASKS_FOLDER]:
    os.makedirs(folder, exist_ok=True)

logger.info("📂 工作目录:")
logger.info(f"   - 上传目录: {UPLOAD_FOLDER}")
logger.info(f"   - 输出目录: {OUTPUT_FOLDER}")
logger.info(f"   - 任务目录: {TASKS_FOLDER}")
logger.info("   💊 本地模式：所有视频处理都在本地完成")

# 任务存储
tasks = {}
tasks_lock = threading.Lock()


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'service': 'Local Video Processing Server',
        'mode': 'local'
    })


@app.route('/api/upload', methods=['POST'])
def upload_files():
    """
    上传文件接口（本地处理）

    Request:
        - video: 原视频文件
        - srt: 新字幕文件
        - audio: 配音ZIP文件（可选）
        - subtitle_config: 字幕样式配置（JSON字符串）

    Response:
        - task_id: 任务ID
    """
    try:
        logger.info("=" * 60)
        logger.info("收到本地视频处理任务")

        # 检查文件
        if 'video' not in request.files:
            return jsonify({'error': '缺少视频文件'}), 400
        if 'srt' not in request.files:
            return jsonify({'error': '缺少字幕文件'}), 400

        video = request.files['video']
        srt = request.files['srt']
        audio = request.files.get('audio')  # 可选

        # 获取字幕配置
        subtitle_config_json = request.form.get('subtitle_config', '{}')
        try:
            subtitle_config = json.loads(subtitle_config_json)
        except:
            subtitle_config = {}

        if video.filename == '' or srt.filename == '':
            return jsonify({'error': '文件名为空'}), 400

        # 生成任务ID
        task_id = str(uuid.uuid4())

        # 创建任务目录
        task_dir = os.path.join(TASKS_FOLDER, task_id)
        os.makedirs(task_dir, exist_ok=True)

        # 保存文件
        video_path = os.path.join(task_dir, video.filename)
        srt_path = os.path.join(task_dir, srt.filename)
        audio_path = None

        video.save(video_path)
        srt.save(srt_path)

        if audio and audio.filename:
            audio_path = os.path.join(task_dir, audio.filename)
            audio.save(audio_path)
            logger.info(f"配音文件: {audio.filename} ({os.path.getsize(audio_path) / 1024 / 1024:.2f} MB)")

        logger.info(f"任务ID: {task_id}")
        logger.info(f"视频: {video.filename} ({os.path.getsize(video_path) / 1024 / 1024:.2f} MB)")
        logger.info(f"字幕: {srt.filename}")
        logger.info(f"💾 本地模式：文件保存在本地")
        logger.info(f"   - 视频路径: {video_path}")
        logger.info(f"   - 字幕路径: {srt_path}")

        # 初始化任务
        with tasks_lock:
            tasks[task_id] = {
                'type': 'local_subtitle',
                'status': 'processing',
                'progress': 0,
                'message': '正在处理',
                'created_at': datetime.now().isoformat(),
                'video_path': video_path,
                'srt_path': srt_path,
                'audio_path': audio_path,
                'subtitle_config': subtitle_config,
                'soft_subtitle_video': None,
                'hard_subtitle_video': None,
                'error': None
            }

        # 在后台线程中处理
        thread = threading.Thread(
            target=process_local_task,
            args=(task_id, video_path, srt_path, audio_path, subtitle_config)
        )
        thread.daemon = True
        thread.start()

        logger.info("=" * 60)

        return jsonify({
            'task_id': task_id,
            'status': 'processing',
            'message': '任务已创建，正在本地处理'
        })

    except Exception as e:
        logger.error(f"创建任务失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def process_local_task(task_id, video_path, srt_path, audio_path, subtitle_config):
    """处理本地任务（后台线程）"""
    try:
        logger.info(f"🎬 开始处理本地任务 {task_id}")

        video_name = Path(video_path).stem

        # 生成软字幕视频
        logger.info(f"📝 步骤1/2: 生成软字幕视频")
        update_task_status(task_id, 'processing', 25, '正在生成软字幕视频...')

        soft_output = os.path.join(OUTPUT_FOLDER, f"{video_name}_soft.mp4")
        success_soft = create_soft_subtitle_video(video_path, srt_path, soft_output)

        if success_soft:
            with tasks_lock:
                tasks[task_id]['soft_subtitle_video'] = soft_output
                tasks[task_id]['progress'] = 50
                tasks[task_id]['message'] = '软字幕视频生成完成'
        else:
            with tasks_lock:
                tasks[task_id]['status'] = 'failed'
                tasks[task_id]['error'] = '软字幕视频生成失败'
            return

        # 生成硬字幕视频
        logger.info(f"📝 步骤2/2: 生成硬字幕视频")
        update_task_status(task_id, 'burning', 50, '正在生成硬字幕视频...')

        hard_output = os.path.join(OUTPUT_FOLDER, f"{video_name}_hard.mp4")
        success_hard = create_hard_subtitle_video(
            video_path,
            srt_path,
            hard_output,
            subtitle_config
        )

        if success_hard:
            with tasks_lock:
                tasks[task_id]['hard_subtitle_video'] = hard_output
                tasks[task_id]['status'] = 'completed'
                tasks[task_id]['progress'] = 100
                tasks[task_id]['message'] = '处理完成'
                tasks[task_id]['completed_at'] = datetime.now().isoformat()

            logger.info(f"✅ 本地任务 {task_id} 处理成功")
            logger.info(f"   软字幕视频: {soft_output}")
            logger.info(f"   硬字幕视频: {hard_output}")
            logger.info(f"   💾 保存位置: {OUTPUT_FOLDER}")
            logger.info("=" * 60)
        else:
            with tasks_lock:
                tasks[task_id]['status'] = 'failed'
                tasks[task_id]['error'] = '硬字幕视频生成失败'

    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"❌ 本地任务 {task_id} 处理失败: {str(e)}")

        with tasks_lock:
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = str(e)
            tasks[task_id]['message'] = f'处理失败: {str(e)}'
        logger.error("=" * 60)


def create_soft_subtitle_video(video_path: str, srt_path: str, output_path: str) -> bool:
    """创建软字幕视频"""
    try:
        logger.info(f"   正在生成软字幕视频...")
        logger.info(f"   输入: {Path(video_path).name}")
        logger.info(f"   输出: {Path(output_path).name}")

        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-i', srt_path,
            '-c', 'copy',
            '-c:s', 'mov_text',
            '-map', '0:v:0',
            '-map', '0:a:0?',
            '-map', '1:s:0',
            '-metadata:s:s:0', 'language=chi',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if result.returncode == 0 and os.path.exists(output_path):
            # 获取视频时长
            duration = get_video_duration(output_path)
            logger.info(f"   ✅ 软字幕视频生成成功！时长: {duration:.2f}秒")
            return True
        else:
            logger.error(f"   ❌ 生成失败")
            if result.stderr:
                logger.error(f"   错误: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"   ⏱️  生成超时")
        return False
    except Exception as e:
        logger.error(f"   ❌ 出错: {e}")
        return False


def parse_srt(srt_path: str) -> list:
    """解析SRT字幕文件，返回字幕条目列表"""
    subtitles = []

    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # SRT格式：序号 -> 时间轴 -> 文本 -> 空行
    pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\n|\n*$)'
    matches = re.findall(pattern, content, re.DOTALL)

    for match in matches:
        index = int(match[0])
        start_time = match[1]
        end_time = match[2]
        text = match[3].replace('\n', ' ')  # 多行字幕合并为一行

        # 转换时间戳为秒
        def time_to_seconds(time_str):
            h, m, s_ms = time_str.split(':')
            s, ms = s_ms.split(',')
            return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

        start_seconds = time_to_seconds(start_time)
        end_seconds = time_to_seconds(end_time)

        subtitles.append({
            'index': index,
            'start': start_seconds,
            'end': end_seconds,
            'text': text.strip()
        })

    return subtitles


def wrap_text(text, font, draw, max_width):
    """将文本自动换行以适应指定宽度"""
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        width = bbox[2] - bbox[0]

        if width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]

    if current_line:
        lines.append(' '.join(current_line))

    return lines


def create_hard_subtitle_video(video_path: str, srt_path: str, output_path: str, subtitle_config: dict = None) -> bool:
    """创建硬字幕视频（使用Pillow/OpenCV将字幕烧录到画面上）"""
    try:
        logger.info(f"   正在生成硬字幕视频（使用Pillow）...")
        logger.info(f"   输入: {Path(video_path).name}")
        logger.info(f"   输出: {Path(output_path).name}")

        # 默认配置
        config = {
            'fontSize': 24,
            'fontColor': '#FFFFFF',
            'bold': False,
            'italic': False,
            'outline': True,
            'shadow': True,
            'bottomMargin': 50,  # 距离底部的高度（像素）
            'maxWidthRatio': 0.9  # 字幕最大宽度占视频宽度的比例
        }
        if subtitle_config:
            config.update(subtitle_config)

        logger.info(f"   字幕样式: 大小={config['fontSize']}, 颜色={config['fontColor']}, "
                   f"加粗={config['bold']}, 描边={config['outline']}, 阴影={config['shadow']}, "
                   f"底部边距={config['bottomMargin']}px")

        # 解析SRT字幕
        logger.info(f"   正在解析字幕文件...")
        subtitles = parse_srt(srt_path)
        logger.info(f"   解析到 {len(subtitles)} 条字幕")

        # 打开视频
        logger.info(f"   正在打开视频文件...")
        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            logger.error(f"   ❌ 无法打开视频文件")
            return False

        # 获取视频属性
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        logger.info(f"   视频属性: {width}x{height}, {fps:.2f}fps, {total_frames}帧")

        # 设置输出视频编码器
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        # 准备字体和颜色
        font_size = config['fontSize']
        font_color = config['fontColor'].lstrip('#')

        # 转换十六进制颜色为RGB
        if len(font_color) == 6:
            font_color_rgb = tuple(int(font_color[i:i+2], 16) for i in (0, 2, 4))
        else:
            font_color_rgb = (255, 255, 255)  # 默认白色

        # 尝试加载中文字体，如果失败则使用默认字体
        try:
            # macOS 中文字体路径
            font_paths = [
                '/System/Library/Fonts/PingFang.ttc',
                '/System/Library/Fonts/STHeiti Light.ttc',
                '/System/Library/Fonts/Helvetica.ttc',
            ]
            font = None
            for font_path in font_paths:
                if os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, font_size)
                    break

            if font is None:
                # 使用默认字体
                font = ImageFont.load_default()
                logger.warning(f"   ⚠️  未找到中文字体，使用默认字体（可能无法显示中文）")
        except Exception as e:
            logger.warning(f"   ⚠️  加载字体失败: {e}，使用默认字体")
            font = ImageFont.load_default()

        # 处理每一帧
        frame_count = 0
        last_progress = 0

        logger.info(f"   开始处理视频帧...")

        while True:
            ret, frame = cap.read()

            if not ret:
                break

            # 当前帧的时间戳（秒）
            current_time = frame_count / fps

            # 查找当前时间应该显示的字幕
            current_subtitle = None
            for sub in subtitles:
                if sub['start'] <= current_time <= sub['end']:
                    current_subtitle = sub['text']
                    break

            # 如果有字幕，绘制到帧上
            if current_subtitle:
                # 将OpenCV图像转换为PIL图像
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(frame_rgb)
                draw = ImageDraw.Draw(pil_image)

                # 自动换行处理
                max_text_width = int(width * config['maxWidthRatio'])
                lines = wrap_text(current_subtitle, font, draw, max_text_width)

                # 计算多行文本的总高度和位置
                line_heights = []
                for line in lines:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    line_heights.append(bbox[3] - bbox[1])

                total_height = sum(line_heights) + (len(lines) - 1) * 5  # 5像素行间距
                y = height - total_height - config['bottomMargin']

                # 绘制每一行字幕
                for i, line in enumerate(lines):
                    bbox = draw.textbbox((0, 0), line, font=font)
                    text_width = bbox[2] - bbox[0]
                    x = (width - text_width) // 2

                    # 绘制阴影
                    if config['shadow']:
                        shadow_offset = 2
                        draw.text((x + shadow_offset, y + shadow_offset), line,
                                 font=font, fill=(0, 0, 0, 128))

                    # 绘制描边
                    if config['outline']:
                        outline_color = (0, 0, 0)
                        for adj_x in range(-2, 3):
                            for adj_y in range(-2, 3):
                                if adj_x != 0 or adj_y != 0:
                                    draw.text((x + adj_x, y + adj_y), line,
                                            font=font, fill=outline_color)

                    # 绘制主文本
                    draw.text((x, y), line, font=font, fill=font_color_rgb)

                    # 移动到下一行
                    y += line_heights[i] + 5

                # 转换回OpenCV格式
                frame = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

            # 写入输出视频
            out.write(frame)

            frame_count += 1

            # 显示进度
            progress = int((frame_count / total_frames) * 100)
            if progress - last_progress >= 10:  # 每10%显示一次
                logger.info(f"   处理进度: {progress}% ({frame_count}/{total_frames}帧)")
                last_progress = progress

        # 释放资源
        cap.release()
        out.release()

        logger.info(f"   ✅ 视频处理完成，共处理 {frame_count} 帧")

        # 验证输出文件
        if os.path.exists(output_path):
            duration = get_video_duration(output_path)
            logger.info(f"   ✅ 硬字幕视频生成成功！时长: {duration:.2f}秒")
            return True
        else:
            logger.error(f"   ❌ 输出文件不存在")
            return False

    except Exception as e:
        import traceback
        logger.error(f"   ❌ 出错: {e}")
        logger.error(f"   详细错误:\n{traceback.format_exc()}")
        return False


def get_video_duration(video_path: str) -> float:
    """获取视频时长"""
    cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', video_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        return float(info['format']['duration'])
    except:
        return 0.0


def update_task_status(task_id, status, progress, message):
    """更新任务状态"""
    with tasks_lock:
        if task_id in tasks:
            tasks[task_id]['status'] = status
            tasks[task_id]['progress'] = progress
            tasks[task_id]['message'] = message
            if status == 'burning':
                tasks[task_id]['step'] = 'burning'
            elif status == 'processing':
                tasks[task_id]['step'] = 'processing'


@app.route('/api/status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """获取任务状态"""
    with tasks_lock:
        task = tasks.get(task_id)
        if not task:
            return jsonify({'error': '任务不存在'}), 404
        return jsonify(task)


@app.route('/api/download/<task_id>/<type>', methods=['GET'])
def download_video(task_id, type):
    """
    下载生成的视频

    Args:
        task_id: 任务ID
        type: 类型 (soft, hard, audio)
    """
    with tasks_lock:
        task = tasks.get(task_id)
        if not task:
            return jsonify({'error': '任务不存在'}), 404

        if task['status'] != 'completed':
            return jsonify({'error': '任务未完成'}), 400

    try:
        if type == 'soft':
            file_path = task.get('soft_subtitle_video')
        elif type == 'hard':
            file_path = task.get('hard_subtitle_video')
        else:
            return jsonify({'error': '无效的类型'}), 400

        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': '文件不存在'}), 404

        filename = os.path.basename(file_path)
        return send_file(file_path, as_attachment=True, download_name=filename)

    except Exception as e:
        logger.error(f"下载失败: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks', methods=['GET'])
def list_tasks():
    """列出所有任务"""
    with tasks_lock:
        return jsonify(list(tasks.values()))


@app.route('/api/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    """删除任务"""
    with tasks_lock:
        task = tasks.get(task_id)
        if not task:
            return jsonify({'error': '任务不存在'}), 404

        # 删除任务目录
        task_dir = os.path.join(TASKS_FOLDER, task_id)
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir)
            logger.info(f"已删除任务目录: {task_dir}")

        # 删除任务记录
        del tasks[task_id]

        return jsonify({'message': '任务已删除'})


if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("🚀 本地视频处理服务器启动")
    logger.info("=" * 60)
    logger.info(f"🌐 API地址: http://localhost:5001")
    logger.info(f"📂 工作目录: {os.path.dirname(__file__)}")
    logger.info(f"💾 本地模式：所有视频处理都在本地完成")
    logger.info("   - 文件不上传到远程服务器")
    logger.info("   - 保护您的隐私")
    logger.info("=" * 60)
    logger.info("服务已启动，等待请求...")
    logger.info("")

    app.run(
        host='0.0.0.0',
        port=5001,
        debug=True,
        threaded=True
    )
