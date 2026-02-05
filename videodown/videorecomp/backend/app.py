#!/usr/bin/env python3.12
"""
视频重新生成工具 - Flask API服务
"""

import os
import uuid
import shutil
import threading
import logging
import tempfile
import subprocess
import json
import re
from pathlib import Path
from datetime import datetime

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import sys

# Pillow and OpenCV for hard subtitle generation
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from video_processor import create_video_recomposer
from subtitle_analyzer import SubtitleAnalyzer
from enhanced_video_processor import EnhancedVideoClipper, BatchVideoProcessor
from compact_video_processor import CompactVideoClipper
from timeline_aligner import TimelineAligner
from timeline_remap_clipper import TimelineRemapClipper

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 配置
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
DOWNLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'downloads')
TASKS_FOLDER = os.path.join(os.path.dirname(__file__), 'tasks')
OUTPUT_FOLDER = os.path.join(os.path.dirname(__file__), '../../output/audio_segments')  # 本地输出目录

MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB 最大文件大小

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DOWNLOAD_FOLDER'] = DOWNLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# 确保目录存在
for folder in [UPLOAD_FOLDER, DOWNLOAD_FOLDER, TASKS_FOLDER, OUTPUT_FOLDER]:
    os.makedirs(folder, exist_ok=True)

logger.info("📂 工作目录:")
logger.info(f"   - 上传目录: {UPLOAD_FOLDER}")
logger.info(f"   - 下载目录: {DOWNLOAD_FOLDER}")
logger.info(f"   - 任务目录: {TASKS_FOLDER}")
logger.info(f"   - 输出目录: {OUTPUT_FOLDER}")

# 任务存储 (生产环境应使用Redis或数据库)
tasks = {}
tasks_lock = threading.Lock()


# ==================== 辅助函数 ====================

def get_video_duration(video_path: str) -> float:
    """获取视频时长"""
    cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', video_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        return float(info['format']['duration'])
    except:
        return 0.0


def create_soft_subtitle_video(video_path: str, srt_path: str, output_path: str) -> bool:
    """创建软字幕视频（字幕嵌入到视频容器中）"""
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


# ==================== 软硬字幕生成API ====================

subtitle_tasks = {}
subtitle_tasks_lock = threading.Lock()


@app.route('/api/subtitle-generate', methods=['POST'])
def subtitle_generate_upload():
    """
    软硬字幕视频生成 - 上传文件（完整版本，使用video_processor）

    Request:
        - video: 原视频文件
        - srt: 新字幕文件
        - original_srt: 原字幕文件（可选）
        - audio: 配音ZIP文件（可选）
        - subtitle_config: 字幕样式配置（JSON字符串，可选）
        - enable_ai_separation: 是否启用AI音频分离（可选，默认false）
        - generate_no_subtitle: 是否生成不带字幕的视频（可选，默认true）

    Response:
        - task_id: 任务ID
    """
    try:
        logger.info("=" * 60)
        logger.info("收到软硬字幕视频生成任务（完整版）")

        # 检查是否为纯音频合成模式（不需要视频）
        audio_only = request.form.get('audio_only', 'false').lower() == 'true'

        # 检查必需文件
        if 'srt' not in request.files:
            return jsonify({'error': '缺少字幕文件'}), 400

        srt = request.files['srt']

        # 视频文件：仅在非纯音频模式下必需
        video = request.files.get('video')
        if not audio_only and not video:
            return jsonify({'error': '缺少视频文件'}), 400

        # 获取可选文件
        original_srt = request.files.get('original_srt')
        audio_zip = request.files.get('audio')

        # 纯音频合成模式下，音频文件是必需的
        if audio_only and not audio_zip:
            return jsonify({'error': '缺少配音音频文件'}), 400

        # 获取字幕配置
        subtitle_config_json = request.form.get('subtitle_config', '{}')
        try:
            subtitle_config = json.loads(subtitle_config_json)
        except:
            subtitle_config = {}

        # 获取处理选项
        enable_ai_separation = request.form.get('enable_ai_separation', 'false').lower() == 'true'
        generate_no_subtitle = request.form.get('generate_no_subtitle', 'true').lower() == 'true'

        # 检查文件名
        if srt.filename == '':
            return jsonify({'error': '字幕文件名为空'}), 400
        if video and video.filename == '':
            return jsonify({'error': '视频文件名为空'}), 400

        # 生成任务ID
        task_id = str(uuid.uuid4())

        # 创建任务目录
        task_dir = os.path.join(TASKS_FOLDER, f'subtitle_{task_id}')
        os.makedirs(task_dir, exist_ok=True)

        # 保存字幕文件
        srt_path = os.path.join(task_dir, srt.filename)
        srt.save(srt_path)
        logger.info(f"字幕文件: {srt.filename}")

        # 保存视频（如果有）
        video_path = None
        if video and video.filename:
            video_path = os.path.join(task_dir, video.filename)
            video.save(video_path)
            logger.info(f"视频文件: {video.filename}")
        else:
            logger.info("无视频文件（纯音频合成模式）")

        # 保存原字幕（如果提供）
        original_srt_path = None
        if original_srt and original_srt.filename:
            original_srt_path = os.path.join(task_dir, original_srt.filename)
            original_srt.save(original_srt_path)
            logger.info(f"原字幕: {original_srt.filename}")

        # 保存配音ZIP（如果提供）
        audio_zip_path = None
        if audio_zip and audio_zip.filename:
            audio_zip_path = os.path.join(task_dir, audio_zip.filename)
            audio_zip.save(audio_zip_path)
            logger.info(f"配音: {audio_zip.filename}")

        # 创建输出目录
        output_dir = os.path.join(OUTPUT_FOLDER, f'subtitle_{task_id}')
        os.makedirs(output_dir, exist_ok=True)

        logger.info(f"任务ID: {task_id}")
        if video and video.filename:
            logger.info(f"视频: {video.filename} ({os.path.getsize(video_path) / 1024 / 1024:.2f} MB)")
        logger.info(f"字幕: {srt.filename}")
        logger.info(f"AI分离: {enable_ai_separation}")
        logger.info(f"生成无字幕视频: {generate_no_subtitle}")
        logger.info(f"💾 本地模式：文件保存在本地")
        if video_path:
            logger.info(f"   - 视频路径: {video_path}")
        logger.info(f"   - 字幕路径: {srt_path}")
        if audio_zip_path:
            logger.info(f"   - 配音路径: {audio_zip_path}")
        logger.info(f"   - 纯音频模式: {audio_only}")

        # 初始化步骤列表
        if audio_only:
            # 纯音频合成模式：只需要字幕和配音
            steps = [
                {'id': 1, 'name': '解析字幕', 'status': 'pending', 'message': '等待开始...'},
                {'id': 2, 'name': '合成配音音轨', 'status': 'pending', 'message': '等待开始...'},
                {'id': 3, 'name': '完成', 'status': 'pending', 'message': '等待开始...'}
            ]
        else:
            # 完整视频生成模式
            steps = [
                {'id': 1, 'name': '提取音轨', 'status': 'pending', 'message': '等待开始...'},
                {'id': 2, 'name': 'AI音频分离', 'status': 'pending', 'message': '等待开始...'},
                {'id': 3, 'name': '合并配音', 'status': 'pending', 'message': '等待开始...'},
                {'id': 4, 'name': '生成视频', 'status': 'pending', 'message': '等待开始...'},
                {'id': 5, 'name': '完成', 'status': 'pending', 'message': '等待开始...'}
            ]

            # 根据选项调整步骤
            if not enable_ai_separation and not audio_zip_path:
                # 没有AI分离，没有配音，只生成视频
                steps = [
                    {'id': 1, 'name': '生成不带字幕视频', 'status': 'pending', 'message': '等待开始...'},
                    {'id': 2, 'name': '生成软字幕视频', 'status': 'pending', 'message': '等待开始...'},
                    {'id': 3, 'name': '生成硬字幕视频', 'status': 'pending', 'message': '等待开始...'}
                ]
            elif not enable_ai_separation:
                # 没有AI分离，但有配音
                steps = [
                    {'id': 1, 'name': '合并配音', 'status': 'pending', 'message': '等待开始...'},
                    {'id': 2, 'name': '生成视频', 'status': 'pending', 'message': '等待开始...'}
                ]

        # 初始化任务
        with subtitle_tasks_lock:
            subtitle_tasks[task_id] = {
                'type': 'subtitle_generate',
                'status': 'processing',
                'progress': 0,
                'message': '正在处理',
                'created_at': datetime.now().isoformat(),
                'video_path': video_path,
                'srt_path': srt_path,
                'original_srt_path': original_srt_path,
                'audio_zip_path': audio_zip_path,
                'subtitle_config': subtitle_config,
                'enable_ai_separation': enable_ai_separation,
                'generate_no_subtitle': generate_no_subtitle,
                'audio_only': audio_only,
                'output_dir': output_dir,
                'steps': steps,
                'current_step': 0,
                'files': {},
                'error': None
            }

        # 在后台线程中处理
        logger.info(f"   正在创建后台线程...")
        thread = threading.Thread(
            target=process_subtitle_generate_task_v2,
            args=(task_id, video_path, srt_path, output_dir, subtitle_config,
                  original_srt_path, audio_zip_path, enable_ai_separation, generate_no_subtitle, audio_only)
        )
        thread.daemon = True
        logger.info(f"   线程对象已创建，准备启动...")
        thread.start()
        logger.info(f"   ✅ 后台线程已启动，task_id={task_id}")

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


def process_subtitle_generate_task(task_id, video_path, srt_path, output_dir, subtitle_config):
    """处理软硬字幕生成任务（后台线程）"""
    try:
        logger.info(f"🎬 开始处理字幕生成任务 {task_id}")

        video_name = Path(video_path).stem

        # 生成软字幕视频
        logger.info(f"📝 步骤1/2: 生成软字幕视频")
        update_subtitle_task_status(task_id, 'processing', 25, '正在生成软字幕视频...')

        soft_output = os.path.join(output_dir, f"{video_name}_soft.mp4")
        success_soft = create_soft_subtitle_video(video_path, srt_path, soft_output)

        if success_soft:
            with subtitle_tasks_lock:
                subtitle_tasks[task_id]['soft_subtitle_video'] = soft_output
                subtitle_tasks[task_id]['progress'] = 50
                subtitle_tasks[task_id]['message'] = '软字幕视频生成完成'
        else:
            with subtitle_tasks_lock:
                subtitle_tasks[task_id]['status'] = 'failed'
                subtitle_tasks[task_id]['error'] = '软字幕视频生成失败'
            return

        # 生成硬字幕视频
        logger.info(f"📝 步骤2/2: 生成硬字幕视频")
        update_subtitle_task_status(task_id, 'burning', 50, '正在生成硬字幕视频...')

        hard_output = os.path.join(output_dir, f"{video_name}_hard.mp4")
        success_hard = create_hard_subtitle_video(
            video_path,
            srt_path,
            hard_output,
            subtitle_config
        )

        if success_hard:
            with subtitle_tasks_lock:
                subtitle_tasks[task_id]['hard_subtitle_video'] = hard_output
                subtitle_tasks[task_id]['status'] = 'completed'
                subtitle_tasks[task_id]['progress'] = 100
                subtitle_tasks[task_id]['message'] = '处理完成'
                subtitle_tasks[task_id]['completed_at'] = datetime.now().isoformat()

            logger.info(f"✅ 字幕生成任务 {task_id} 处理成功")
            logger.info(f"   软字幕视频: {soft_output}")
            logger.info(f"   硬字幕视频: {hard_output}")
            logger.info(f"   💾 保存位置: {output_dir}")
            logger.info("=" * 60)
        else:
            with subtitle_tasks_lock:
                subtitle_tasks[task_id]['status'] = 'failed'
                subtitle_tasks[task_id]['error'] = '硬字幕视频生成失败'

    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"❌ 字幕生成任务 {task_id} 处理失败: {str(e)}")

        with subtitle_tasks_lock:
            subtitle_tasks[task_id]['status'] = 'failed'
            subtitle_tasks[task_id]['error'] = str(e)
            subtitle_tasks[task_id]['message'] = f'处理失败: {str(e)}'
        logger.error("=" * 60)


def process_subtitle_generate_task_v2(task_id, video_path, srt_path, output_dir,
                                     subtitle_config, original_srt_path, audio_zip_path,
                                     enable_ai_separation, generate_no_subtitle, audio_only):
    """处理字幕生成任务（后台线程）- 使用video_processor的完整版本"""
    logger.info(f"🚀 [线程启动] 开始处理完整字幕生成任务 {task_id}")

    # 首先更新状态，表示线程已启动
    try:
        with subtitle_tasks_lock:
            if task_id in subtitle_tasks:
                subtitle_tasks[task_id]['message'] = '线程已启动，正在初始化...'
    except:
        pass

    try:
        logger.info(f"🎬 [任务开始] task_id={task_id}")
        logger.info(f"   video_path={video_path}")
        logger.info(f"   srt_path={srt_path}")
        logger.info(f"   output_dir={output_dir}")
        logger.info(f"   original_srt_path={original_srt_path}")
        logger.info(f"   audio_zip_path={audio_zip_path}")
        logger.info(f"   enable_ai_separation={enable_ai_separation}")
        logger.info(f"   generate_no_subtitle={generate_no_subtitle}")

        # 转换字幕样式配置
        video_processor_style = {}
        if subtitle_config:
            logger.info(f"   字幕配置: {subtitle_config}")
            video_processor_style = {
                'font_size': subtitle_config.get('fontSize', 32),
                'primary_colour': subtitle_config.get('fontColor', '&HFFFFFF'),
                'outline_colour': subtitle_config.get('outlineColor', '&H000000'),
                'outline': subtitle_config.get('outline', 1) if subtitle_config.get('outline') else 0,
                'margin_v': subtitle_config.get('bottomMargin', 100),
                'max_width_ratio': subtitle_config.get('maxWidthRatio', 90),
                'alignment': 'center'
            }

        # 准备音频ZIP路径
        audio_zip_for_processor = audio_zip_path if audio_zip_path else None
        logger.info(f"   audio_zip_for_processor={audio_zip_for_processor}")

        # 如果没有配音文件，使用简化处理
        if not audio_zip_path:
            logger.info(f"   没有配音文件，使用简化处理流程")
            result = _process_video_only(None, task_id, video_path, srt_path,
                                        output_dir, subtitle_config, original_srt_path,
                                        enable_ai_separation, generate_no_subtitle)
        elif audio_only and not video_path:
            # 纯音频合成模式：没有视频文件，只有字幕和配音
            logger.info(f"   纯音频合成模式，不需要视频文件")
            result = _process_audio_only_simple(
                task_id, srt_path, output_dir, audio_zip_path
            )
        else:
            logger.info(f"   有配音文件，使用完整处理流程")
            # 尝试使用 video_processor
            try:
                recomposer = create_video_recomposer(
                    original_video=video_path,
                    srt_file=srt_path,
                    audio_zip=audio_zip_for_processor,
                    output_dir=output_dir,
                    subtitle_style=video_processor_style,
                    enable_ai_separation=enable_ai_separation,
                    original_srt_file=original_srt_path
                )
                result = recomposer.process()
            except Exception as e:
                logger.error(f"   video_processor处理失败: {e}")
                logger.error(f"   回退到简化处理流程")
                import traceback
                traceback.print_exc()
                # 回退到简化处理
                result = _process_video_only(None, task_id, video_path, srt_path,
                                            output_dir, subtitle_config, original_srt_path,
                                            enable_ai_separation, generate_no_subtitle)

        logger.info(f"   处理结果: {list(result.keys())}")

        # 更新任务状态
        with subtitle_tasks_lock:
            task = subtitle_tasks[task_id]
            task['status'] = 'completed'
            task['progress'] = 100
            task['message'] = '处理完成'
            task['completed_at'] = datetime.now().isoformat()

            # 保存生成的文件
            task['files'] = {
                'no_subtitle': result.get('no_subtitle'),
                'new_soft_subtitle': result.get('new_soft_subtitle'),
                'new_hard_subtitle': result.get('new_hard_subtitle'),
                'original_soft_subtitle': result.get('original_soft_subtitle'),
                'original_hard_subtitle': result.get('original_hard_subtitle'),
                'merged_audio': result.get('merged_audio'),
                'mixed_audio': result.get('mixed_audio')
            }

            # 记录所有文件
            logger.info(f"   生成的文件:")
            for key, value in task['files'].items():
                if value:
                    logger.info(f"      ✅ {key}: {value}")
                else:
                    logger.info(f"      ❌ {key}: None")

        logger.info(f"✅ 完整字幕生成任务 {task_id} 处理成功")
        logger.info(f"   💾 保存位置: {output_dir}")
        logger.info("=" * 60)

    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"❌ 完整字幕生成任务 {task_id} 处理失败: {str(e)}")
        logger.error(f"   错误类型: {type(e).__name__}")
        logger.error(f"   错误信息: {str(e)}")

        # 更新任务状态为失败
        with subtitle_tasks_lock:
            subtitle_tasks[task_id]['status'] = 'failed'
            subtitle_tasks[task_id]['error'] = str(e)
            subtitle_tasks[task_id]['message'] = f'处理失败: {str(e)}'
        logger.error("=" * 60)


def _process_video_only(recomposer, task_id, video_path, srt_path, output_dir,
                       subtitle_config, original_srt_path, enable_ai_separation, generate_no_subtitle):
    """只处理视频，不处理音频（简化版本）"""
    from moviepy import VideoFileClip
    import subprocess

    video_name = Path(video_path).stem
    result = {}

    # 1. 生成不带字幕的视频（如果需要）
    if generate_no_subtitle:
        update_subtitle_task_status(task_id, 'processing', 20, '正在生成不带字幕视频...')
        no_subtitle_path = os.path.join(output_dir, f"{video_name}_no_subtitle.mp4")
        # 直接复制原视频
        subprocess.run(['ffmpeg', '-y', '-i', video_path, '-c', 'copy', no_subtitle_path],
                      capture_output=True, check=True)
        result['no_subtitle'] = no_subtitle_path
        logger.info(f"✅ 不带字幕视频: {no_subtitle_path}")

    # 2. 生成新字幕软字幕视频
    update_subtitle_task_status(task_id, 'processing', 40, '正在生成新字幕软字幕视频...')
    new_soft_path = os.path.join(output_dir, f"{video_name}_new_soft.mp4")
    success = create_soft_subtitle_video(video_path, srt_path, new_soft_path)
    if success:
        result['new_soft_subtitle'] = new_soft_path
        logger.info(f"✅ 新字幕软字幕视频: {new_soft_path}")

    # 3. 生成新字幕硬字幕视频
    update_subtitle_task_status(task_id, 'burning', 60, '正在生成新字幕硬字幕视频...')
    new_hard_path = os.path.join(output_dir, f"{video_name}_new_hard.mp4")
    success = create_hard_subtitle_video(video_path, srt_path, new_hard_path, subtitle_config)
    if success:
        result['new_hard_subtitle'] = new_hard_path
        logger.info(f"✅ 新字幕硬字幕视频: {new_hard_path}")

    # 4. 如果有原字幕，生成原字幕版本
    if original_srt_path and os.path.exists(original_srt_path):
        update_subtitle_task_status(task_id, 'burning', 80, '正在生成原字幕视频...')

        original_soft_path = os.path.join(output_dir, f"{video_name}_original_soft.mp4")
        success = create_soft_subtitle_video(video_path, original_srt_path, original_soft_path)
        if success:
            result['original_soft_subtitle'] = original_soft_path
            logger.info(f"✅ 原字幕软字幕视频: {original_soft_path}")

        original_hard_path = os.path.join(output_dir, f"{video_name}_original_hard.mp4")
        success = create_hard_subtitle_video(video_path, original_srt_path, original_hard_path, subtitle_config)
        if success:
            result['original_hard_subtitle'] = original_hard_path
            logger.info(f"✅ 原字幕硬字幕视频: {original_hard_path}")

    return result


def update_subtitle_task_status(task_id, status, progress, message):
    """更新字幕任务状态"""
    with subtitle_tasks_lock:
        if task_id in subtitle_tasks:
            task = subtitle_tasks[task_id]
            task['status'] = status
            task['progress'] = progress
            task['message'] = message

            # 更新步骤状态
            if 'steps' in task and task['steps']:
                # 根据进度确定当前步骤
                step_count = len(task['steps'])
                current_step_index = int((progress / 100) * (step_count - 1))
                for i, step in enumerate(task['steps']):
                    if i < current_step_index:
                        step['status'] = 'completed'
                    elif i == current_step_index:
                        step['status'] = 'processing'
                        step['message'] = message
                    else:
                        step['status'] = 'pending'


@app.route('/api/subtitle-generate/status/<task_id>', methods=['GET'])
def subtitle_generate_status(task_id):
    """获取字幕生成任务状态"""
    with subtitle_tasks_lock:
        task = subtitle_tasks.get(task_id)
        if not task:
            return jsonify({'error': '任务不存在'}), 404

        # 确保files字段存在，如果不存在则初始化
        if 'files' not in task:
            task['files'] = {}
            logger.info(f"   [状态查询] 初始化files字段为空字典")

        # 兼容旧格式：如果使用旧的处理函数，将旧字段映射到新格式
        if not task['files'] and task.get('soft_subtitle_video'):
            task['files']['soft'] = task.get('soft_subtitle_video')
            logger.info(f"   [状态查询] 映射旧字段soft_subtitle_video到files.soft")

        if not task['files'] and task.get('hard_subtitle_video'):
            task['files']['hard'] = task.get('hard_subtitle_video')
            logger.info(f"   [状态查询] 映射旧字段hard_subtitle_video到files.hard")

        # 同时也保持新格式的映射（为了前端兼容性）
        if task.get('files', {}).get('new_soft_subtitle'):
            task['soft_subtitle_video'] = task['files']['new_soft_subtitle']

        if task.get('files', {}).get('new_hard_subtitle'):
            task['hard_subtitle_video'] = task['files']['new_hard_subtitle']

        # 记录状态
        if task['status'] == 'completed':
            logger.info(f"   [状态查询] 任务已完成，files字段内容:")
            for key, value in task['files'].items():
                if value:
                    logger.info(f"      {key}: {value}")
                else:
                    logger.info(f"      {key}: None")

        return jsonify(task)


@app.route('/api/subtitle-generate/download/<task_id>/<type>', methods=['GET'])
def subtitle_generate_download(task_id, type):
    """
    下载生成的文件（支持多种类型）

    Args:
        task_id: 任务ID
        type: 文件类型
            - no_subtitle: 不带字幕视频
            - soft: 新字幕软字幕视频
            - hard: 新字幕硬字幕视频
            - original_soft: 原字幕软字幕视频
            - original_hard: 原字幕硬字幕视频
            - merged_audio: 合并的配音音频
            - mixed_audio: 伴奏混合音频
            - vocals: 人声
            - no_vocals: 伴奏
    """
    with subtitle_tasks_lock:
        task = subtitle_tasks.get(task_id)
        if not task:
            return jsonify({'error': '任务不存在'}), 404

        if task['status'] != 'completed':
            return jsonify({'error': '任务未完成'}), 400

    try:
        # 文件类型映射
        file_mapping = {
            'no_subtitle': task.get('files', {}).get('no_subtitle'),
            'soft': task.get('files', {}).get('new_soft_subtitle'),
            'hard': task.get('files', {}).get('new_hard_subtitle'),
            'original_soft': task.get('files', {}).get('original_soft_subtitle'),
            'original_hard': task.get('files', {}).get('original_hard_subtitle'),
            'merged_audio': task.get('files', {}).get('merged_audio'),
            'mixed_audio': task.get('files', {}).get('mixed_audio'),
            'vocals': task.get('files', {}).get('vocals'),
            'no_vocals': task.get('files', {}).get('no_vocals')
        }

        file_path = file_mapping.get(type)

        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': f'文件不存在: {type}'}), 404

        filename = os.path.basename(file_path)
        return send_file(file_path, as_attachment=True, download_name=filename)

    except Exception as e:
        logger.error(f"下载失败: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/subtitle-generate/task/<task_id>', methods=['DELETE'])
def subtitle_generate_delete_task(task_id):
    """删除字幕生成任务"""
    with subtitle_tasks_lock:
        task = subtitle_tasks.get(task_id)
        if not task:
            return jsonify({'error': '任务不存在'}), 404

        # 删除任务目录
        task_dir = os.path.join(TASKS_FOLDER, f'subtitle_{task_id}')
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir)
            logger.info(f"已删除任务目录: {task_dir}")

        # 删除任务记录
        del subtitle_tasks[task_id]

        return jsonify({'message': '任务已删除'})


def _process_audio_only_simple(task_id, srt_path, output_dir, audio_zip_path):
    """处理纯音频合成（无视频文件模式）

    根据字幕时间戳将配音文件合成为音轨，字幕之间填充静音

    Args:
        task_id: 任务ID
        srt_path: 字幕文件路径
        output_dir: 输出目录
        audio_zip_path: 配音ZIP文件路径

    Returns:
        dict: 包含生成的文件路径
    """
    import subprocess
    import zipfile
    import glob
    from pathlib import Path

    result = {}
    video_name = f"audio_mix_{task_id[:8]}"

    try:
        update_subtitle_task_status(task_id, 'processing', 10, '正在解析字幕文件...')

        # 1. 解析字幕文件
        subtitles = parse_srt(srt_path)
        logger.info(f"📝 解析字幕文件: {len(subtitles)} 条字幕")

        if not subtitles:
            update_subtitle_task_status(task_id, 'failed', 0, '字幕文件为空')
            return result

        # 获取最后一条字幕的结束时间作为总时长
        total_duration = subtitles[-1]['end']
        logger.info(f"📹 音频总时长: {total_duration:.2f} 秒")

        # 2. 解压配音文件
        update_subtitle_task_status(task_id, 'processing', 30, '正在解压配音文件...')
        zip_extract_dir = os.path.join(output_dir, 'audio_segments')
        os.makedirs(zip_extract_dir, exist_ok=True)

        with zipfile.ZipFile(audio_zip_path, 'r') as zip_ref:
            zip_ref.extractall(zip_extract_dir)

        logger.info(f"解压完成，目录: {zip_extract_dir}")

        # 3. 获取所有音频文件并按名称排序
        audio_files = []
        for ext in ['*.mp3', '*.wav', '*.m4a']:
            audio_files.extend(glob.glob(os.path.join(zip_extract_dir, ext)))
        audio_files.sort()

        logger.info(f"找到 {len(audio_files)} 个配音音频文件")

        if len(audio_files) < len(subtitles):
            logger.warning(f"⚠️ 配音音频数量 ({len(audio_files)}) 少于字幕数量 ({len(subtitles)})")

        # 4. 创建临时目录
        temp_dir = output_dir

        # 5. 合成音频
        update_subtitle_task_status(task_id, 'processing', 60, '正在合成音频...')

        if not audio_files:
            # 没有配音文件，生成全静音音频
            logger.warning("⚠️ 没有配音文件，生成静音音频")
            output_path = os.path.join(output_dir, f"{video_name}_mixed_audio.mp3")

            cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi',
                '-i', f'anullsrc=r=44100:cl=stereo',
                '-t', str(total_duration),
                '-q:a', '2',
                '-b:a', '192k',
                output_path
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            result['mixed_audio'] = output_path
        else:
            # 使用多音轨合成函数
            success = merge_dubbing_audios(
                srt_path,
                zip_extract_dir,
                os.path.join(output_dir, f"{video_name}_mixed_audio.mp3")
            )

            if success:
                result['mixed_audio'] = os.path.join(output_dir, f"{video_name}_mixed_audio.mp3")
            else:
                update_subtitle_task_status(task_id, 'failed', 80, '音频合成失败')
                return result

        update_subtitle_task_status(task_id, 'processing', 100, '音频合成完成')

        # 记录生成的文件
        logger.info(f"📊 音频合成结果:")
        for key, value in result.items():
            if value:
                logger.info(f"   ✅ {key}: {value}")

        return result

    except Exception as e:
        logger.error(f"❌ 纯音频合成失败: {e}")
        import traceback
        traceback.print_exc()
        update_subtitle_task_status(task_id, 'failed', 0, f'处理失败: {str(e)}')
        return result


def _process_video_only(recomposer, task_id, video_path, srt_path, output_dir,
                       subtitle_config, original_srt_path, enable_ai_separation, generate_no_subtitle):
    """只处理视频，不处理音频（简化版本）"""
    from moviepy import VideoFileClip
    import subprocess

    video_name = Path(video_path).stem
    result = {}

    # 1. 生成不带字幕的视频（如果需要）
    if generate_no_subtitle:
        update_subtitle_task_status(task_id, 'processing', 20, '正在生成不带字幕视频...')
        no_subtitle_path = os.path.join(output_dir, f"{video_name}_no_subtitle.mp4")
        # 直接复制原视频
        subprocess.run(['ffmpeg', '-y', '-i', video_path, '-c', 'copy', no_subtitle_path],
                      capture_output=True, check=True)
        result['no_subtitle'] = no_subtitle_path
        logger.info(f"✅ 不带字幕视频: {no_subtitle_path}")

    # 2. 生成新字幕软字幕视频
    update_subtitle_task_status(task_id, 'processing', 40, '正在生成新字幕软字幕视频...')
    new_soft_path = os.path.join(output_dir, f"{video_name}_new_soft.mp4")
    success = create_soft_subtitle_video(video_path, srt_path, new_soft_path)
    if success:
        result['new_soft_subtitle'] = new_soft_path
        logger.info(f"✅ 新字幕软字幕视频: {new_soft_path}")

    # 3. 生成新字幕硬字幕视频
    update_subtitle_task_status(task_id, 'burning', 60, '正在生成新字幕硬字幕视频...')
    new_hard_path = os.path.join(output_dir, f"{video_name}_new_hard.mp4")
    success = create_hard_subtitle_video(video_path, srt_path, new_hard_path, subtitle_config)
    if success:
        result['new_hard_subtitle'] = new_hard_path
        logger.info(f"✅ 新字幕硬字幕视频: {new_hard_path}")

    # 4. 如果有原字幕，生成原字幕版本
    if original_srt_path and os.path.exists(original_srt_path):
        update_subtitle_task_status(task_id, 'burning', 80, '正在生成原字幕视频...')

        original_soft_path = os.path.join(output_dir, f"{video_name}_original_soft.mp4")
        success = create_soft_subtitle_video(video_path, original_srt_path, original_soft_path)
        if success:
            result['original_soft_subtitle'] = original_soft_path
            logger.info(f"✅ 原字幕软字幕视频: {original_soft_path}")

        original_hard_path = os.path.join(output_dir, f"{video_name}_original_hard.mp4")
        success = create_hard_subtitle_video(video_path, original_srt_path, original_hard_path, subtitle_config)
        if success:
            result['original_hard_subtitle'] = original_hard_path
            logger.info(f"✅ 原字幕硬字幕视频: {original_hard_path}")

    return result


audio_split_tasks = {}
audio_split_tasks_lock = threading.Lock()


@app.route('/api/subtitle-audio-split', methods=['POST'])
def subtitle_audio_split_upload():
    """
    根据字幕文件分割音频文件，每个字幕对应一个MP3文件，间隙使用静音

    Request:
        - video: 原视频文件（用于提取音频，可选）
        - audio: 配音音频文件（可选，如果提供则使用此音频）
        - srt: 字幕文件（必需）
        - use_silence: 是否使用静音填充间隙（默认true）

    Response:
        - task_id: 任务ID
    """
    try:
        logger.info("=" * 60)
        logger.info("收到字幕音频分割任务")

        # 检查字幕文件
        if 'srt' not in request.files:
            return jsonify({'error': '缺少字幕文件'}), 400

        srt = request.files['srt']
        video = request.files.get('video')
        audio = request.files.get('audio')

        # 获取配置
        use_silence = request.form.get('use_silence', 'true').lower() == 'true'

        if srt.filename == '':
            return jsonify({'error': '字幕文件名为空'}), 400

        # 必须提供视频或音频文件之一
        if not video and not audio:
            return jsonify({'error': '必须提供视频文件或音频文件'}), 400

        # 生成任务ID
        task_id = str(uuid.uuid4())

        # 创建任务目录
        task_dir = os.path.join(TASKS_FOLDER, f'audio_split_{task_id}')
        os.makedirs(task_dir, exist_ok=True)

        # 保存字幕文件
        srt_path = os.path.join(task_dir, srt.filename)
        srt.save(srt_path)

        # 确定音频源
        audio_source_path = None
        if audio and audio.filename:
            # 如果提供了单独的音频文件，使用它
            audio_source_path = os.path.join(task_dir, audio.filename)
            audio.save(audio_source_path)
            logger.info(f"使用音频文件: {audio.filename}")
        elif video and video.filename:
            # 否则从视频中提取音频
            video_path = os.path.join(task_dir, video.filename)
            video.save(video_path)
            audio_source_path = os.path.join(task_dir, 'extracted_audio.mp3')
            logger.info(f"从视频提取音频: {video.filename}")

        # 创建输出目录
        output_dir = os.path.join(OUTPUT_FOLDER, f'audio_split_{task_id}')
        os.makedirs(output_dir, exist_ok=True)

        logger.info(f"任务ID: {task_id}")
        logger.info(f"字幕: {srt.filename}")
        logger.info(f"音频源: {audio_source_path}")
        logger.info(f"使用静音填充: {use_silence}")

        # 初始化任务
        with audio_split_tasks_lock:
            audio_split_tasks[task_id] = {
                'type': 'audio_split',
                'status': 'processing',
                'progress': 0,
                'message': '正在处理',
                'created_at': datetime.now().isoformat(),
                'srt_path': srt_path,
                'audio_source_path': audio_source_path,
                'video_path': video_path if video else None,
                'output_dir': output_dir,
                'use_silence': use_silence,
                'audio_files': [],
                'error': None
            }

        # 在后台线程中处理
        thread = threading.Thread(
            target=process_audio_split_task,
            args=(task_id, srt_path, audio_source_path, output_dir, use_silence)
        )
        thread.daemon = True
        thread.start()

        logger.info("=" * 60)

        return jsonify({
            'task_id': task_id,
            'status': 'processing',
            'message': '任务已创建，正在处理'
        })

    except Exception as e:
        logger.error(f"创建任务失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def process_audio_split_task(task_id, srt_path, audio_source_path, output_dir, use_silence):
    """处理音频分割任务（后台线程）"""
    try:
        logger.info(f"🎬 开始处理音频分割任务 {task_id}")

        # 如果需要从视频提取音频
        if 'video_path' in audio_split_tasks[task_id] and audio_split_tasks[task_id]['video_path']:
            video_path = audio_split_tasks[task_id]['video_path']
            logger.info(f"正在从视频提取音频...")
            success = extract_audio_from_video(video_path, audio_source_path)
            if not success:
                with audio_split_tasks_lock:
                    audio_split_tasks[task_id]['status'] = 'failed'
                    audio_split_tasks[task_id]['error'] = '音频提取失败'
                return

        # 解析字幕文件
        logger.info(f"正在解析字幕文件...")
        subtitles = parse_srt(srt_path)
        logger.info(f"解析到 {len(subtitles)} 条字幕")

        # 处理每条字幕，生成对应的音频文件
        audio_files = []
        for i, sub in enumerate(subtitles):
            update_audio_split_task_status(task_id, int((i / len(subtitles)) * 100),
                                         f'正在处理第 {i+1}/{len(subtitles)} 个音频片段...')

            start_time = sub['start']
            end_time = sub['end']
            duration = end_time - start_time

            # 输出文件名
            output_filename = f"subtitle_{i+1:03d}_{start_time:.3f}-{end_time:.3f}.mp3"
            output_path = os.path.join(output_dir, output_filename)

            # 提取音频片段
            success = extract_audio_segment(audio_source_path, start_time, duration, output_path)

            if success:
                audio_files.append({
                    'index': i + 1,
                    'filename': output_filename,
                    'start': start_time,
                    'end': end_time,
                    'text': sub['text'],
                    'path': output_path
                })
            else:
                logger.warning(f"音频片段 {i+1} 提取失败")

        # 生成静音片段（如果需要）
        if use_silence:
            logger.info(f"正在生成静音片段...")
            silence_dir = os.path.join(output_dir, 'silences')
            os.makedirs(silence_dir, exist_ok=True)

            for i in range(len(subtitles) - 1):
                # 计算当前字幕结束到下一条字幕开始的时间差
                current_end = subtitles[i]['end']
                next_start = subtitles[i + 1]['start']
                gap_duration = next_start - current_end

                if gap_duration > 0.1:  # 忽略小于0.1秒的间隙
                    silence_filename = f"silence_{i+1:03d}_{current_end:.3f}-{next_start:.3f}.mp3"
                    silence_path = os.path.join(silence_dir, silence_filename)

                    # 生成静音
                    success = generate_silence(gap_duration, silence_path)

                    if success:
                        audio_files.append({
                            'index': f'silence_{i+1}',
                            'filename': f"silences/{silence_filename}",
                            'start': current_end,
                            'end': next_start,
                            'text': '[静音]',
                            'path': silence_path
                        })

        # 任务完成
        with audio_split_tasks_lock:
            audio_split_tasks[task_id]['status'] = 'completed'
            audio_split_tasks[task_id]['progress'] = 100
            audio_split_tasks[task_id]['message'] = '处理完成'
            audio_split_tasks[task_id]['audio_files'] = audio_files
            audio_split_tasks[task_id]['completed_at'] = datetime.now().isoformat()

        logger.info(f"✅ 音频分割任务 {task_id} 处理成功")
        logger.info(f"   生成了 {len([f for f in audio_files if not f['filename'].startswith('silences/')])} 个字幕音频文件")
        if use_silence:
            logger.info(f"   生成了 {len([f for f in audio_files if f['filename'].startswith('silences/')])} 个静音文件")
        logger.info(f"   💾 保存位置: {output_dir}")
        logger.info("=" * 60)

    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"❌ 音频分割任务 {task_id} 处理失败: {str(e)}")

        with audio_split_tasks_lock:
            audio_split_tasks[task_id]['status'] = 'failed'
            audio_split_tasks[task_id]['error'] = str(e)
            audio_split_tasks[task_id]['message'] = f'处理失败: {str(e)}'
        logger.error("=" * 60)


def extract_audio_from_video(video_path: str, output_path: str) -> bool:
    """从视频提取音频"""
    try:
        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-vn',
            '-acodec', 'libmp3lame',
            '-q:a', '2',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if result.returncode == 0 and os.path.exists(output_path):
            logger.info(f"   ✅ 音频提取成功")
            return True
        else:
            logger.error(f"   ❌ 音频提取失败")
            if result.stderr:
                logger.error(f"   错误: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"   ⏱️  音频提取超时")
        return False
    except Exception as e:
        logger.error(f"   ❌ 出错: {e}")
        return False


def extract_audio_segment(audio_path: str, start_time: float, duration: float, output_path: str) -> bool:
    """从音频文件提取指定时间段的片段"""
    try:
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start_time),
            '-t', str(duration),
            '-i', audio_path,
            '-acodec', 'copy',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        return result.returncode == 0 and os.path.exists(output_path)

    except Exception as e:
        logger.warning(f"   ⚠️  提取音频片段失败: {e}")
        return False


def generate_silence(duration: float, output_path: str) -> bool:
    """生成指定时长的静音MP3文件（立体声）"""
    try:
        cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', f'anullsrc=r=44100:cl=stereo',
            '-t', str(duration),
            '-acodec', 'libmp3lame',
            '-q:a', '2',
            '-b:a', '192k',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        return result.returncode == 0 and os.path.exists(output_path)

    except Exception as e:
        logger.warning(f"   ⚠️  生成静音失败: {e}")
        return False


def update_audio_split_task_status(task_id, progress, message):
    """更新音频分割任务状态"""
    with audio_split_tasks_lock:
        if task_id in audio_split_tasks:
            audio_split_tasks[task_id]['progress'] = progress
            audio_split_tasks[task_id]['message'] = message


@app.route('/api/subtitle-audio-split/status/<task_id>', methods=['GET'])
def audio_split_status(task_id):
    """获取音频分割任务状态"""
    with audio_split_tasks_lock:
        task = audio_split_tasks.get(task_id)
        if not task:
            return jsonify({'error': '任务不存在'}), 404
        return jsonify(task)


@app.route('/api/subtitle-audio-split/download/<task_id>', methods=['GET'])
def audio_split_download(task_id):
    """下载音频分割结果（ZIP压缩包）"""
    with audio_split_tasks_lock:
        task = audio_split_tasks.get(task_id)
        if not task:
            return jsonify({'error': '任务不存在'}), 404

        if task['status'] != 'completed':
            return jsonify({'error': '任务未完成'}), 400

    try:
        import zipfile
        from io import BytesIO

        # 创建内存中的ZIP文件
        memory_file = BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for audio_file in task['audio_files']:
                if os.path.exists(audio_file['path']):
                    # 添加文件到ZIP，使用相对路径
                    arcname = audio_file['filename']
                    zf.write(audio_file['path'], arcname)

        memory_file.seek(0)

        # 发送ZIP文件
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'audio_split_{task_id}.zip'
        )

    except Exception as e:
        logger.error(f"下载失败: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/subtitle-audio-split/task/<task_id>', methods=['DELETE'])
def audio_split_delete_task(task_id):
    """删除音频分割任务"""
    with audio_split_tasks_lock:
        task = audio_split_tasks.get(task_id)
        if not task:
            return jsonify({'error': '任务不存在'}), 404

        # 删除任务目录
        task_dir = os.path.join(TASKS_FOLDER, f'audio_split_{task_id}')
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir)
            logger.info(f"已删除任务目录: {task_dir}")

        # 删除输出目录
        output_dir = task.get('output_dir')
        if output_dir and os.path.exists(output_dir):
            shutil.rmtree(output_dir)
            logger.info(f"已删除输出目录: {output_dir}")

        # 删除任务记录
        del audio_split_tasks[task_id]

        return jsonify({'message': '任务已删除'})


# ==================== 音轨合成API ====================

audio_mix_tasks = {}
audio_mix_tasks_lock = threading.Lock()


@app.route('/api/audio-mix', methods=['POST'])
def audio_mix_upload():
    """
    音轨合成 - 分离人声伴奏、合并配音音轨并合成

    Request:
        - video: 原视频文件（必需）
        - srt: 字幕文件（必需）
        - vocals: 人声音频文件（可选，如果提供则跳过分离）
        - accompaniment: 伴奏音频文件（可选，如果提供则跳过分离）
        - dubbing_audio_dir: 配音音频文件夹ZIP（包含多个MP3文件，按字幕顺序命名）

    Response:
        - task_id: 任务ID
    """
    try:
        logger.info("=" * 60)
        logger.info("收到音轨合成任务")

        # 检查必需文件
        if 'video' not in request.files:
            return jsonify({'error': '缺少视频文件'}), 400
        if 'srt' not in request.files:
            return jsonify({'error': '缺少字幕文件'}), 400

        video = request.files['video']
        srt = request.files['srt']
        vocals_file = request.files.get('vocals')
        accompaniment_file = request.files.get('accompaniment')
        dubbing_zip = request.files.get('dubbing_audio_dir')

        if video.filename == '' or srt.filename == '':
            return jsonify({'error': '文件名为空'}), 400

        # 生成任务ID
        task_id = str(uuid.uuid4())

        # 创建任务目录
        task_dir = os.path.join(TASKS_FOLDER, f'audio_mix_{task_id}')
        os.makedirs(task_dir, exist_ok=True)

        # 保存文件
        video_path = os.path.join(task_dir, video.filename)
        srt_path = os.path.join(task_dir, srt.filename)
        video.save(video_path)
        srt.save(srt_path)

        vocals_path = None
        accompaniment_path = None
        skip_separation = False

        # 如果提供了人声和伴奏，直接使用
        if vocals_file and vocals_file.filename:
            vocals_path = os.path.join(task_dir, vocals_file.filename)
            vocals_file.save(vocals_path)
            logger.info(f"使用提供的人声文件: {vocals_file.filename}")

        if accompaniment_file and accompaniment_file.filename:
            accompaniment_path = os.path.join(task_dir, accompaniment_file.filename)
            accompaniment_file.save(accompaniment_path)
            logger.info(f"使用提供的伴奏文件: {accompaniment_file.filename}")

        if vocals_path and accompaniment_path:
            skip_separation = True

        # 处理配音音频ZIP文件
        dubbing_audio_dir = os.path.join(task_dir, 'dubbing_audios')
        os.makedirs(dubbing_audio_dir, exist_ok=True)

        if dubbing_zip and dubbing_zip.filename:
            zip_path = os.path.join(task_dir, dubbing_zip.filename)
            dubbing_zip.save(zip_path)
            logger.info(f"配音音频ZIP: {dubbing_zip.filename}")

            # 解压ZIP文件
            import zipfile
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(dubbing_audio_dir)
            logger.info(f"解压了 {len(os.listdir(dubbing_audio_dir))} 个配音音频文件")

        # 创建输出目录
        output_dir = os.path.join(OUTPUT_FOLDER, f'audio_mix_{task_id}')
        os.makedirs(output_dir, exist_ok=True)

        logger.info(f"任务ID: {task_id}")
        logger.info(f"视频: {video.filename}")
        logger.info(f"字幕: {srt.filename}")
        logger.info(f"跳过人声分离: {skip_separation}")
        logger.info(f"配音音频数量: {len(os.listdir(dubbing_audio_dir)) if os.path.exists(dubbing_audio_dir) else 0}")

        # 初始化步骤列表
        steps = [
            {'id': 1, 'name': '提取原视频音轨', 'status': 'pending', 'message': '等待开始...'},
            {'id': 2, 'name': 'AI分离人声和伴奏', 'status': 'pending', 'message': '等待开始...'},
            {'id': 3, 'name': '合并配音音轨', 'status': 'pending', 'message': '等待开始...'},
            {'id': 4, 'name': '混合人声和配音', 'status': 'pending', 'message': '等待开始...'},
            {'id': 5, 'name': '生成最终音轨', 'status': 'pending', 'message': '等待开始...'}
        ]

        # 如果跳过分离，调整步骤列表
        if skip_separation:
            steps = [
                {'id': 1, 'name': '使用提供的人声和伴奏', 'status': 'pending', 'message': '等待开始...'},
                {'id': 2, 'name': '合并配音音轨', 'status': 'pending', 'message': '等待开始...'},
                {'id': 3, 'name': '混合人声和配音', 'status': 'pending', 'message': '等待开始...'},
                {'id': 4, 'name': '生成最终音轨', 'status': 'pending', 'message': '等待开始...'}
            ]

        # 初始化任务
        with audio_mix_tasks_lock:
            audio_mix_tasks[task_id] = {
                'type': 'audio_mix',
                'status': 'processing',
                'progress': 0,
                'message': '正在处理',
                'created_at': datetime.now().isoformat(),
                'video_path': video_path,
                'srt_path': srt_path,
                'vocals_path': vocals_path,
                'accompaniment_path': accompaniment_path,
                'skip_separation': skip_separation,
                'dubbing_audio_dir': dubbing_audio_dir,
                'output_dir': output_dir,
                'separated_vocals': None,
                'separated_accompaniment': None,
                'merged_dubbing': None,
                'final_audio': None,
                'error': None,
                'steps': steps,
                'current_step': 0
            }

        # 在后台线程中处理
        thread = threading.Thread(
            target=process_audio_mix_task,
            args=(task_id, video_path, srt_path, output_dir, vocals_path, accompaniment_path, skip_separation, dubbing_audio_dir)
        )
        thread.daemon = True
        thread.start()

        logger.info("=" * 60)

        return jsonify({
            'task_id': task_id,
            'status': 'processing',
            'message': '任务已创建，正在处理'
        })

    except Exception as e:
        logger.error(f"创建任务失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def process_audio_mix_task(task_id, video_path, srt_path, output_dir, vocals_path, accompaniment_path, skip_separation, dubbing_audio_dir):
    """处理音轨合成任务（后台线程）"""
    try:
        logger.info(f"🎬 开始处理音轨合成任务 {task_id}")

        # 步骤1: 提取原视频音轨并分离人声伴奏（如果需要）
        if not skip_separation:
            # 步骤1.1: 提取音频
            logger.info(f"📝 步骤1/5: 提取原视频音轨")
            update_audio_mix_step_status(task_id, 1, 'processing', '正在从视频提取音频...')
            update_audio_mix_task_status(task_id, 5, '正在提取音轨...')

            temp_audio = os.path.join(output_dir, 'temp_audio.wav')
            success = extract_audio_for_demucs(video_path, temp_audio)
            if not success:
                update_audio_mix_step_status(task_id, 1, 'failed', '音频提取失败')
                with audio_mix_tasks_lock:
                    audio_mix_tasks[task_id]['status'] = 'failed'
                    audio_mix_tasks[task_id]['error'] = '音频提取失败'
                return

            update_audio_mix_step_status(task_id, 1, 'completed', '音轨提取完成')

            # 步骤1.2: AI分离人声和伴奏
            logger.info(f"📝 步骤2/5: 使用Demucs AI分离人声和伴奏")
            update_audio_mix_step_status(task_id, 2, 'processing', '正在使用Demucs AI模型分离人声和伴奏（这可能需要几分钟）...')
            update_audio_mix_task_status(task_id, 10, '正在AI分离人声和伴奏...')

            demucs_output = os.path.join(output_dir, 'demucs_output')
            success = separate_vocals_accompaniment(temp_audio, demucs_output)
            if not success:
                update_audio_mix_step_status(task_id, 2, 'failed', 'AI分离失败')
                with audio_mix_tasks_lock:
                    audio_mix_tasks[task_id]['status'] = 'failed'
                    audio_mix_tasks[task_id]['error'] = '人声分离失败'
                return

            vocals_path = os.path.join(demucs_output, 'vocals.wav')
            accompaniment_path = os.path.join(demucs_output, 'no_vocals.wav')

            with audio_mix_tasks_lock:
                audio_mix_tasks[task_id]['separated_vocals'] = vocals_path
                audio_mix_tasks[task_id]['separated_accompaniment'] = accompaniment_path

            update_audio_mix_step_status(task_id, 2, 'completed', '人声和伴奏分离完成')
        else:
            # 跳过分离步骤
            logger.info(f"📝 步骤1/4: 跳过AI分离（使用提供的人声和伴奏文件）")
            update_audio_mix_step_status(task_id, 1, 'processing', '使用提供的人声和伴奏文件')
            update_audio_mix_task_status(task_id, 15, '使用提供的人声和伴奏文件')
            update_audio_mix_step_status(task_id, 1, 'completed', '已加载提供的人声和伴奏文件')

        # 步骤: 合并配音音轨
        step_offset = 0 if skip_separation else 1
        logger.info(f"📝 步骤{2 + step_offset}/5: 按字幕时间轴合并配音音轨")
        update_audio_mix_step_status(task_id, 2 + step_offset, 'processing', '正在解析字幕并合并配音片段...')
        update_audio_mix_task_status(task_id, 35 if not skip_separation else 40, '正在合并配音音轨...')

        merged_dubbing_path = os.path.join(output_dir, 'merged_dubbing.mp3')
        success = merge_dubbing_audios(srt_path, dubbing_audio_dir, merged_dubbing_path)

        if not success:
            update_audio_mix_step_status(task_id, 2 + step_offset, 'failed', '配音音轨合并失败')
            with audio_mix_tasks_lock:
                audio_mix_tasks[task_id]['status'] = 'failed'
                audio_mix_tasks[task_id]['error'] = '配音音轨合并失败'
            return

        with audio_mix_tasks_lock:
            audio_mix_tasks[task_id]['merged_dubbing'] = merged_dubbing_path

        update_audio_mix_step_status(task_id, 2 + step_offset, 'completed', f'配音音轨合并完成')

        # 步骤: 合并人声和配音
        logger.info(f"📝 步骤{3 + step_offset}/5: 混合人声和配音音轨")
        update_audio_mix_step_status(task_id, 3 + step_offset, 'processing', '正在混合人声和配音（人声30% + 配音70%）...')
        update_audio_mix_task_status(task_id, 60, '正在混合人声和配音...')

        vocals_with_dubbing_path = os.path.join(output_dir, 'vocals_with_dubbing.mp3')
        success = mix_two_audios(vocals_path, merged_dubbing_path, vocals_with_dubbing_path, vocals_ratio=0.3, dubbing_ratio=0.7)

        if not success:
            update_audio_mix_step_status(task_id, 3 + step_offset, 'failed', '人声配音混合失败')
            with audio_mix_tasks_lock:
                audio_mix_tasks[task_id]['status'] = 'failed'
                audio_mix_tasks[task_id]['error'] = '人声配音混合失败'
            return

        update_audio_mix_step_status(task_id, 3 + step_offset, 'completed', '人声和配音混合完成')

        # 步骤: 混合伴奏和人声配音
        logger.info(f"📝 步骤{4 + step_offset}/5: 混合伴奏和人声配音生成最终音轨")
        update_audio_mix_step_status(task_id, 4 + step_offset, 'processing', '正在混合伴奏和人声配音（伴奏70% + 人声配音30%）...')
        update_audio_mix_task_status(task_id, 80, '正在生成最终音轨...')

        final_audio_path = os.path.join(output_dir, 'final_audio.mp3')
        success = mix_two_audios(accompaniment_path, vocals_with_dubbing_path, final_audio_path, vocals_ratio=0.7, dubbing_ratio=0.3)

        if not success:
            update_audio_mix_step_status(task_id, 4 + step_offset, 'failed', '最终音轨混合失败')
            with audio_mix_tasks_lock:
                audio_mix_tasks[task_id]['status'] = 'failed'
                audio_mix_tasks[task_id]['error'] = '最终音轨混合失败'
            return

        update_audio_mix_step_status(task_id, 4 + step_offset, 'completed', '最终音轨生成完成')

        # 清理临时文件，只保留需要的文件
        logger.info(f"🗑️  清理临时文件...")
        keep_files = {
            'vocals.wav',           # 人声
            'no_vocals.wav',        # 伴奏
            'final_audio.mp3',      # 最终音轨
            'merged_dubbing.mp3',   # 合并的配音
            'vocals_with_dubbing.mp3'  # 人声+配音混合
        }

        files_to_delete = []
        for file in os.listdir(output_dir):
            if file not in keep_files:
                file_path = os.path.join(output_dir, file)
                if os.path.isfile(file_path):
                    files_to_delete.append(file_path)

        # 删除临时文件
        for file_path in files_to_delete:
            try:
                os.remove(file_path)
                logger.info(f"   ✅ 已删除: {os.path.basename(file_path)}")
            except Exception as e:
                logger.warning(f"   ⚠️  删除失败 {os.path.basename(file_path)}: {e}")

        logger.info(f"   📦 保留文件: {sorted(keep_files)}")

        # 任务完成
        with audio_mix_tasks_lock:
            audio_mix_tasks[task_id]['status'] = 'completed'
            audio_mix_tasks[task_id]['progress'] = 100
            audio_mix_tasks[task_id]['message'] = '音轨合成完成'
            audio_mix_tasks[task_id]['final_audio'] = final_audio_path
            audio_mix_tasks[task_id]['completed_at'] = datetime.now().isoformat()

        logger.info(f"✅ 音轨合成任务 {task_id} 处理成功")
        logger.info(f"   最终音轨: {final_audio_path}")
        logger.info(f"   💾 保存位置: {output_dir}")
        logger.info(f"   📊 保留文件数: {len(keep_files)}")
        logger.info("=" * 60)

    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"❌ 音轨合成任务 {task_id} 处理失败: {str(e)}")

        with audio_mix_tasks_lock:
            audio_mix_tasks[task_id]['status'] = 'failed'
            audio_mix_tasks[task_id]['error'] = str(e)
            audio_mix_tasks[task_id]['message'] = f'处理失败: {str(e)}'
        logger.error("=" * 60)


def extract_audio_for_demucs(video_path: str, output_path: str) -> bool:
    """提取音频用于demucs处理"""
    try:
        logger.info(f"   正在从视频提取音频...")
        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-vn',
            '-acodec', 'pcm_s16le',  # 使用WAV格式，demucs支持更好
            '-ar', '44100',
            '-ac', '2',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if result.returncode == 0 and os.path.exists(output_path):
            logger.info(f"   ✅ 音频提取成功")
            return True
        else:
            logger.error(f"   ❌ 音频提取失败")
            if result.stderr:
                logger.error(f"   错误: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"   ⏱️  音频提取超时")
        return False
    except Exception as e:
        logger.error(f"   ❌ 出错: {e}")
        return False


def separate_vocals_accompaniment(audio_path: str, output_dir: str) -> bool:
    """使用demucs分离人声和伴奏"""
    try:
        logger.info(f"   正在使用demucs分离人声和伴奏...")
        logger.info(f"   📊 Demucs使用AI模型处理，通常需要2-5分钟...")
        logger.info(f"   ⏱️  请耐心等待，处理时间取决于音频长度...")

        # 获取当前Python解释器路径，使用venv中的Python
        import sys
        python_exe = sys.executable

        cmd = [
            python_exe, '-m', 'demucs',
            '-n', 'htdemucs',
            '--out', output_dir,
            audio_path
        ]

        # 使用Popen来获取实时输出
        import time
        start_time = time.time()

        logger.info(f"   🔧 执行命令: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1  # 行缓冲
        )

        # 实时输出demucs的进度
        last_log_time = start_time
        for line in iter(process.stdout.readline, ''):
            if line:
                current_time = time.time()
                elapsed = int(current_time - start_time)

                # 记录所有输出（帮助调试）
                line_stripped = line.strip()
                if line_stripped:
                    logger.info(f"   [Demucs] {line_stripped}")

                # 每30秒输出一次进度信息
                if current_time - last_log_time >= 30:
                    logger.info(f"   ⏳  Demucs正在处理... 已运行 {elapsed} 秒")
                    last_log_time = current_time

        # 等待进程完成
        return_code = process.wait()

        if return_code == 0:
            logger.info(f"   ✅ Demucs处理完成，用时 {int(time.time() - start_time)} 秒")

            # demucs使用htdemucs模型时，创建的子目录格式为: output_dir/htdemucs/完整文件名/vocals.wav
            # 注意：demucs保留完整的文件名（包括扩展名）作为子目录名
            audio_name_with_ext = os.path.basename(audio_path)  # temp_audio.wav
            audio_name_no_ext = Path(audio_path).stem  # temp_audio

            # 先列出实际的目录结构进行调试
            logger.info(f"   🔍 正在扫描输出目录: {output_dir}")
            for root, dirs, files in os.walk(output_dir):
                logger.info(f"   📁 {root}")
                if files:
                    logger.info(f"      文件: {files}")

            # 首先检查 htdemucs 目录下是否有 vocals.wav（demucs 可能直接输出到模型目录）
            htdemucs_dir = os.path.join(output_dir, 'htdemucs')
            src_dir = None

            if os.path.exists(htdemucs_dir):
                htdemucs_files = os.listdir(htdemucs_dir)
                logger.info(f"   📂 htdemucs 目录内容: {htdemucs_files}")

                # 查找 vocals.wav
                if 'vocals.wav' in htdemucs_files:
                    src_dir = htdemucs_dir
                    logger.info(f"   ✅ 找到 vocals.wav 在 htdemucs 目录")
                else:
                    # 如果没有 vocals.wav，检查是否有子目录
                    for item in htdemucs_files:
                        item_path = os.path.join(htdemucs_dir, item)
                        if os.path.isdir(item_path):
                            item_files = os.listdir(item_path)
                            logger.info(f"   📂 子目录 {item} 内容: {item_files}")
                            if 'vocals.wav' in item_files:
                                src_dir = item_path
                                logger.info(f"   ✅ 找到 vocals.wav 在 {item} 子目录")
                                break

            # 如果在 htdemucs 目录没找到，尝试其他可能的路径
            if not src_dir:
                # 尝试多个可能的路径（优先检查完整文件名）
                possible_paths = [
                    # htdemucs 模型 + 完整文件名
                    os.path.join(output_dir, 'htdemucs', audio_name_with_ext, 'vocals.wav'),
                    # htdemucs 模型 + 无扩展名
                    os.path.join(output_dir, 'htdemucs', audio_name_no_ext, 'vocals.wav'),
                    # 默认模型 + 完整文件名
                    os.path.join(output_dir, audio_name_with_ext, 'vocals.wav'),
                    # 默认模型 + 无扩展名
                    os.path.join(output_dir, audio_name_no_ext, 'vocals.wav'),
                ]

                logger.info(f"   🔍 检查子目录路径:")
                for path in possible_paths:
                    exists = os.path.exists(path)
                    logger.info(f"     {exists} - {path}")
                    if exists:
                        src_dir = os.path.dirname(path)
                        break

            if src_dir and os.path.exists(src_dir):
                logger.info(f"   📂 找到输出目录: {src_dir}")

                # 移动文件到目标目录
                for file in os.listdir(src_dir):
                    src_file = os.path.join(src_dir, file)
                    dst_file = os.path.join(output_dir, file)
                    if os.path.exists(dst_file):
                        os.remove(dst_file)
                    shutil.move(src_file, dst_file)
                    logger.info(f"   ✅ 已移动: {file}")

                # 检查是否有 no_vocals.wav，如果没有则从 drums + bass + other 混合生成
                no_vocals_path = os.path.join(output_dir, 'no_vocals.wav')
                if not os.path.exists(no_vocals_path):
                    logger.info(f"   🎵 正在混合伴奏 (drums + bass + other)...")

                    drums_path = os.path.join(output_dir, 'drums.wav')
                    bass_path = os.path.join(output_dir, 'bass.wav')
                    other_path = os.path.join(output_dir, 'other.wav')

                    if all(os.path.exists(p) for p in [drums_path, bass_path, other_path]):
                        # 使用 ffmpeg 混合三个音轨
                        cmd = [
                            'ffmpeg', '-y',
                            '-i', drums_path,
                            '-i', bass_path,
                            '-i', other_path,
                            '-filter_complex', '[0:a][1:a][2:a]amix=inputs=3:duration=longest',
                            '-loglevel', 'error',
                            no_vocals_path
                        ]

                        result = subprocess.run(cmd, capture_output=True, text=True)
                        if result.returncode == 0:
                            logger.info(f"   ✅ 伴奏生成成功: no_vocals.wav")
                        else:
                            logger.error(f"   ❌ 伴奏生成失败: {result.stderr}")
                            return False
                    else:
                        logger.error(f"   ❌ 缺少必要的音轨文件")
                        logger.error(f"      drums: {os.path.exists(drums_path)}")
                        logger.error(f"      bass: {os.path.exists(bass_path)}")
                        logger.error(f"      other: {os.path.exists(other_path)}")
                        return False

                # 清理空的子目录
                try:
                    htdemucs_dir = os.path.join(output_dir, 'htdemucs')
                    if os.path.exists(htdemucs_dir):
                        shutil.rmtree(htdemucs_dir)
                        logger.info(f"   🗑️  已清理临时目录")
                except:
                    pass

                logger.info(f"   ✅ 人声分离成功")
                return True
            else:
                logger.error(f"   ❌ 分离输出文件不存在")
                logger.error(f"   尝试的路径:")
                for path in possible_paths:
                    logger.error(f"     - {path}")
                # 列出实际创建的目录结构
                if os.path.exists(output_dir):
                    logger.error(f"   实际目录结构:")
                    for root, dirs, files in os.walk(output_dir):
                        level = root.replace(output_dir, '').count(os.sep)
                        indent = ' ' * 2 * (level + 1)
                        logger.error(f"{indent}{os.path.basename(root)}/")
                        subindent = ' ' * 2 * (level + 2)
                        for file in files:
                            logger.error(f"{subindent}{file}")
                return False
        else:
            logger.error(f"   ❌ demucs执行失败，返回码: {return_code}")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"   ⏱️  demucs分离超时（30分钟）")
        return False
    except Exception as e:
        logger.error(f"   ❌ 出错: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def merge_dubbing_audios(srt_path: str, audio_dir: str, output_path: str) -> bool:
    """根据字幕文件合并多个配音音频文件

    根据每个字幕的开始时间放置音频，字幕之间用静音填充
    """
    try:
        logger.info(f"   正在合并配音音轨...")

        # 解析字幕
        subtitles = parse_srt(srt_path)
        logger.info(f"   解析到 {len(subtitles)} 条字幕")

        if len(subtitles) == 0:
            logger.error(f"   ❌ 字幕文件为空")
            return False

        # 获取音频文件列表并排序
        audio_files = sorted([f for f in os.listdir(audio_dir) if f.endswith('.mp3')])

        if len(audio_files) == 0:
            logger.error(f"   ❌ 配音音频目录为空")
            return False

        logger.info(f"   找到 {len(audio_files)} 个配音音频文件")

        # 计算总时长（最后一条字幕的结束时间）
        total_duration = subtitles[-1]['end']
        logger.info(f"   总时长: {total_duration:.2f} 秒")

        # 创建临时目录
        temp_dir = os.path.join(os.path.dirname(output_path), 'temp_merge')
        os.makedirs(temp_dir, exist_ok=True)

        # 创建 concat 文件
        concat_file = os.path.join(temp_dir, 'concat.txt')
        segment_files = []

        current_time = 0.0

        for i in range(min(len(audio_files), len(subtitles))):
            sub = subtitles[i]
            audio_file = os.path.join(audio_dir, audio_files[i])

            # 在当前时间点和字幕开始时间之间添加静音
            if current_time < sub['start']:
                gap = sub['start'] - current_time
                if gap > 0.05:  # 大于50ms才生成静音
                    silence_file = os.path.join(temp_dir, f'silence_{i:03d}.mp3')
                    logger.info(f"   添加静音: {gap:.2f}秒 (从 {current_time:.2f}s 到 {sub['start']:.2f}s)")
                    if generate_silence(gap, silence_file):
                        segment_files.append(silence_file)
                        current_time += gap

            # 添加音频文件
            logger.info(f"   添加音频 {i+1}: {audio_files[i]} (在 {sub['start']:.2f}s)")
            segment_file = os.path.join(temp_dir, f'audio_{i:03d}.mp3')
            shutil.copy(audio_file, segment_file)

            # 验证文件复制成功
            if os.path.exists(segment_file):
                file_size = os.path.getsize(segment_file)
                logger.info(f"      ✅ 文件已复制: {segment_file}, 大小: {file_size} 字节")
                segment_files.append(segment_file)
            else:
                logger.error(f"      ❌ 文件复制失败: {segment_file}")
                return False

            # 更新当前时间（需要获取音频时长）
            # 这里简化处理，假设音频时长不超过字幕时长
            current_time = sub['end']

        # 在最后添加静音直到总时长
        if current_time < total_duration:
            gap = total_duration - current_time
            if gap > 0.05:
                silence_file = os.path.join(temp_dir, f'silence_end.mp3')
                logger.info(f"   添加结尾静音: {gap:.2f}秒")
                if generate_silence(gap, silence_file):
                    segment_files.append(silence_file)

        # 写入 concat 文件
        with open(concat_file, 'w') as f:
            for segment in segment_files:
                # 使用绝对路径，并转义特殊字符
                f.write(f"file '{segment}'\n")

        logger.info(f"   Concat 文件内容 (前5行):")
        with open(concat_file, 'r') as f:
            lines = f.readlines()
            for line in lines[:5]:
                logger.info(f"      {line.strip()}")

        # 使用 ffmpeg concat 协议合并
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-acodec', 'libmp3lame',
            '-q:a', '2',
            '-b:a', '192k',
            output_path
        ]

        logger.info(f"   执行合并命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        # 清理临时文件
        shutil.rmtree(temp_dir, ignore_errors=True)

        if result.returncode == 0 and os.path.exists(output_path):
            logger.info(f"   ✅ 配音音轨合并成功")
            return True
        else:
            logger.error(f"   ❌ 配音音轨合并失败")
            if result.stderr:
                logger.error(f"   错误: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"   ❌ 出错: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def mix_two_audios(audio1_path: str, audio2_path: str, output_path: str, vocals_ratio: float = 0.5, dubbing_ratio: float = 0.5) -> bool:
    """混合两个音频文件"""
    try:
        cmd = [
            'ffmpeg', '-y',
            '-i', audio1_path,
            '-i', audio2_path,
            '-filter_complex', f'[0:a]volume={vocals_ratio}[a1];[1:a]volume={dubbing_ratio}[a2];[a1][a2]amix=inputs=2:duration=longest',
            '-acodec', 'libmp3lame',
            '-q:a', '2',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode == 0 and os.path.exists(output_path):
            logger.info(f"   ✅ 音频混合成功")
            return True
        else:
            logger.error(f"   ❌ 音频混合失败")
            if result.stderr:
                logger.error(f"   错误: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"   ❌ 出错: {e}")
        return False


def update_audio_mix_task_status(task_id, progress, message):
    """更新音轨合成任务状态"""
    with audio_mix_tasks_lock:
        if task_id in audio_mix_tasks:
            audio_mix_tasks[task_id]['progress'] = progress
            audio_mix_tasks[task_id]['message'] = message


def update_audio_mix_step_status(task_id, step_id, status, message=None):
    """
    更新音轨合成任务的步骤状态

    Args:
        task_id: 任务ID
        step_id: 步骤ID（从1开始）
        status: 步骤状态 (pending, processing, completed, failed)
        message: 步骤详细信息（可选）
    """
    with audio_mix_tasks_lock:
        if task_id in audio_mix_tasks:
            task = audio_mix_tasks[task_id]
            steps = task.get('steps', [])

            # 查找对应的步骤
            for step in steps:
                if step['id'] == step_id:
                    step['status'] = status
                    if message:
                        step['message'] = message
                    break

            # 更新当前步骤
            if status == 'processing':
                task['current_step'] = step_id


@app.route('/api/audio-mix/status/<task_id>', methods=['GET'])
def audio_mix_status(task_id):
    """获取音轨合成任务状态"""
    with audio_mix_tasks_lock:
        task = audio_mix_tasks.get(task_id)
        if not task:
            return jsonify({'error': '任务不存在'}), 404
        return jsonify(task)


@app.route('/api/audio-mix/download/<task_id>', methods=['GET'])
def audio_mix_download(task_id):
    """下载音轨合成结果"""
    with audio_mix_tasks_lock:
        task = audio_mix_tasks.get(task_id)
        if not task:
            return jsonify({'error': '任务不存在'}), 404

        if task['status'] != 'completed':
            return jsonify({'error': '任务未完成'}), 400

    try:
        file_path = task.get('final_audio')
        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': '文件不存在'}), 404

        filename = os.path.basename(file_path)
        return send_file(file_path, as_attachment=True, download_name=filename)

    except Exception as e:
        logger.error(f"下载失败: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/audio-mix/task/<task_id>', methods=['DELETE'])
def audio_mix_delete_task(task_id):
    """删除音轨合成任务"""
    with audio_mix_tasks_lock:
        task = audio_mix_tasks.get(task_id)
        if not task:
            return jsonify({'error': '任务不存在'}), 404

        # 删除任务目录
        task_dir = os.path.join(TASKS_FOLDER, f'audio_mix_{task_id}')
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir)
            logger.info(f"已删除任务目录: {task_dir}")

        # 删除输出目录
        output_dir = task.get('output_dir')
        if output_dir and os.path.exists(output_dir):
            shutil.rmtree(output_dir)
            logger.info(f"已删除输出目录: {output_dir}")

        # 删除任务记录
        del audio_mix_tasks[task_id]

        return jsonify({'message': '任务已删除'})


# ==================== 原有API ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'service': 'Video Recomp API'
    })


@app.before_request
def log_request():
    """记录请求日志"""
    if request.path.startswith('/api/'):
        logger.info(f"📨 {request.method} {request.path}")


@app.route('/api/upload', methods=['POST'])
def upload_files():
    """
    上传文件接口

    Request:
        - video: 原视频文件
        - original_srt: 原字幕文件（可选）
        - srt: 新字幕文件（必需）
        - audio: 配音ZIP文件
        - auto_clip: 是否自动剪辑视频（可选，默认False）

    Response:
        - task_id: 任务ID
    """
    try:
        logger.info("=" * 60)
        logger.info("收到新的视频重新生成任务")

        # 检查必需文件
        if 'video' not in request.files or 'srt' not in request.files or 'audio' not in request.files:
            logger.error("❌ 缺少必需文件")
            return jsonify({'error': '缺少必需文件'}), 400

        video = request.files['video']
        srt = request.files['srt']
        audio = request.files['audio']
        original_srt = request.files.get('original_srt')  # 可选

        # 获取自动剪辑选项
        auto_clip = request.form.get('auto_clip', 'false').lower() == 'true'

        logger.info(f"📹 原视频: {video.filename}")
        if original_srt and original_srt.filename:
            logger.info(f"📝 原字幕文件: {original_srt.filename}")
        logger.info(f"📝 新字幕文件: {srt.filename}")
        logger.info(f"🎤 配音文件: {audio.filename}")
        if auto_clip:
            logger.info(f"✂️  自动剪辑视频: 启用")

        # 检查文件名
        if video.filename == '' or srt.filename == '' or audio.filename == '':
            logger.error("❌ 文件名为空")
            return jsonify({'error': '文件名为空'}), 400

        # 验证文件类型
        if not audio.filename.lower().endswith('.zip'):
            logger.error(f"❌ 配音文件格式错误: {audio.filename}")
            return jsonify({'error': '配音文件必须是ZIP格式'}), 400

        if not srt.filename.lower().endswith('.srt'):
            logger.error(f"❌ 新字幕文件格式错误: {srt.filename}")
            return jsonify({'error': '新字幕文件必须是SRT格式'}), 400

        if original_srt and original_srt.filename and not original_srt.filename.lower().endswith('.srt'):
            logger.error(f"❌ 原字幕文件格式错误: {original_srt.filename}")
            return jsonify({'error': '原字幕文件必须是SRT格式'}), 400

        # 创建任务ID
        task_id = str(uuid.uuid4())
        task_folder = os.path.join(TASKS_FOLDER, task_id)
        os.makedirs(task_folder, exist_ok=True)

        logger.info(f"✅ 创建任务ID: {task_id}")

        # 保存文件
        video_path = os.path.join(task_folder, 'original_video.mp4')
        srt_path = os.path.join(task_folder, 'subtitles.srt')
        audio_path = os.path.join(task_folder, 'audio.zip')

        video.save(video_path)
        srt.save(srt_path)
        audio.save(audio_path)

        # 保存原字幕文件（如果存在）
        original_srt_path = None
        if original_srt and original_srt.filename:
            original_srt_path = os.path.join(task_folder, 'original_subtitles.srt')
            original_srt.save(original_srt_path)
            logger.info(f"   - 原字幕大小: {os.path.getsize(original_srt_path) / 1024:.2f} KB")

        logger.info(f"✅ 文件保存完成")
        logger.info(f"   - 视频大小: {os.path.getsize(video_path) / 1024 / 1024:.2f} MB")
        logger.info(f"   - 新字幕大小: {os.path.getsize(srt_path) / 1024:.2f} KB")
        logger.info(f"   - 配音大小: {os.path.getsize(audio_path) / 1024 / 1024:.2f} MB")

        # 创建带时间戳的本地输出目录
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        local_output_dir = os.path.join(OUTPUT_FOLDER, f'video_recomp_{timestamp}')
        os.makedirs(local_output_dir, exist_ok=True)
        logger.info(f"✅ 创建本地输出目录: {local_output_dir}")

        # 初始化任务状态
        with tasks_lock:
            tasks[task_id] = {
                'status': 'uploaded',
                'progress': 0,
                'message': '文件上传完成',
                'video_path': video_path,
                'srt_path': srt_path,
                'original_srt_path': original_srt_path,  # 保存原字幕路径
                'audio_path': audio_path,
                'auto_clip': auto_clip,  # 保存自动剪辑选项
                'output_folder': os.path.join(DOWNLOAD_FOLDER, task_id),
                'local_output_dir': local_output_dir,  # 本地输出目录
                'error': None,
                'created_at': datetime.now().isoformat()
            }

        logger.info(f"✅ 任务创建成功: {task_id}")
        logger.info("=" * 60)

        return jsonify({
            'task_id': task_id,
            'message': '文件上传成功'
        }), 200

    except Exception as e:
        return jsonify({'error': f'上传失败: {str(e)}'}), 500


@app.route('/api/process/<task_id>', methods=['POST'])
def process_video(task_id):
    """
    开始处理视频

    Args:
        task_id: 任务ID

    Response:
        - status: 状态
        - message: 消息
    """
    try:
        with tasks_lock:
            if task_id not in tasks:
                return jsonify({'error': '任务不存在'}), 404

            task = tasks[task_id]

            if task['status'] == 'processing':
                return jsonify({'message': '任务正在处理中'}), 200

            if task['status'] == 'completed':
                return jsonify({'message': '任务已完成'}), 200

        # 在新线程中处理视频
        thread = threading.Thread(
            target=process_video_thread,
            args=(task_id,)
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            'status': 'processing',
            'message': '开始处理视频'
        }), 200

    except Exception as e:
        return jsonify({'error': f'处理失败: {str(e)}'}), 500


def process_video_thread(task_id):
    """视频处理线程"""
    try:
        logger.info("=" * 60)
        logger.info(f"🎬 开始处理视频任务: {task_id}")

        with tasks_lock:
            task = tasks[task_id]
            task['status'] = 'processing'
            task['message'] = '正在加载视频...'

        logger.info("📂 创建输出目录")
        # 创建输出目录
        os.makedirs(tasks[task_id]['output_folder'], exist_ok=True)

        logger.info("🔧 初始化视频处理器")
        # 创建处理器（使用本地输出目录）
        recomposer = create_video_recomposer(
            original_video=tasks[task_id]['video_path'],
            srt_file=tasks[task_id]['srt_path'],
            audio_zip=tasks[task_id]['audio_path'],
            output_dir=tasks[task_id]['local_output_dir'],
            original_srt_file=tasks[task_id].get('original_srt_path'),
            auto_clip_video=tasks[task_id].get('auto_clip', False)
        )

        # 更新进度
        with tasks_lock:
            tasks[task_id]['progress'] = 10
            tasks[task_id]['message'] = '正在加载字幕...'

        logger.info("📝 加载字幕文件")

        # 处理视频
        with tasks_lock:
            tasks[task_id]['progress'] = 30
            tasks[task_id]['message'] = '正在处理配音文件...'

        logger.info("🎵 处理配音文件（合并音频片段）")
        result = recomposer.process()

        logger.info(f"✅ 视频处理完成")
        for key, path in result.items():
            if path:
                logger.info(f"   - {key}: {path}")

        # 更新为完成状态
        with tasks_lock:
            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['progress'] = 100
            tasks[task_id]['message'] = '处理完成'
            # 保存所有生成文件的路径
            for key, path in result.items():
                if path:
                    tasks[task_id][f'_{key}'] = path

        logger.info(f"✅ 任务 {task_id} 处理成功")
        logger.info("=" * 60)

    except Exception as e:
        import traceback
        traceback.print_exc()

        logger.error(f"❌ 任务 {task_id} 处理失败: {str(e)}")

        with tasks_lock:
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = str(e)
            tasks[task_id]['message'] = f'处理失败: {str(e)}'
        logger.error("=" * 60)


@app.route('/api/status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """
    获取任务状态

    Args:
        task_id: 任务ID

    Response:
        - status: 状态 (uploaded, processing, completed, failed)
        - progress: 进度 (0-100)
        - message: 消息
        - error: 错误信息 (如果有)
    """
    try:
        with tasks_lock:
            if task_id not in tasks:
                return jsonify({'error': '任务不存在'}), 404

            task = tasks[task_id]

        response = {
            'status': task['status'],
            'progress': task['progress'],
            'message': task['message'],
            'error': task.get('error')
        }

        # 如果任务完成，返回本地输出目录和文件路径
        if task['status'] == 'completed':
            response['local_output_dir'] = task.get('local_output_dir', '')
            response['merged_audio_path'] = task.get('_merged_audio', '')
            response['available_versions'] = {}

            # 新字幕版本
            if task.get('_new_soft_subtitle'):
                response['available_versions']['new_soft'] = task.get('_new_soft_subtitle')
            if task.get('_new_hard_subtitle'):
                response['available_versions']['new_hard'] = task.get('_new_hard_subtitle')

            # 原字幕版本（如果存在）
            if task.get('_original_soft_subtitle'):
                response['available_versions']['original_soft'] = task.get('_original_soft_subtitle')
            if task.get('_original_hard_subtitle'):
                response['available_versions']['original_hard'] = task.get('_original_hard_subtitle')

            # 不带字幕版本
            if task.get('_no_subtitle'):
                response['available_versions']['no_subtitle'] = task.get('_no_subtitle')

        return jsonify(response), 200

    except Exception as e:
        return jsonify({'error': f'获取状态失败: {str(e)}'}), 500


@app.route('/api/download/<task_id>/<type>', methods=['GET'])
def download_video(task_id, type):
    """
    下载处理后的视频

    Args:
        task_id: 任务ID
        type: 类型 (soft, hard, original_soft, original_hard, no_subtitle)

    Response:
        - 视频文件
    """
    try:
        with tasks_lock:
            if task_id not in tasks:
                return jsonify({'error': '任务不存在'}), 404

            task = tasks[task_id]

            if task['status'] != 'completed':
                return jsonify({'error': '任务尚未完成'}), 400

        # 确定文件路径和文件名
        type_mapping = {
            'soft': ('_new_soft_subtitle', 'output_new_soft_subtitle.mp4'),
            'hard': ('_new_hard_subtitle', 'output_new_hard_subtitle.mp4'),
            'original_soft': ('_original_soft_subtitle', 'output_original_soft_subtitle.mp4'),
            'original_hard': ('_original_hard_subtitle', 'output_original_hard_subtitle.mp4'),
            'no_subtitle': ('_no_subtitle', 'output_no_subtitle.mp4'),
            'clipped_video': ('_clipped_video', 'clipped_video.mp4')
        }

        if type not in type_mapping:
            return jsonify({'error': '无效的类型'}), 400

        key, filename = type_mapping[type]
        file_path = task.get(key)

        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': '文件不存在'}), 404

        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='video/mp4'
        )

    except Exception as e:
        return jsonify({'error': f'下载失败: {str(e)}'}), 500


@app.route('/api/task/<task_id>', methods=['DELETE'])
def cancel_task(task_id):
    """
    取消任务

    Args:
        task_id: 任务ID

    Response:
        - message: 消息
    """
    try:
        with tasks_lock:
            if task_id not in tasks:
                return jsonify({'error': '任务不存在'}), 404

            # 删除任务
            del tasks[task_id]

        # 清理文件
        task_folder = os.path.join(TASKS_FOLDER, task_id)
        download_folder = os.path.join(DOWNLOAD_FOLDER, task_id)

        if os.path.exists(task_folder):
            shutil.rmtree(task_folder)

        if os.path.exists(download_folder):
            shutil.rmtree(download_folder)

        return jsonify({'message': '任务已取消'}), 200

    except Exception as e:
        return jsonify({'error': f'取消失败: {str(e)}'}), 500


@app.route('/api/tasks', methods=['GET'])
def list_tasks():
    """列出所有任务（调试用）"""
    with tasks_lock:
        task_list = []
        for task_id, task in tasks.items():
            task_list.append({
                'task_id': task_id,
                'status': task['status'],
                'progress': task['progress'],
                'message': task['message'],
                'created_at': task['created_at']
            })

        return jsonify({'tasks': task_list}), 200


# ==================== 音频拆分相关API ====================

# 音频拆分任务存储
split_tasks = {}
split_tasks_lock = threading.Lock()


@app.route('/api/split/upload', methods=['POST'])
def split_upload():
    """
    上传字幕和配音文件进行拆分

    Request:
        - srt: SRT字幕文件
        - audio: 配音文件（音频/视频）

    Response:
        - task_id: 任务ID
    """
    try:
        logger.info("=" * 60)
        logger.info("收到新的音频拆分任务")

        # 检查必需文件
        if 'srt' not in request.files or 'audio' not in request.files:
            logger.error("❌ 缺少必需文件")
            return jsonify({'error': '缺少必需文件'}), 400

        srt = request.files['srt']
        audio = request.files['audio']

        logger.info(f"📝 字幕文件: {srt.filename}")
        logger.info(f"🎤 配音文件: {audio.filename}")

        # 检查文件名
        if srt.filename == '' or audio.filename == '':
            logger.error("❌ 文件名为空")
            return jsonify({'error': '文件名为空'}), 400

        # 验证文件类型
        if not srt.filename.lower().endswith('.srt'):
            logger.error(f"❌ 字幕文件格式错误: {srt.filename}")
            return jsonify({'error': '字幕文件必须是SRT格式'}), 400

        # 创建任务ID
        task_id = str(uuid.uuid4())
        task_folder = os.path.join(TASKS_FOLDER, 'split_' + task_id)
        os.makedirs(task_folder, exist_ok=True)

        logger.info(f"✅ 创建任务ID: {task_id}")

        # 保存文件
        srt_path = os.path.join(task_folder, 'subtitles.srt')
        audio_path = os.path.join(task_folder, 'audio')

        srt.save(srt_path)
        audio.save(audio_path)

        logger.info(f"✅ 文件保存完成")
        logger.info(f"   - 字幕大小: {os.path.getsize(srt_path) / 1024:.2f} KB")
        logger.info(f"   - 配音大小: {os.path.getsize(audio_path) / 1024 / 1024:.2f} MB")

        # 初始化任务状态
        with split_tasks_lock:
            split_tasks[task_id] = {
                'status': 'uploaded',
                'progress': 0,
                'message': '文件上传完成',
                'srt_path': srt_path,
                'audio_path': audio_path,
                'output_folder': os.path.join(DOWNLOAD_FOLDER, 'split_' + task_id),
                'segments': [],
                'error': None,
                'created_at': datetime.now().isoformat()
            }

        logger.info(f"✅ 任务创建成功: {task_id}")
        logger.info("=" * 60)

        return jsonify({
            'task_id': task_id,
            'message': '文件上传成功，正在拆分'
        }), 200

    except Exception as e:
        logger.error(f"❌ 音频拆分上传失败: {str(e)}")
        logger.error("=" * 60)
        return jsonify({'error': f'上传失败: {str(e)}'}), 500


@app.route('/api/split/process/<task_id>', methods=['POST'])
def split_process(task_id):
    """
    开始拆分音频

    Args:
        task_id: 任务ID

    Response:
        - status: 状态
        - message: 消息
    """
    try:
        with split_tasks_lock:
            if task_id not in split_tasks:
                return jsonify({'error': '任务不存在'}), 404

            task = split_tasks[task_id]

            if task['status'] == 'processing':
                return jsonify({'message': '任务正在处理中'}), 200

            if task['status'] == 'completed':
                return jsonify({'message': '任务已完成'}), 200

        # 在新线程中处理拆分
        thread = threading.Thread(
            target=process_split_thread,
            args=(task_id,)
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            'status': 'processing',
            'message': '开始拆分音频'
        }), 200

    except Exception as e:
        return jsonify({'error': f'处理失败: {str(e)}'}), 500


def process_split_thread(task_id):
    """音频拆分线程"""
    try:
        from moviepy import AudioFileClip
        import pysrt
        import chardet
        import zipfile

        logger.info("=" * 60)
        logger.info(f"✂️  开始拆分音频任务: {task_id}")

        with split_tasks_lock:
            task = split_tasks[task_id]
            task['status'] = 'processing'
            task['message'] = '正在加载文件...'

        # 检测字幕编码
        logger.info("🔍 检测字幕编码")
        with open(task['srt_path'], 'rb') as f:
            raw_data = f.read()
            result = chardet.detect(raw_data)
            encoding = result['encoding'] or 'utf-8'
            logger.info(f"   编码: {encoding}")

        # 加载字幕
        logger.info("📝 加载字幕文件")
        subs = pysrt.open(task['srt_path'], encoding=encoding)
        logger.info(f"   字幕条数: {len(subs)}")

        # 创建本地输出目录（使用时间戳命名）
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        local_output_dir = os.path.join(OUTPUT_FOLDER, f'split_{timestamp}')
        os.makedirs(local_output_dir, exist_ok=True)

        logger.info(f"📂 创建本地输出目录: {local_output_dir}")

        with split_tasks_lock:
            split_tasks[task_id]['local_output_dir'] = local_output_dir

        # 加载音频
        with split_tasks_lock:
            task['progress'] = 10
            task['message'] = '正在加载音频文件...'

        logger.info("🎵 加载音频文件")
        audio_clip = AudioFileClip(task['audio_path'])
        audio_duration = audio_clip.duration
        logger.info(f"   音频时长: {audio_duration:.2f} 秒")

        # 拆分音频 - 使用 ffmpeg 直接处理更稳定
        logger.info("✂️  开始拆分音频...")
        segments = []
        total_subs = len(subs)
        import subprocess

        for i, sub in enumerate(subs):
            start_time = sub.start.ordinal / 1000.0  # 转换为秒
            end_time = sub.end.ordinal / 1000.0
            duration = end_time - start_time

            # 更新进度
            with split_tasks_lock:
                task['progress'] = int(10 + (i / total_subs) * 80)
                task['message'] = f'正在拆分片段 {i+1}/{total_subs}...'

            # 使用 ffmpeg 直接提取音频片段
            segment_filename = f"segment_{i+1:03d}.mp3"
            segment_path = os.path.join(local_output_dir, segment_filename)

            # ffmpeg 命令：从指定时间点提取指定时长的音频
            cmd = [
                'ffmpeg',
                '-i', task['audio_path'],  # 输入文件
                '-ss', str(start_time),     # 开始时间
                '-t', str(duration),        # 持续时间
                '-vn',                      # 不处理视频
                '-acodec', 'libmp3lame',    # 使用 mp3 编码
                '-y',                       # 覆盖输出文件
                segment_path
            ]

            # 执行 ffmpeg 命令，隐藏输出
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"   [{i+1:03d}] ffmpeg 错误: {result.stderr}")
                raise Exception(f"音频拆分失败: {result.stderr}")

            logger.info(f"   [{i+1:03d}/{total_subs}] {sub.start} -> {sub.end} ({duration:.2f}s)")

            # 保存片段信息
            segments.append({
                'index': i + 1,
                'start': str(sub.start),
                'end': str(sub.end),
                'duration': round(duration, 2),
                'text': sub.text,
                'filename': segment_filename
            })

        # 关闭音频clip
        audio_clip.close()

        logger.info(f"✅ 成功拆分为 {len(segments)} 个片段")

        # 保存片段信息到JSON文件
        import json
        info_path = os.path.join(local_output_dir, 'segments_info.json')
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(segments, f, ensure_ascii=False, indent=2)
        logger.info(f"📄 片段信息已保存: segments_info.json")

        # 创建ZIP文件到本地输出目录
        with split_tasks_lock:
            task['progress'] = 90
            task['message'] = '正在创建ZIP文件...'

        logger.info("📦 创建ZIP压缩包")
        zip_path = os.path.join(local_output_dir, 'segments.zip')
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for segment in segments:
                segment_path = os.path.join(local_output_dir, segment['filename'])
                zipf.write(segment_path, segment['filename'])

        logger.info(f"📦 ZIP文件已创建: segments.zip ({len(segments)} 个文件)")
        logger.info(f"💾 文件保存到: {local_output_dir}")

        # 更新为完成状态
        with split_tasks_lock:
            split_tasks[task_id]['status'] = 'completed'
            split_tasks[task_id]['progress'] = 100
            split_tasks[task_id]['message'] = f'拆分完成！文件已保存到: {local_output_dir}'
            split_tasks[task_id]['segments'] = segments

        logger.info(f"✅ 任务 {task_id} 拆分成功")
        logger.info("=" * 60)

    except Exception as e:
        import traceback
        traceback.print_exc()

        logger.error(f"❌ 任务 {task_id} 拆分失败: {str(e)}")
        logger.error("=" * 60)

        with split_tasks_lock:
            split_tasks[task_id]['status'] = 'failed'
            split_tasks[task_id]['error'] = str(e)
            split_tasks[task_id]['message'] = f'拆分失败: {str(e)}'
            split_tasks[task_id]['message'] = '拆分完成'
            split_tasks[task_id]['segments'] = segments

    except Exception as e:
        import traceback
        traceback.print_exc()

        with split_tasks_lock:
            split_tasks[task_id]['status'] = 'failed'
            split_tasks[task_id]['error'] = str(e)
            split_tasks[task_id]['message'] = f'拆分失败: {str(e)}'


@app.route('/api/split/status/<task_id>', methods=['GET'])
def get_split_status(task_id):
    """
    获取拆分任务状态

    Args:
        task_id: 任务ID

    Response:
        - status: 状态 (uploaded, processing, completed, failed)
        - progress: 进度 (0-100)
        - message: 消息
        - segments: 片段列表（完成后）
        - error: 错误信息（如果有）
    """
    try:
        with split_tasks_lock:
            if task_id not in split_tasks:
                return jsonify({'error': '任务不存在'}), 404

            task = split_tasks[task_id]

        return jsonify({
            'status': task['status'],
            'progress': task['progress'],
            'message': task['message'],
            'segments': task.get('segments', []),
            'error': task.get('error')
        }), 200

    except Exception as e:
        return jsonify({'error': f'获取状态失败: {str(e)}'}), 500


@app.route('/api/split/download/<task_id>/<file_type>', methods=['GET'])
def download_split_result(task_id, file_type):
    """
    下载拆分结果

    Args:
        task_id: 任务ID
        file_type: 文件类型 (zip 或 json)

    Response:
        - 文件
    """
    try:
        with split_tasks_lock:
            if task_id not in split_tasks:
                return jsonify({'error': '任务不存在'}), 404

            task = split_tasks[task_id]

            if task['status'] != 'completed':
                return jsonify({'error': '任务尚未完成'}), 400

        if file_type == 'zip':
            # 下载ZIP文件
            zip_path = os.path.join(task['output_folder'], 'segments.zip')
            if not os.path.exists(zip_path):
                return jsonify({'error': '文件不存在'}), 404

            return send_file(
                zip_path,
                as_attachment=True,
                download_name=f'audio_segments_{task_id}.zip',
                mimetype='application/zip'
            )

        elif file_type == 'json':
            # 下载JSON信息
            import json
            json_data = json.dumps(task['segments'], ensure_ascii=False, indent=2)

            from flask import Response
            return Response(
                json_data,
                mimetype='application/json',
                headers={'Content-Disposition': f'attachment;filename=segments_info_{task_id}.json'}
            )

        else:
            return jsonify({'error': '无效的文件类型'}), 400

    except Exception as e:
        return jsonify({'error': f'下载失败: {str(e)}'}), 500


@app.route('/api/split/task/<task_id>', methods=['DELETE'])
def cancel_split_task(task_id):
    """
    取消拆分任务

    Args:
        task_id: 任务ID

    Response:
        - message: 消息
    """
    try:
        with split_tasks_lock:
            if task_id not in split_tasks:
                return jsonify({'error': '任务不存在'}), 404

            # 删除任务
            del split_tasks[task_id]

        # 清理文件
        task_folder = os.path.join(TASKS_FOLDER, 'split_' + task_id)
        download_folder = os.path.join(DOWNLOAD_FOLDER, 'split_' + task_id)

        if os.path.exists(task_folder):
            shutil.rmtree(task_folder)

        if os.path.exists(download_folder):
            shutil.rmtree(download_folder)

        return jsonify({'message': '任务已取消'}), 200

    except Exception as e:
        return jsonify({'error': f'取消失败: {str(e)}'}), 500


@app.errorhandler(413)
def request_entity_too_large(error):
    """处理文件过大错误"""
    return jsonify({'error': '文件过大，最大支持500MB'}), 413


# ==================== 新增：字幕分析和增强剪辑API ====================

@app.route('/api/analyze-subtitles', methods=['POST'])
def analyze_subtitles():
    """
    分析字幕时间差异（新增）

    Request:
        - original_srt: 原字幕文件
        - new_srt: 新字幕文件

    Response:
        - analysis: 详细分析结果
        - visualization: 可视化数据
        - recommendations: 剪辑参数推荐
    """
    try:
        logger.info("=" * 60)
        logger.info("收到字幕分析请求")

        # 检查文件
        if 'original_srt' not in request.files or 'new_srt' not in request.files:
            return jsonify({'error': '缺少字幕文件'}), 400

        original_srt = request.files['original_srt']
        new_srt = request.files['new_srt']

        # 保存到临时文件
        temp_dir = tempfile.mkdtemp(prefix="subtitle_analysis_")

        original_srt_path = os.path.join(temp_dir, 'original.srt')
        new_srt_path = os.path.join(temp_dir, 'new.srt')

        original_srt.save(original_srt_path)
        new_srt.save(new_srt_path)

        logger.info(f"原字幕: {original_srt.filename}")
        logger.info(f"新字幕: {new_srt.filename}")

        # 分析字幕
        analyzer = SubtitleAnalyzer(original_srt_path, new_srt_path)
        analyzer.load_subtitles()

        analysis = analyzer.compare_subtitles()
        visualization = analyzer.generate_visualization_data()
        recommendations = analyzer.recommend_clip_parameters()

        # 清理临时文件
        shutil.rmtree(temp_dir)

        logger.info("✅ 字幕分析完成")

        return jsonify({
            'analysis': analysis,
            'visualization': visualization,
            'recommendations': recommendations
        }), 200

    except Exception as e:
        logger.error(f"字幕分析失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'分析失败: {str(e)}'}), 500


@app.route('/api/enhanced-clip', methods=['POST'])
def enhanced_clip_video():
    """
    增强的视频剪辑（新增）

    Request:
        - video: 原视频文件
        - original_srt: 原字幕文件
        - new_srt: 新字幕文件
        - merge_gap: 合并间隙阈值（可选，默认2.0）
        - use_precise: 是否使用精确模式（可选，默认false）

    Response:
        - task_id: 任务ID
    """
    try:
        logger.info("=" * 60)
        logger.info("收到增强视频剪辑请求")

        # 检查必需文件
        if 'video' not in request.files or 'original_srt' not in request.files or 'new_srt' not in request.files:
            return jsonify({'error': '缺少必需文件'}), 400

        video = request.files['video']
        original_srt = request.files['original_srt']
        new_srt = request.files['new_srt']

        # 获取参数
        merge_gap = float(request.form.get('merge_gap', 2.0))
        use_precise = request.form.get('use_precise', 'false').lower() == 'true'

        logger.info(f"原视频: {video.filename}")
        logger.info(f"原字幕: {original_srt.filename}")
        logger.info(f"新字幕: {new_srt.filename}")
        logger.info(f"合并间隙: {merge_gap}秒")
        logger.info(f"精确模式: {use_precise}")

        # 创建任务ID
        task_id = str(uuid.uuid4())
        task_folder = os.path.join(TASKS_FOLDER, f'enhanced_clip_{task_id}')
        os.makedirs(task_folder, exist_ok=True)

        # 保存文件
        video_path = os.path.join(task_folder, 'video.mp4')
        original_srt_path = os.path.join(task_folder, 'original.srt')
        new_srt_path = os.path.join(task_folder, 'new.srt')

        video.save(video_path)
        original_srt.save(original_srt_path)
        new_srt.save(new_srt_path)

        # 创建输出目录
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = os.path.join(OUTPUT_FOLDER, f'enhanced_clip_{timestamp}')
        os.makedirs(output_dir, exist_ok=True)

        # 初始化任务
        with tasks_lock:
            tasks[task_id] = {
                'type': 'enhanced_clip',
                'status': 'uploaded',
                'progress': 0,
                'message': '文件上传完成',
                'video_path': video_path,
                'original_srt_path': original_srt_path,
                'new_srt_path': new_srt_path,
                'merge_gap': merge_gap,
                'use_precise': use_precise,
                'output_folder': output_dir,
                'error': None,
                'created_at': datetime.now().isoformat()
            }

        logger.info(f"✅ 任务创建成功: {task_id}")

        return jsonify({
            'task_id': task_id,
            'message': '文件上传成功'
        }), 200

    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        return jsonify({'error': f'创建任务失败: {str(e)}'}), 500


@app.route('/api/process-enhanced/<task_id>', methods=['POST'])
def process_enhanced_clip(task_id):
    """
    处理增强剪辑任务（新增）

    Args:
        task_id: 任务ID

    Response:
        - status: 状态
        - message: 消息
    """
    try:
        with tasks_lock:
            if task_id not in tasks:
                return jsonify({'error': '任务不存在'}), 404

            task = tasks[task_id]
            if task.get('type') != 'enhanced_clip':
                return jsonify({'error': '任务类型不匹配'}), 400

        # 在新线程中处理
        thread = threading.Thread(
            target=process_enhanced_clip_thread,
            args=(task_id,)
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            'status': 'processing',
            'message': '开始处理视频'
        }), 200

    except Exception as e:
        return jsonify({'error': f'处理失败: {str(e)}'}), 500


def process_enhanced_clip_thread(task_id):
    """增强剪辑处理线程"""
    try:
        logger.info("=" * 60)
        logger.info(f"🎬 开始增强剪辑任务: {task_id}")

        with tasks_lock:
            task = tasks[task_id]
            task['status'] = 'processing'
            task['message'] = '正在初始化剪辑器...'

        logger.info("创建增强剪辑器...")

        clipper = EnhancedVideoClipper(
            video_path=tasks[task_id]['video_path'],
            original_srt_path=tasks[task_id]['original_srt_path'],
            new_srt_path=tasks[task_id]['new_srt_path'],
            output_dir=tasks[task_id]['output_folder'],
            merge_gap=tasks[task_id]['merge_gap'],
            use_precise_seek=tasks[task_id]['use_precise']
        )

        with tasks_lock:
            tasks[task_id]['progress'] = 20
            tasks[task_id]['message'] = '正在分析字幕...'

        logger.info("处理视频...")

        result = clipper.process()

        logger.info(f"✅ 增强剪辑完成")

        # 更新任务状态
        with tasks_lock:
            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['progress'] = 100
            tasks[task_id]['message'] = '处理完成'

            if result.get('success'):
                tasks[task_id]['clipped_video'] = result.get('clipped_video')
                tasks[task_id]['segment_count'] = result.get('segment_count')
            else:
                tasks[task_id]['error'] = result.get('error', '未知错误')

        logger.info(f"✅ 任务 {task_id} 处理成功")
        logger.info("=" * 60)

    except Exception as e:
        import traceback
        traceback.print_exc()

        logger.error(f"❌ 任务 {task_id} 处理失败: {str(e)}")

        with tasks_lock:
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = str(e)
            tasks[task_id]['message'] = f'处理失败: {str(e)}'
        logger.error("=" * 60)


@app.route('/api/batch-clip', methods=['POST'])
def batch_clip_videos():
    """
    批量视频剪辑（新增）

    Request:
        - tasks: 任务列表JSON，每个任务包含 video_path, original_srt_path, new_srt_path
        - merge_gap: 合并间隙阈值（可选）
        - use_precise: 是否精确模式（可选）

    Response:
        - batch_id: 批处理任务ID
    """
    try:
        logger.info("=" * 60)
        logger.info("收到批量剪辑请求")

        # 获取参数
        tasks_data = request.json.get('tasks', [])
        merge_gap = float(request.json.get('merge_gap', 2.0))
        use_precise = request.json.get('use_precise', False)

        if not tasks_data:
            return jsonify({'error': '任务列表为空'}), 400

        logger.info(f"任务数量: {len(tasks_data)}")
        logger.info(f"合并间隙: {merge_gap}秒")

        # 创建批量处理ID
        batch_id = str(uuid.uuid4())

        # 初始化批量任务
        with tasks_lock:
            tasks[batch_id] = {
                'type': 'batch_clip',
                'status': 'processing',
                'progress': 0,
                'message': f'正在处理 {len(tasks_data)} 个视频',
                'total': len(tasks_data),
                'completed': 0,
                'failed': 0,
                'tasks': tasks_data,
                'merge_gap': merge_gap,
                'use_precise': use_precise,
                'results': [],
                'error': None,
                'created_at': datetime.now().isoformat()
            }

        # 在新线程中处理
        thread = threading.Thread(
            target=process_batch_clip_thread,
            args=(batch_id,)
        )
        thread.daemon = True
        thread.start()

        logger.info(f"✅ 批量任务创建成功: {batch_id}")

        return jsonify({
            'batch_id': batch_id,
            'message': f'开始处理 {len(tasks_data)} 个视频'
        }), 200

    except Exception as e:
        logger.error(f"创建批量任务失败: {e}")
        return jsonify({'error': f'创建失败: {str(e)}'}), 500


def process_batch_clip_thread(batch_id):
    """批量剪辑处理线程"""
    try:
        logger.info("=" * 60)
        logger.info(f"🎬 开始批量剪辑任务: {batch_id}")

        with tasks_lock:
            task = tasks[batch_id]
            tasks_data = task['tasks']
            merge_gap = task['merge_gap']
            use_precise = task['use_precise']

        # 创建批量处理器
        batch_processor = BatchVideoProcessor(
            output_dir=os.path.join(OUTPUT_FOLDER, f'batch_{batch_id}')
        )

        # 处理每个任务
        for i, task_data in enumerate(tasks_data):
            with tasks_lock:
                tasks[batch_id]['message'] = f'处理第 {i+1}/{len(tasks_data)} 个视频'
                tasks[batch_id]['progress'] = int((i / len(tasks_data)) * 100)

            logger.info(f"[{i+1}/{len(tasks_data)}] 处理: {task_data.get('video_path')}")

            result = batch_processor.process_single(
                video_path=task_data['video_path'],
                original_srt_path=task_data['original_srt_path'],
                new_srt_path=task_data['new_srt_path'],
                merge_gap=merge_gap,
                use_precise_seek=use_precise
            )

            with tasks_lock:
                tasks[batch_id]['results'].append(result)
                if result.get('success'):
                    tasks[batch_id]['completed'] += 1
                else:
                    tasks[batch_id]['failed'] += 1

        # 生成报告
        report = batch_processor.generate_report(f'batch_{batch_id}_report.json')

        # 更新状态
        with tasks_lock:
            tasks[batch_id]['status'] = 'completed'
            tasks[batch_id]['progress'] = 100
            tasks[batch_id]['message'] = '批量处理完成'
            tasks[batch_id]['report'] = report

        logger.info(f"✅ 批量任务 {batch_id} 完成")
        logger.info(f"   总计: {report['total']}")
        logger.info(f"   成功: {report['successful']}")
        logger.info(f"   失败: {report['failed']}")
        logger.info("=" * 60)

    except Exception as e:
        import traceback
        traceback.print_exc()

        logger.error(f"❌ 批量任务 {batch_id} 失败: {str(e)}")

        with tasks_lock:
            tasks[batch_id]['status'] = 'failed'
            tasks[batch_id]['error'] = str(e)
            tasks[batch_id]['message'] = f'批量处理失败: {str(e)}'
        logger.error("=" * 60)


# ==================== 紧凑剪辑API（累积偏移算法）====================

@app.route('/api/compact-clip', methods=['POST'])
def compact_clip_video():
    """
    紧凑视频剪辑（累积偏移算法）

    相比普通剪辑，紧凑剪辑会：
    1. 对比原字幕和新字幕的时间差
    2. 累积计算偏移量
    3. 减掉不必要的时间，生成更紧凑的视频

    Request:
        - video: 原视频文件
        - original_srt: 原字幕文件
        - new_srt: 新字幕文件
        - use_precise: 是否使用精确模式（可选，默认false）

    Response:
        - task_id: 任务ID
    """
    try:
        logger.info("=" * 60)
        logger.info("收到紧凑剪辑请求（累积偏移算法）")

        # 检查必需文件
        if 'video' not in request.files or 'original_srt' not in request.files or 'new_srt' not in request.files:
            return jsonify({'error': '缺少必需文件'}), 400

        video = request.files['video']
        original_srt = request.files['original_srt']
        new_srt = request.files['new_srt']

        # 获取参数
        use_precise = request.form.get('use_precise', 'false').lower() == 'true'

        logger.info(f"原视频: {video.filename}")
        logger.info(f"原字幕: {original_srt.filename}")
        logger.info(f"新字幕: {new_srt.filename}")
        logger.info(f"精确模式: {use_precise}")

        # 创建任务ID
        task_id = str(uuid.uuid4())
        task_folder = os.path.join(TASKS_FOLDER, f'compact_clip_{task_id}')
        os.makedirs(task_folder, exist_ok=True)

        # 保存文件
        video_path = os.path.join(task_folder, 'video.mp4')
        original_srt_path = os.path.join(task_folder, 'original.srt')
        new_srt_path = os.path.join(task_folder, 'new.srt')

        video.save(video_path)
        original_srt.save(original_srt_path)
        new_srt.save(new_srt_path)

        # 创建输出目录
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = os.path.join(OUTPUT_FOLDER, f'compact_clip_{timestamp}')
        os.makedirs(output_dir, exist_ok=True)

        # 初始化任务
        with tasks_lock:
            tasks[task_id] = {
                'type': 'compact_clip',
                'status': 'uploaded',
                'progress': 0,
                'message': '文件上传完成',
                'video_path': video_path,
                'original_srt_path': original_srt_path,
                'new_srt_path': new_srt_path,
                'use_precise': use_precise,
                'output_folder': output_dir,
                'error': None,
                'created_at': datetime.now().isoformat()
            }

        logger.info(f"✅ 任务创建成功: {task_id}")

        return jsonify({
            'task_id': task_id,
            'message': '文件上传成功，将使用累积偏移算法生成紧凑视频'
        }), 200

    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        return jsonify({'error': f'创建任务失败: {str(e)}'}), 500


@app.route('/api/process-compact/<task_id>', methods=['POST'])
def process_compact_clip(task_id):
    """
    处理紧凑剪辑任务

    Args:
        task_id: 任务ID

    Response:
        - status: 状态
        - message: 消息
    """
    try:
        with tasks_lock:
            if task_id not in tasks:
                return jsonify({'error': '任务不存在'}), 404

            task = tasks[task_id]
            if task.get('type') != 'compact_clip':
                return jsonify({'error': '任务类型不匹配'}), 400

        # 在新线程中处理
        thread = threading.Thread(
            target=process_compact_clip_thread,
            args=(task_id,)
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            'status': 'processing',
            'message': '开始紧凑剪辑处理'
        }), 200

    except Exception as e:
        return jsonify({'error': f'处理失败: {str(e)}'}), 500


def process_compact_clip_thread(task_id):
    """紧凑剪辑处理线程"""
    try:
        logger.info("=" * 60)
        logger.info(f"🎬 开始紧凑剪辑任务: {task_id}")

        with tasks_lock:
            task = tasks[task_id]
            task['status'] = 'processing'
            task['message'] = '正在初始化紧凑剪辑器...'

        logger.info("创建紧凑剪辑器（累积偏移算法）...")

        clipper = CompactVideoClipper(
            video_path=tasks[task_id]['video_path'],
            original_srt_path=tasks[task_id]['original_srt_path'],
            new_srt_path=tasks[task_id]['new_srt_path'],
            output_dir=tasks[task_id]['output_folder'],
            use_precise_seek=tasks[task_id]['use_precise']
        )

        with tasks_lock:
            tasks[task_id]['progress'] = 20
            tasks[task_id]['message'] = '正在分析字幕并计算累积偏移...'

        logger.info("处理视频...")

        result = clipper.process()

        logger.info(f"✅ 紧凑剪辑完成")

        # 更新任务状态
        with tasks_lock:
            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['progress'] = 100
            tasks[task_id]['message'] = '处理完成'

            if result.get('success'):
                tasks[task_id]['compact_video'] = result.get('compact_video')
                tasks[task_id]['stats'] = result.get('stats')
                tasks[task_id]['segment_count'] = result.get('segment_count')

                # 统计信息
                stats = result.get('stats', {})
                logger.info(f"   节省时间: {stats.get('time_saved', 0):.2f}秒")
                logger.info(f"   紧凑比例: {(1 - stats.get('new_total_duration', 0) / max(stats.get('original_total_duration', 1), 1)) * 100:.1f}%")
            else:
                tasks[task_id]['error'] = result.get('error', '未知错误')

        logger.info(f"✅ 任务 {task_id} 处理成功")
        logger.info("=" * 60)

    except Exception as e:
        import traceback
        traceback.print_exc()

        logger.error(f"❌ 任务 {task_id} 处理失败: {str(e)}")

        with tasks_lock:
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = str(e)
            tasks[task_id]['message'] = f'处理失败: {str(e)}'
        logger.error("=" * 60)


# ==================== 时间轴对齐API ====================

@app.route('/api/timeline-align', methods=['POST'])
def timeline_align_video():
    """
    时间轴对齐剪辑（以新字幕为基准）

    通过对比原字幕和新字幕，剪辑原视频，
    让新视频与新字幕完美同步，保留字幕间的自然间隙

    Request:
        - video: 原视频文件
        - original_srt: 原字幕文件
        - new_srt: 新字幕文件
        - use_precise: 是否使用精确模式（可选，默认false）

    Response:
        - task_id: 任务ID
    """
    try:
        logger.info("=" * 60)
        logger.info("收到时间轴对齐请求")

        # 检查必需文件
        if 'video' not in request.files or 'original_srt' not in request.files or 'new_srt' not in request.files:
            return jsonify({'error': '缺少必需文件'}), 400

        video = request.files['video']
        original_srt = request.files['original_srt']
        new_srt = request.files['new_srt']

        # 获取参数
        use_precise = request.form.get('use_precise', 'false').lower() == 'true'

        logger.info(f"原视频: {video.filename}")
        logger.info(f"原字幕: {original_srt.filename}")
        logger.info(f"新字幕: {new_srt.filename}")
        logger.info(f"精确模式: {use_precise}")

        # 创建任务ID
        task_id = str(uuid.uuid4())
        task_folder = os.path.join(TASKS_FOLDER, f'align_{task_id}')
        os.makedirs(task_folder, exist_ok=True)

        # 保存文件
        video_path = os.path.join(task_folder, 'video.mp4')
        original_srt_path = os.path.join(task_folder, 'original.srt')
        new_srt_path = os.path.join(task_folder, 'new.srt')

        video.save(video_path)
        original_srt.save(original_srt_path)
        new_srt.save(new_srt_path)

        # 创建输出目录
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = os.path.join(OUTPUT_FOLDER, f'timeline_align_{timestamp}')
        os.makedirs(output_dir, exist_ok=True)

        # 初始化任务
        with tasks_lock:
            tasks[task_id] = {
                'type': 'timeline_align',
                'status': 'uploaded',
                'progress': 0,
                'message': '文件上传完成',
                'video_path': video_path,
                'original_srt_path': original_srt_path,
                'new_srt_path': new_srt_path,
                'use_precise': use_precise,
                'output_folder': output_dir,
                'error': None,
                'created_at': datetime.now().isoformat()
            }

        logger.info(f"✅ 任务创建成功: {task_id}")

        return jsonify({
            'task_id': task_id,
            'message': '文件上传成功，将以新字幕时间轴为基准进行对齐'
        }), 200

    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        return jsonify({'error': f'创建任务失败: {str(e)}'}), 500


@app.route('/api/process-align/<task_id>', methods=['POST'])
def process_timeline_align(task_id):
    """
    处理时间轴对齐任务

    Args:
        task_id: 任务ID

    Response:
        - status: 状态
        - message: 消息
    """
    try:
        with tasks_lock:
            if task_id not in tasks:
                return jsonify({'error': '任务不存在'}), 404

            task = tasks[task_id]
            if task.get('type') != 'timeline_align':
                return jsonify({'error': '任务类型不匹配'}), 400

        # 在新线程中处理
        thread = threading.Thread(
            target=process_timeline_align_thread,
            args=(task_id,)
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            'status': 'processing',
            'message': '开始时间轴对齐处理'
        }), 200

    except Exception as e:
        return jsonify({'error': f'处理失败: {str(e)}'}), 500


def process_timeline_align_thread(task_id):
    """时间轴对齐处理线程"""
    try:
        logger.info("=" * 60)
        logger.info(f"🎬 开始时间轴对齐任务: {task_id}")

        with tasks_lock:
            task = tasks[task_id]
            task['status'] = 'processing'
            task['message'] = '正在初始化时间轴对齐器...'

        logger.info("创建时间轴对齐器（以新字幕为基准）...")

        aligner = TimelineAligner(
            video_path=tasks[task_id]['video_path'],
            original_srt_path=tasks[task_id]['original_srt_path'],
            new_srt_path=tasks[task_id]['new_srt_path'],
            output_dir=tasks[task_id]['output_folder'],
            use_precise_seek=tasks[task_id]['use_precise']
        )

        with tasks_lock:
            tasks[task_id]['progress'] = 20
            tasks[task_id]['message'] = '正在对比字幕并提取对齐片段...'

        logger.info("处理视频...")

        result = aligner.process()

        logger.info(f"✅ 时间轴对齐完成")

        # 更新任务状态
        with tasks_lock:
            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['progress'] = 100
            tasks[task_id]['message'] = '处理完成'

            if result.get('success'):
                tasks[task_id]['aligned_video'] = result.get('aligned_video')
                tasks[task_id]['stats'] = result.get('stats')
                tasks[task_id]['segment_count'] = result.get('segment_count')

                # 统计信息
                stats = result.get('stats', {})
                logger.info(f"   匹配率: {stats.get('match_rate', 'N/A')}")
                logger.info(f"   新字幕时长: {stats.get('new_subtitle_total_duration', 0):.2f}秒")
            else:
                tasks[task_id]['error'] = result.get('error', '未知错误')

        logger.info(f"✅ 任务 {task_id} 处理成功")
        logger.info("=" * 60)

    except Exception as e:
        import traceback
        traceback.print_exc()

        logger.error(f"❌ 任务 {task_id} 处理失败: {str(e)}")

        with tasks_lock:
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = str(e)
            tasks[task_id]['message'] = f'处理失败: {str(e)}'
        logger.error("=" * 60)


# ==================== 迭代调整剪辑 API ====================

@app.route('/api/iterative-adjust', methods=['POST'])
def iterative_adjust_upload():
    """
    迭代调整剪辑 - 上传并处理（使用时间轴重映射算法）

    Request:
        - video: 原视频文件
        - original_srt: 原字幕文件
        - new_srt: 新字幕文件

    Response:
        - task_id: 任务ID
    """
    try:
        logger.info("=" * 60)
        logger.info("收到迭代调整剪辑任务")

        # 检查文件
        if 'video' not in request.files:
            return jsonify({'error': '缺少视频文件'}), 400
        if 'original_srt' not in request.files:
            return jsonify({'error': '缺少原字幕文件'}), 400
        if 'new_srt' not in request.files:
            return jsonify({'error': '缺少新字幕文件'}), 400

        video = request.files['video']
        original_srt = request.files['original_srt']
        new_srt = request.files['new_srt']

        if video.filename == '' or original_srt.filename == '' or new_srt.filename == '':
            return jsonify({'error': '文件名为空'}), 400

        # 生成任务ID
        task_id = str(uuid.uuid4())

        # 创建任务目录
        task_dir = os.path.join(TASKS_FOLDER, task_id)
        os.makedirs(task_dir, exist_ok=True)

        # 保存文件
        video_path = os.path.join(task_dir, video.filename)
        original_srt_path = os.path.join(task_dir, original_srt.filename)
        new_srt_path = os.path.join(task_dir, new_srt.filename)

        video.save(video_path)
        original_srt.save(original_srt_path)
        new_srt.save(new_srt_path)

        logger.info(f"任务ID: {task_id}")
        logger.info(f"视频: {video.filename} ({os.path.getsize(video_path) / 1024 / 1024:.2f} MB)")
        logger.info(f"原字幕: {original_srt.filename}")
        logger.info(f"新字幕: {new_srt.filename}")

        # 初始化任务
        with tasks_lock:
            tasks[task_id] = {
                'type': 'iterative_adjust',
                'status': 'processing',
                'progress': 0,
                'message': '正在处理',
                'created_at': datetime.now().isoformat(),
                'video_path': video_path,
                'original_srt_path': original_srt_path,
                'new_srt_path': new_srt_path,
                'adjusted_video': None,
                'stats': None,
                'error': None
            }

        # 在后台线程中处理
        thread = threading.Thread(
            target=process_iterative_adjust_task,
            args=(task_id, video_path, original_srt_path, new_srt_path, 0.5)  # 传递默认阈值
        )
        thread.daemon = True
        thread.start()

        logger.info("=" * 60)

        return jsonify({
            'task_id': task_id,
            'status': 'processing',
            'message': '任务已创建，正在处理'
        })

    except Exception as e:
        logger.error(f"创建任务失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def process_iterative_adjust_task(task_id, video_path, original_srt_path, new_srt_path, threshold=0.3):
    """处理迭代调整剪辑任务（后台线程）- 使用时间轴重映射算法"""
    try:
        logger.info(f"🎬 开始处理任务 {task_id}")

        # 创建输出目录
        output_dir = os.path.join(TASKS_FOLDER, task_id, 'output')
        os.makedirs(output_dir, exist_ok=True)

        # 创建剪辑器（使用时间轴重映射算法）
        clipper = TimelineRemapClipper(
            video_path=video_path,
            original_srt_path=original_srt_path,
            new_srt_path=new_srt_path,
            output_dir=output_dir,
            threshold=threshold  # 用于字幕匹配的相似度阈值
        )

        # 处理
        result = clipper.process()

        # 更新任务状态
        with tasks_lock:
            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['progress'] = 100
            tasks[task_id]['message'] = '处理完成'

            if result.get('success'):
                video_path = result.get('remapped_video')
                tasks[task_id]['adjusted_video'] = video_path
                tasks[task_id]['stats'] = result.get('stats')

                # 额外保存到全局output目录
                global_output_dir = os.path.join(os.path.dirname(__file__), '../../output')
                os.makedirs(global_output_dir, exist_ok=True)
                global_video_path = os.path.join(global_output_dir, f'adjusted_{task_id[:8]}_video.mp4')
                shutil.copy2(video_path, global_video_path)
                logger.info(f"   视频已保存到全局目录: {global_video_path}")

                # 统计信息
                stats = result.get('stats', {})
                logger.info(f"   原视频时长: {result.get('original_duration', 0):.2f}秒")
                logger.info(f"   重映射后时长: {result.get('final_duration', 0):.2f}秒")
                logger.info(f"   时长变化: {result.get('duration_change', 0):+.2f}秒")
                logger.info(f"   匹配率: {stats.get('match_rate', 'N/A')}")
                logger.info(f"   新字幕总时长: {stats.get('new_subtitle_total_duration', 0):.2f}秒")
                logger.info(f"   任务目录视频: {video_path}")
            else:
                tasks[task_id]['error'] = result.get('error', '未知错误')

        logger.info(f"✅ 任务 {task_id} 处理成功")
        logger.info("=" * 60)

    except Exception as e:
        import traceback
        traceback.print_exc()

        logger.error(f"❌ 任务 {task_id} 处理失败: {str(e)}")

        with tasks_lock:
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = str(e)
            tasks[task_id]['message'] = f'处理失败: {str(e)}'
        logger.error("=" * 60)


@app.route('/api/iterative-adjust/status/<task_id>', methods=['GET'])
def iterative_adjust_status(task_id):
    """
    查询迭代调整剪辑任务状态

    Response:
        - task_id: 任务ID
        - status: 状态 (processing, completed, failed)
        - progress: 进度 0-100
        - message: 消息
        - adjusted_video: 调整后的视频路径（完成后）
        - stats: 统计信息（完成后）
        - error: 错误信息（失败时）
    """
    with tasks_lock:
        task = tasks.get(task_id)

        if not task:
            return jsonify({'error': '任务不存在'}), 404

        if task.get('type') != 'iterative_adjust':
            return jsonify({'error': '任务类型不匹配'}), 400

        response = {
            'task_id': task_id,
            'status': task['status'],
            'progress': task.get('progress', 0),
            'message': task.get('message', '')
        }

        if task['status'] == 'completed':
            response['adjusted_video'] = task.get('adjusted_video')
            response['stats'] = task.get('stats')

        if task['status'] == 'failed':
            response['error'] = task.get('error')

        return jsonify(response)


@app.route('/api/iterative-adjust/download/<task_id>', methods=['GET'])
def iterative_adjust_download(task_id):
    """
    下载迭代调整剪辑结果

    Query:
        - type: 文件类型 (video, log)

    Response: 文件下载
    """
    with tasks_lock:
        task = tasks.get(task_id)

        if not task:
            return jsonify({'error': '任务不存在'}), 404

        if task.get('type') != 'iterative_adjust':
            return jsonify({'error': '任务类型不匹配'}), 400

        if task['status'] != 'completed':
            return jsonify({'error': '任务未完成'}), 400

    file_type = request.args.get('type', 'video')

    try:
        if file_type == 'video':
            file_path = task.get('adjusted_video')
            if not file_path or not os.path.exists(file_path):
                return jsonify({'error': '视频文件不存在'}), 404

            filename = os.path.basename(file_path)
            return send_file(file_path, as_attachment=True, download_name=filename)

        elif file_type == 'log':
            log_path = os.path.join(os.path.dirname(task.get('adjusted_video', '')), 'timeline_remap_log.json')
            if not os.path.exists(log_path):
                return jsonify({'error': '日志文件不存在'}), 404

            filename = os.path.basename(log_path)
            return send_file(log_path, as_attachment=True, download_name=filename)

        else:
            return jsonify({'error': '无效的文件类型'}), 400

    except Exception as e:
        logger.error(f"下载文件失败: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/iterative-adjust/task/<task_id>', methods=['DELETE'])
def iterative_adjust_delete_task(task_id):
    """
    删除迭代调整剪辑任务

    Response:
        - message: 成功消息
    """
    with tasks_lock:
        task = tasks.get(task_id)

        if not task:
            return jsonify({'error': '任务不存在'}), 404

        if task.get('type') != 'iterative_adjust':
            return jsonify({'error': '任务类型不匹配'}), 400

        # 删除任务目录
        task_dir = os.path.join(TASKS_FOLDER, task_id)
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir)
            logger.info(f"已删除任务目录: {task_dir}")

        # 删除任务记录
        del tasks[task_id]

        return jsonify({
            'message': '任务已删除',
            'task_id': task_id
        })


if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("🚀 视频重新生成工具 - API服务启动")
    logger.info("=" * 60)
    logger.info(f"🌐 API地址: http://localhost:5001")
    logger.info(f"📂 工作目录: {os.path.dirname(__file__)}")
    logger.info("=" * 60)
    logger.info("服务已启动，等待请求...")
    logger.info("")

    app.run(
        host='0.0.0.0',
        port=5001,
        debug=True,
        threaded=True
    )
