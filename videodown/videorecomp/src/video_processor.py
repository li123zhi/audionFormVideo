#!/usr/bin/env python3.12
"""
视频处理核心模块
处理视频重新生成的核心逻辑
"""

import os
import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import List, Tuple, Optional
import pysrt
from moviepy import VideoFileClip, AudioFileClip, TextClip, CompositeAudioClip, ImageClip, CompositeVideoClip
from moviepy.video.tools.subtitles import SubtitlesClip
import chardet
from tqdm import tqdm
from PIL import Image, ImageDraw, ImageFont
import subprocess
import json


class SubtitleProcessor:
    """字幕处理器"""

    def __init__(self, srt_path: str):
        """
        初始化字幕处理器

        Args:
            srt_path: SRT字幕文件路径
        """
        self.srt_path = srt_path
        self.subs = self._load_srt()

    def _load_srt(self) -> pysrt.SubRipFile:
        """加载SRT字幕文件，自动检测编码"""
        # 检测文件编码
        with open(self.srt_path, 'rb') as f:
            raw_data = f.read()
            result = chardet.detect(raw_data)
            encoding = result['encoding'] or 'utf-8'

        # 加载字幕
        subs = pysrt.open(self.srt_path, encoding=encoding)
        return subs

    def get_subtitle_count(self) -> int:
        """获取字幕条数"""
        return len(self.subs)

    def get_subtitle_by_index(self, index: int) -> pysrt.SubRipItem:
        """根据索引获取字幕"""
        return self.subs[index]

    def get_total_duration(self) -> int:
        """获取字幕总时长（毫秒）"""
        if not self.subs:
            return 0
        return self.subs[-1].end.ordinal

    def to_moviepy_format(self) -> List[Tuple[Tuple[float, float], str]]:
        """
        转换为moviepy可用的格式

        Returns:
            List of ((start_time, end_time), text) tuples
        """
        result = []
        for sub in self.subs:
            start = sub.start.ordinal / 1000.0  # 转换为秒
            end = sub.end.ordinal / 1000.0
            text = sub.text
            result.append(((start, end), text))
        return result


class AudioMerger:
    """音频合并器 - 根据字幕时间轴合并音频"""

    def __init__(self, audio_files: List[str], srt_file: str):
        """
        初始化音频合并器

        Args:
            audio_files: 音频文件列表（按顺序，第一个对应第一个字幕）
            srt_file: SRT字幕文件路径
        """
        self.audio_files = audio_files
        self.srt_file = srt_file

    def merge_audio(self, output_path: str) -> str:
        """
        根据字幕时间轴合并多个音频文件，字幕之间填充静音

        Args:
            output_path: 输出文件路径

        Returns:
            输出文件路径
        """
        if not self.audio_files:
            raise ValueError("没有音频文件需要合并")

        # 读取字幕文件获取时间轴
        print(f"正在读取字幕文件...")
        subs = pysrt.open(self.srt_file)

        if len(subs) != len(self.audio_files):
            raise ValueError(f"字幕数量({len(subs)})与音频文件数量({len(self.audio_files)})不匹配")

        print(f"正在根据字幕时间轴合并 {len(self.audio_files)} 个音频片段...")

        # 为每个音频片段创建一个剪辑，放置在对应的字幕时间段
        audio_clips = []

        for i, (audio_file, sub) in enumerate(tqdm(zip(self.audio_files, subs), desc="合并音频", total=len(self.audio_files))):
            try:
                # 加载音频文件
                clip = AudioFileClip(audio_file)

                # 获取字幕的时间段
                start_time = sub.start.ordinal / 1000.0  # 转换为秒
                end_time = sub.end.ordinal / 1000.0
                segment_duration = end_time - start_time

                # 如果音频长度超过字幕时间段，裁剪音频
                if clip.duration > segment_duration:
                    clip = clip.subclipped(0, segment_duration)

                # 设置音频在最终音频中的开始时间
                clip = clip.with_start(start_time)
                audio_clips.append(clip)

            except Exception as e:
                print(f"警告: 无法处理音频文件 {audio_file}: {e}")
                continue

        if not audio_clips:
            raise ValueError("没有成功加载任何音频文件")

        # 合并所有音频片段（CompositeAudioClip 会自动在音频之间填充静音）
        final_audio = CompositeAudioClip(audio_clips)

        # 写入文件
        final_audio.write_audiofile(output_path)

        # 关闭所有clip释放内存
        for clip in audio_clips:
            clip.close()
        final_audio.close()

        # 输出总时长
        total_duration = final_audio.duration
        print(f"✅ 音频合并完成，总时长: {total_duration:.2f}秒")

        return output_path


class VideoRecomposer:
    """视频重新生成器"""

    # 默认字幕样式
    DEFAULT_STYLE = {
        'font_name': 'Arial',              # 字体（macOS使用Arial，Windows可用微软雅黑）
        'font_size': 32,                   # 字号（1080p推荐32，720p推荐24）
        'alignment': 'center',             # 对齐方式（center=底部居中）
        'margin_v': 100,                   # 垂直边距（像素）
        'primary_colour': '&HFFFFFF',      # 字体颜色（白色）
        'outline_colour': '&H000000',      # 描边颜色（黑色）
        'outline': 0,                      # 描边宽度（像素，0=无描边）
        'back_colour': '&H00000000',       # 背景色（完全透明）
        'border_style': 1                  # 边框样式（1=描边+背景）
    }

    def __init__(
        self,
        original_video: str,
        srt_file: str,
        audio_zip: str,
        output_dir: str = "output",
        subtitle_style: dict = None,
        enable_ai_separation: bool = False,
        original_srt_file: str = None,
        auto_clip_video: bool = False
    ):
        """
        初始化视频重新生成器

        Args:
            original_video: 原视频文件路径
            srt_file: SRT字幕文件路径（新字幕）
            audio_zip: 配音ZIP文件路径
            output_dir: 输出目录
            subtitle_style: 字幕样式配置（可选，默认使用DEFAULT_STYLE）
            enable_ai_separation: 是否启用AI音频分离（默认False）
            original_srt_file: 原字幕文件路径（可选）
            auto_clip_video: 是否根据字幕时间自动剪辑视频（默认False）
        """
        self.original_video = original_video
        self.srt_file = srt_file
        self.original_srt_file = original_srt_file
        self.audio_zip = audio_zip
        self.output_dir = output_dir
        self.subtitle_style = {**self.DEFAULT_STYLE, **(subtitle_style or {})}
        self.enable_ai_separation = enable_ai_separation
        self.auto_clip_video = auto_clip_video
        self.temp_dir = tempfile.mkdtemp(prefix="videorecomp_")

        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)

        # 初始化处理器
        self.subtitle_processor = None
        self.original_subtitle_processor = None
        self.extracted_audio_files = []

    def _extract_audio_from_zip(self) -> List[str]:
        """从ZIP文件中提取音频文件并按顺序排列"""
        audio_files = []

        with zipfile.ZipFile(self.audio_zip, 'r') as zip_ref:
            # 获取所有文件
            all_files = zip_ref.namelist()
            # 过滤出音频文件
            audio_files_in_zip = [f for f in all_files if f.endswith(('.mp3', '.mp4', '.m4a', '.aac', '.wav'))]

            if not audio_files_in_zip:
                raise ValueError("ZIP文件中没有找到音频文件")

            # 按文件名排序
            audio_files_in_zip.sort()

            print(f"从ZIP中提取 {len(audio_files_in_zip)} 个音频文件...")

            # 提取文件
            for file_name in tqdm(audio_files_in_zip, desc="提取音频"):
                extract_path = os.path.join(self.temp_dir, os.path.basename(file_name))
                zip_ref.extract(file_name, self.temp_dir)
                # 移动到temp_dir根目录
                extracted_file = os.path.join(self.temp_dir, file_name)
                if os.path.exists(extracted_file):
                    audio_files.append(extracted_file)

        return audio_files

    def extract_all_audio_tracks(self) -> tuple:
        """
        提取原视频的所有音轨并保存为ZIP文件

        Returns:
            (ZIP文件路径, 第一个音频文件路径) 或 (None, None)
        """
        print("\n提取原视频音轨...")

        # 使用ffprobe获取视频信息
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_streams',
            '-select_streams', 'a',  # 只选择音频流
            self.original_video
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            streams_info = json.loads(result.stdout)
            audio_streams = streams_info.get('streams', [])
        except subprocess.CalledProcessError as e:
            print(f"警告: 无法获取视频音轨信息: {e}")
            return None
        except json.JSONDecodeError:
            print("警告: 无法解析视频信息")
            return None

        if not audio_streams:
            print("原视频没有音轨")
            return None

        print(f"发现 {len(audio_streams)} 个音轨")

        # 创建临时目录存放提取的音频文件
        temp_audio_dir = os.path.join(self.temp_dir, 'extracted_audio')
        os.makedirs(temp_audio_dir, exist_ok=True)

        extracted_files = []

        # 提取每个音轨并转换为MP3
        for idx, stream in enumerate(audio_streams):
            stream_index = stream.get('index', idx)
            language = stream.get('tags', {}).get('language', f'track_{idx}')

            output_filename = f"audio_{idx}_{language}.mp3"
            output_path = os.path.join(temp_audio_dir, output_filename)

            print(f"提取音轨 {idx + 1}/{len(audio_streams)}: {language}")

            # 使用ffmpeg提取音轨并转换为MP3
            cmd = [
                'ffmpeg',
                '-y',  # 覆盖已存在的文件
                '-i', self.original_video,
                '-map', f'0:a:{idx}',  # 选择第idx个音频流
                '-q:a', '2',  # MP3质量（0-9，2为高质量）
                output_path
            ]

            try:
                subprocess.run(cmd, capture_output=True, check=True)
                extracted_files.append(output_path)
                print(f"  ✅ 已保存: {output_filename}")
            except subprocess.CalledProcessError as e:
                print(f"  ❌ 提取失败: {e}")

        if not extracted_files:
            print("没有成功提取任何音轨")
            return None, None

        # 打包成ZIP文件
        zip_filename = "original_audio_tracks.zip"
        zip_path = os.path.join(self.output_dir, zip_filename)

        print(f"\n打包音轨到 {zip_filename}...")

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in extracted_files:
                arcname = os.path.basename(file_path)
                zipf.write(file_path, arcname)

        print(f"✅ 音轨已保存到: {zip_path}")

        # 返回 ZIP 路径和第一个音频文件路径（用于 AI 分离）
        first_audio_path = extracted_files[0] if extracted_files else None
        return zip_path, first_audio_path

    def separate_audio_tracks(self, main_audio_path: str = None, enable_ai: bool = False) -> dict:
        """
        使用 Demucs AI 分离音频为人声和伴奏

        Args:
            main_audio_path: 主音频文件路径，如果为None则从原视频提取
            enable_ai: 是否启用AI分离（默认False）

        Returns:
            dict: 分离后的音频文件路径字典
        """
        if not enable_ai:
            return None

        print("\n开始 AI 音频分离...")

        # 检查是否安装了 Demucs
        try:
            import torch
            import numpy as np
            import soundfile as sf
            from demucs.pretrained import get_model
            from demucs import apply
        except ImportError as e:
            print(f"⚠️  未安装必要的库: {e}")
            print("   安装方法:")
            print("   pip install demucs soundfile")
            return None

        # 如果没有提供音频路径，从原视频提取主音轨
        if main_audio_path is None:
            main_audio_path = os.path.join(self.temp_dir, 'main_audio.wav')
            print("提取主音轨...")
            cmd = [
                'ffmpeg', '-y',
                '-i', self.original_video,
                '-map', '0:a:0',  # 第一个音轨
                '-ac', '2',  # 双声道
                '-ar', '44100',  # 采样率
                '-loglevel', 'error',
                main_audio_path
            ]
            try:
                subprocess.run(cmd, capture_output=True, check=True)
            except subprocess.CalledProcessError:
                print("❌ 提取主音轨失败")
                return None

        # 创建输出目录
        separation_dir = os.path.join(self.output_dir, 'separated_audio')
        os.makedirs(separation_dir, exist_ok=True)

        print("使用 Demucs htdemucs 模型分离音频...")
        print("分离类型: 人声、伴奏")
        print("这可能需要几分钟，请耐心等待...")

        try:
            # 加载模型
            model = get_model('htdemucs')
            model.eval()

            # 检测设备
            device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            model = model.to(device)
            print(f"使用设备: {device}")

            # 加载音频文件 - 使用 soundfile 直接加载
            print(f"正在加载音频: {main_audio_path}")
            audio, sample_rate = sf.read(main_audio_path, always_2d=True)

            # soundfile 返回格式是 [samples, channels]，需要转置为 [channels, samples]
            waveform = torch.from_numpy(audio.T).float()

            # 转换为单声道如果是立体声（Demucs会自动处理）
            if waveform.shape[0] > 2:
                waveform = waveform[:2, :]  # 只取前两个声道

            # 确保44100采样率 - 使用 resampy 或 ffmpeg 重采样
            if sample_rate != 44100:
                print(f"重采样从 {sample_rate}Hz 到 44100Hz...")
                # 使用 ffmpeg 进行重采样
                temp_resampled = os.path.join(self.temp_dir, 'resampled.wav')
                cmd = [
                    'ffmpeg', '-y',
                    '-i', main_audio_path,
                    '-ar', '44100',
                    '-ac', '2',
                    '-loglevel', 'error',
                    temp_resampled
                ]
                subprocess.run(cmd, capture_output=True, check=True)
                # 重新加载
                audio, sample_rate = sf.read(temp_resampled, always_2d=True)
                waveform = torch.from_numpy(audio.T).float()
                os.remove(temp_resampled)
                sample_rate = 44100

            print(f"音频信息: 采样率={sample_rate}Hz, 声道={waveform.shape[0]}, 时长={waveform.shape[1]/sample_rate:.2f}秒")

            # 添加批次维度
            waveform = waveform.unsqueeze(0)

            # 使用 Demucs apply_model 分离音频
            print("正在分离音频...")
            with torch.no_grad():
                sources = apply.apply_model(
                    model,
                    waveform,
                    device=device,
                    shifts=1,
                    split=True,
                    overlap=0.25,
                    progress=True
                )

            # sources shape: [batch, sources, channels, samples]
            sources = sources.squeeze(0)  # [sources, channels, samples]

            # 模型输出顺序: drums, bass, other, vocals
            source_names = ['drums', 'bass', 'other', 'vocals']

            print("\n保存分离后的音轨...")
            temp_wav_files = {}

            for i, name in enumerate(source_names):
                source = sources[i]  # [channels, samples]

                # 保存为WAV - 使用 soundfile
                wav_path = os.path.join(separation_dir, f'{name}.wav')
                # 转换为 numpy 并转置回 [samples, channels] 格式
                audio_array = source.cpu().numpy().T
                sf.write(wav_path, audio_array, sample_rate)
                temp_wav_files[name] = wav_path
                print(f"  ✅ 已保存: {name}.wav")

            # 转换为 MP3
            print("\n转换为 MP3 格式...")
            temp_mp3_files = {}

            for stem, wav_path in temp_wav_files.items():
                temp_mp3_path = os.path.join(separation_dir, f'temp_{stem}.mp3')

                cmd = [
                    'ffmpeg', '-y',
                    '-i', wav_path,
                    '-q:a', '2',
                    '-loglevel', 'error',
                    temp_mp3_path
                ]
                subprocess.run(cmd, capture_output=True, check=True)

                if os.path.exists(temp_mp3_path):
                    temp_mp3_files[stem] = temp_mp3_path
                    print(f"  ✅ 已转换: {stem}.mp3")

                # 删除 wav 文件
                if os.path.exists(wav_path):
                    os.remove(wav_path)

            # 创建最终的人声文件
            vocals_path = os.path.join(separation_dir, '人声.mp3')
            if 'vocals' in temp_mp3_files and os.path.exists(temp_mp3_files['vocals']):
                shutil.move(temp_mp3_files['vocals'], vocals_path)
                print(f"  ✅ 已保存: 人声.mp3")
            else:
                print("  ❌ 人声文件生成失败")
                return None

            # 创建伴奏（去掉人声）= drums + bass + other
            no_vocals_path = os.path.join(separation_dir, '伴奏.mp3')
            print("\n合并音轨创建伴奏...")

            if all(stem in temp_mp3_files for stem in ['drums', 'bass', 'other']):
                drums_path = temp_mp3_files['drums']
                bass_path = temp_mp3_files['bass']
                other_path = temp_mp3_files['other']

                cmd = [
                    'ffmpeg', '-y',
                    '-i', drums_path,
                    '-i', bass_path,
                    '-i', other_path,
                    '-filter_complex', '[0:a][1:a][2:a]amix=inputs=3:duration=longest',
                    '-q:a', '2',
                    '-loglevel', 'error',
                    no_vocals_path
                ]
                subprocess.run(cmd, capture_output=True, check=True)
                print(f"  ✅ 已创建: 伴奏.mp3")
            else:
                print("  ❌ 缺少必要的音轨文件")
                return None

            # 删除临时 MP3 文件
            for stem in ['drums', 'bass', 'other']:
                temp_path = temp_mp3_files.get(stem)
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)

            # 最终输出文件
            final_output = {
                'vocals': vocals_path,
                'no_vocals': no_vocals_path
            }

            # 打包成ZIP
            zip_path = os.path.join(self.output_dir, 'separated_audio.zip')
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                if os.path.exists(vocals_path):
                    zipf.write(vocals_path, '人声.mp3')
                    print(f"  ✅ 已添加到ZIP: 人声.mp3")
                if os.path.exists(no_vocals_path):
                    zipf.write(no_vocals_path, '伴奏.mp3')
                    print(f"  ✅ 已添加到ZIP: 伴奏.mp3")

            print(f"\n✅ 音频分离完成！")
            print(f"   文件已保存到: {separation_dir}")
            print(f"   - 人声: {vocals_path}")
            print(f"   - 伴奏: {no_vocals_path}")
            print(f"   ZIP打包: {zip_path}")

            return final_output

        except Exception as e:
            print(f"❌ AI 音频分离失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_color(self, color_str: str) -> tuple:
        """
        解析ASS颜色格式为RGB元组

        Args:
            color_str: ASS颜色格式，如 '&HFFFFFF' (白) 或 '&H000000' (黑)

        Returns:
            (R, G, B, A) 元组
        """
        # 移除 &H 前缀
        hex_color = color_str.replace('&H', '')

        # ASS格式是 BGR，需要转换为 RGB
        if len(hex_color) == 6:
            b = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            r = int(hex_color[4:6], 16)
            return (r, g, b, 255)
        return (255, 255, 255, 255)

    def _wrap_text(self, text: str, font, draw, max_width: int) -> list:
        """
        将文本按最大宽度换行

        Args:
            text: 原始文本
            font: 字体对象
            draw: ImageDraw对象
            max_width: 最大宽度（像素）

        Returns:
            换行后的文本行列表
        """
        words = list(text)  # 按字符分割（中文友好）
        lines = []
        current_line = ""

        for char in words:
            test_line = current_line + char
            try:
                bbox = draw.textbbox((0, 0), test_line, font=font)
                width = bbox[2] - bbox[0]
            except:
                width = len(test_line) * 20  # 降级处理

            if width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char

        if current_line:
            lines.append(current_line)

        return lines if lines else [text]

    def _create_subtitle_clips(self, video_clip, subtitles: List[Tuple[Tuple[float, float], str]]) -> 'CompositeVideoClip':
        """
        使用Pillow创建字幕clip（绕过MoviePy的TextClip字体问题）

        Args:
            video_clip: 视频clip
            subtitles: 字幕列表，格式 [((start, end), text), ...]

        Returns:
            包含所有字幕的CompositeVideoClip
        """
        import numpy as np

        # 获取样式配置
        style = self.subtitle_style
        font_size = style.get('font_size', 32)
        margin_v = style.get('margin_v', 60)
        outline = style.get('outline', 3)
        primary_color = self._parse_color(style.get('primary_colour', '&HFFFFFF'))
        outline_color = self._parse_color(style.get('outline_colour', '&H000000'))

        video_width = video_clip.w
        video_height = video_clip.h

        # 字体路径映射
        font_paths = [
            '/System/Library/Fonts/PingFang.ttc',           # macOS 中文字体
            '/System/Library/Fonts/Helvetica.ttc',           # macOS
            '/System/Library/Fonts/ArialHB.ttc',             # macOS
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',  # Linux
            'C:\\Windows\\Fonts\\msyh.ttc',                  # Windows 微软雅黑
            'C:\\Windows\\Fonts\\simhei.ttf',                # Windows 黑体
        ]

        font = None
        for font_path in font_paths:
            try:
                font = ImageFont.truetype(font_path, font_size)
                break
            except:
                continue

        if font is None:
            font = ImageFont.load_default()

        # 为每个字幕创建一个clip
        subtitle_clips = []
        line_spacing = font_size // 4  # 行间距

        for (start_time, end_time), text in subtitles:
            # 创建临时图像用于计算尺寸
            temp_img = Image.new('RGBA', (1, 1), (255, 255, 255, 0))
            temp_draw = ImageDraw.Draw(temp_img)

            # 计算最大宽度（视频宽度的90%）
            max_width = int(video_width * 0.9)

            # 自动换行
            lines = self._wrap_text(text, font, temp_draw, max_width)

            # 计算多行文本的总尺寸
            line_heights = []
            line_widths = []
            for line in lines:
                try:
                    bbox = temp_draw.textbbox((0, 0), line, font=font)
                    line_widths.append(bbox[2] - bbox[0])
                    line_heights.append(bbox[3] - bbox[1])
                except:
                    line_widths.append(len(line) * font_size * 0.6)
                    line_heights.append(font_size)

            max_line_width = max(line_widths) if line_widths else max_width
            total_height = sum(line_heights) + line_spacing * (len(lines) - 1)

            # 创建字幕图像（带边距）
            img_width = max_line_width + 40
            img_height = total_height + margin_v

            # 创建带透明度的 RGBA 图像（完全透明背景）
            img = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # 绘制多行文本
            y_offset = (img_height - total_height) // 2
            for i, line in enumerate(lines):
                try:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    line_width = bbox[2] - bbox[0]
                    line_height = bbox[3] - bbox[1]
                except:
                    line_width = len(line) * font_size * 0.6
                    line_height = font_size

                # 居中绘制
                x = (img_width - line_width) // 2
                y = y_offset

                # 绘制描边（根据配置的描边宽度）
                if outline > 0:
                    for adj_x in range(-outline, outline + 1):
                        for adj_y in range(-outline, outline + 1):
                            if adj_x != 0 or adj_y != 0:
                                draw.text((x + adj_x, y + adj_y), line, font=font, fill=outline_color)

                # 绘制主文本
                draw.text((x, y), line, font=font, fill=primary_color)

                y_offset += line_height + line_spacing

            # 转换为 RGBA 数组（保留透明通道）
            img_rgba = np.array(img)

            # 创建 ImageClip（使用 is_mask=True 保留透明度）
            duration = end_time - start_time
            text_clip = ImageClip(img_rgba, duration=duration, transparent=True)

            # 设置开始时间和位置（根据对齐方式）
            text_clip = text_clip.with_start(start_time).with_end(end_time)

            # 根据对齐方式设置位置
            alignment = style.get('alignment', 'center')
            if alignment == 'center':
                text_clip = text_clip.with_position(('center', video_height - img_height))
            elif alignment == 'left':
                text_clip = text_clip.with_position((margin_v, video_height - img_height))
            elif alignment == 'right':
                text_clip = text_clip.with_position((video_width - img_width - margin_v, video_height - img_height))
            else:
                text_clip = text_clip.with_position(('center', 'bottom'))

            subtitle_clips.append(text_clip)

        return subtitle_clips

    def _clip_video_by_subtitle_times(self, output_path: str) -> str:
        """
        根据原字幕和新字幕的时间对比，智能剪辑原视频
        对比每个字幕条目的开始时间，提取重叠的片段并拼接

        Args:
            output_path: 输出视频路径

        Returns:
            剪辑后的视频路径
        """
        print("\n根据字幕时间对比智能剪辑视频...")

        if not self.original_subtitle_processor:
            print("没有原字幕文件，跳过视频剪辑")
            return self.original_video

        # 获取原字幕和新字幕
        original_subs = self.original_subtitle_processor.subs
        new_subs = self.subtitle_processor.subs

        if not original_subs or not new_subs:
            print("字幕为空，跳过视频剪辑")
            return self.original_video

        print(f"原字幕条数: {len(original_subs)}")
        print(f"新字幕条数: {len(new_subs)}")

        # 获取原视频时长
        from moviepy import VideoFileClip
        video_clip = VideoFileClip(self.original_video)
        video_duration = video_clip.duration
        video_clip.close()

        # 收集需要提取的时间片段
        segments_to_extract = []

        # 对每个新字幕，找到在原字幕中对应的部分
        for new_sub in new_subs:
            new_start = new_sub.start.ordinal / 1000.0
            new_end = new_sub.end.ordinal / 1000.0

            # 查找与新字幕时间有重叠的原字幕
            for orig_sub in original_subs:
                orig_start = orig_sub.start.ordinal / 1000.0
                orig_end = orig_sub.end.ordinal / 1000.0

                # 计算重叠部分
                overlap_start = max(new_start, orig_start)
                overlap_end = min(new_end, orig_end)

                # 如果有重叠（至少0.5秒）
                if overlap_end - overlap_start >= 0.5:
                    clip_start = max(0, overlap_start)
                    clip_end = min(video_duration, overlap_end)

                    # 限制片段长度，避免过长
                    if clip_end - clip_start > 30:  # 最多30秒
                        clip_end = clip_start + 30

                    if clip_end > clip_start:
                        segments_to_extract.append((clip_start, clip_end))
                        print(f"  片段: {clip_start:.2f}s - {clip_end:.2f}s (时长: {clip_end - clip_start:.2f}s)")

        if not segments_to_extract:
            print("没有找到重叠的时间片段，使用原视频")
            return self.original_video

        print(f"\n共找到 {len(segments_to_extract)} 个片段，总计时长: {sum(s[1]-s[0] for s in segments_to_extract):.2f}秒")

        # 合并相邻或接近的片段（间隔小于2秒）
        merged_segments = []
        if segments_to_extract:
            current_start, current_end = segments_to_extract[0]

            for start, end in segments_to_extract[1:]:
                if start - current_end <= 2.0:  # 间隔小于2秒，合并
                    current_end = end
                else:
                    merged_segments.append((current_start, current_end))
                    current_start, current_end = start, end

            merged_segments.append((current_start, current_end))

            print(f"\n合并后共 {len(merged_segments)} 个片段")
            for i, (start, end) in enumerate(merged_segments):
                print(f"  片段{i+1}: {start:.2f}s - {end:.2f}s (时长: {end - start:.2f}s)")

        # 提取并拼接片段
        print("\n正在提取并拼接视频片段...")
        segment_files = []

        for i, (start, end) in enumerate(merged_segments):
            temp_segment = os.path.join(self.temp_dir, f'segment_{i:03d}.mp4')

            cmd = [
                'ffmpeg', '-y',
                '-ss', str(start),
                '-i', self.original_video,
                '-t', str(end - start),
                '-c', 'copy',
                '-avoid_negative_ts', '1',
                temp_segment
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0 and os.path.exists(temp_segment) and os.path.getsize(temp_segment) > 1000:
                segment_files.append(temp_segment)
                print(f"  ✅ 片段{i+1}提取完成: {temp_segment}")
            else:
                print(f"  ⚠️  片段{i+1}提取失败")

        if not segment_files:
            print("所有片段提取失败，使用原视频")
            return self.original_video

        # 创建片段列表文件用于ffmpeg拼接
        segment_list = os.path.join(self.temp_dir, 'segment_list.txt')
        with open(segment_list, 'w') as f:
            for seg_file in segment_files:
                f.write(f"file '{seg_file}'\n")

        # 拼接所有片段
        print("\n正在拼接视频片段...")
        clipped_video_path = os.path.join(self.output_dir, "clipped_video.mp4")

        concat_cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', segment_list,
            '-c', 'copy',
            clipped_video_path
        ]

        result = subprocess.run(concat_cmd, capture_output=True, text=True)

        if result.returncode == 0 and os.path.exists(clipped_video_path) and os.path.getsize(clipped_video_path) > 1000:
            print(f"✅ 视频剪辑完成: {clipped_video_path}")
            print(f"   剪辑后的视频已保存到输出目录")
            return clipped_video_path
        else:
            print(f"⚠️  视频拼接失败，使用原视频: {result.stderr}")
            return self.original_video

    def process(self) -> dict:
        """
        执行视频重新生成流程

        Returns:
            包含所有生成文件路径的字典
        """
        # 0. 提取原视频音轨（默认执行）
        _, first_audio_path = self.extract_all_audio_tracks()

        # 0.1 AI 音频分离（自动执行，使用提取的第一个音轨）
        accompaniment_path = None
        if first_audio_path:
            print("\n自动执行 AI 音频分离...")
            separation_result = self.separate_audio_tracks(main_audio_path=first_audio_path, enable_ai=True)
            if separation_result:
                accompaniment_path = separation_result.get('no_vocals')

        # 1. 加载新字幕
        print("加载新字幕文件...")
        self.subtitle_processor = SubtitleProcessor(self.srt_file)
        print(f"新字幕加载完成，共 {self.subtitle_processor.get_subtitle_count()} 条")

        # 1.1 加载原字幕（如果存在）
        if self.original_srt_file and os.path.exists(self.original_srt_file):
            print("加载原字幕文件...")
            self.original_subtitle_processor = SubtitleProcessor(self.original_srt_file)
            print(f"原字幕加载完成，共 {self.original_subtitle_processor.get_subtitle_count()} 条")

        # 2. 提取并合并配音音频
        print("\n处理配音文件...")
        self.extracted_audio_files = self._extract_audio_from_zip()

        # 保存合并的音频到输出目录
        merged_audio_path = os.path.join(self.output_dir, "merged_audio.mp3")
        audio_merger = AudioMerger(self.extracted_audio_files, self.srt_file)
        audio_merger.merge_audio(merged_audio_path)
        print(f"✅ 音频合并完成并保存到本地: {merged_audio_path}")

        # 2.1 将伴奏与配音合并（如果存在伴奏）
        mixed_audio_path = None
        if accompaniment_path and os.path.exists(accompaniment_path):
            print("\n合并伴奏与配音...")
            mixed_audio_path = os.path.join(self.output_dir, "mixed_audio.mp3")

            # 使用 ffmpeg 混合两个音频
            cmd = [
                'ffmpeg', '-y',
                '-i', accompaniment_path,
                '-i', merged_audio_path,
                '-filter_complex', '[0:a][1:a]amix=inputs=2:duration=longest',
                '-q:a', '2',
                '-loglevel', 'error',
                mixed_audio_path
            ]
            try:
                subprocess.run(cmd, capture_output=True, check=True)
                print(f"✅ 伴奏混合完成: {mixed_audio_path}")
            except subprocess.CalledProcessError as e:
                print(f"⚠️  伴奏混合失败: {e}")
                mixed_audio_path = None

        # 选择使用哪个音频（优先使用混合音频）
        final_audio_path = mixed_audio_path if mixed_audio_path else merged_audio_path
        audio_type = "伴奏+配音" if mixed_audio_path else "仅配音"
        print(f"\n使用音频: {audio_type} -> {final_audio_path}")

        # 3. 根据字幕时间剪辑视频（如果启用）
        if self.auto_clip_video and self.original_srt_file:
            clipped_video_path = self._clip_video_by_subtitle_times(
                os.path.join(self.temp_dir, 'auto_clipped_video.mp4')
            )
            video_to_process = clipped_video_path
        else:
            video_to_process = self.original_video

        # 4. 加载视频
        print("\n加载视频...")
        if self.auto_clip_video and self.original_srt_file and video_to_process != self.original_video:
            print(f"使用剪辑后的视频: {video_to_process}")
        else:
            print(f"使用原视频: {video_to_process}")

        original_clip = VideoFileClip(video_to_process)
        final_audio = AudioFileClip(final_audio_path)

        # 创建带新音频的视频基础版本（不带硬字幕）
        video_with_audio = original_clip.with_audio(final_audio)

        # 4. 生成不带字幕的视频
        print("\n生成不带字幕的视频...")
        no_subtitle_path = os.path.join(self.output_dir, "output_no_subtitle.mp4")
        video_with_audio.write_videofile(
            no_subtitle_path,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile=os.path.join(self.temp_dir, 'temp_audio_no_sub.m4a'),
            remove_temp=True
        )

        # 结果字典
        result = {
            'no_subtitle': no_subtitle_path,
            'merged_audio': merged_audio_path,
            'mixed_audio': mixed_audio_path
        }

        # 如果进行了视频剪辑，保存剪辑后的视频路径
        if self.auto_clip_video and self.original_srt_file and video_to_process != self.original_video:
            result['clipped_video'] = video_to_process

        original_clip = VideoFileClip(video_to_process)
        final_audio = AudioFileClip(final_audio_path)

        # 创建带新音频的视频基础版本（不带硬字幕）
        video_with_audio = original_clip.with_audio(final_audio)

        # 4. 生成不带字幕的视频
        print("\n生成不带字幕的视频...")
        no_subtitle_path = os.path.join(self.output_dir, "output_no_subtitle.mp4")

        video_with_audio.write_videofile(
            no_subtitle_path,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile=os.path.join(self.temp_dir, 'temp_audio_no_sub.m4a'),
            remove_temp=True
        )

        # 结果字典
        result = {
            'no_subtitle': no_subtitle_path,
            'merged_audio': merged_audio_path,
            'mixed_audio': mixed_audio_path
        }

        # 5. 生成新字幕版本
        print("\n生成新字幕版本...")

        # 5.1 生成新字幕软字幕视频
        new_soft_subtitle_path = os.path.join(self.output_dir, "output_new_soft_subtitle.mp4")
        cmd = [
            'ffmpeg', '-y',
            '-i', no_subtitle_path,
            '-i', self.srt_file,
            '-c', 'copy',
            '-c:s', 'mov_text',
            '-metadata:s:s:0', 'language=chi',
            '-movflags', '+faststart',
            new_soft_subtitle_path
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            print(f"✅ 新字幕软字幕视频已生成: {new_soft_subtitle_path}")
            result['new_soft_subtitle'] = new_soft_subtitle_path
        except subprocess.CalledProcessError as e:
            print(f"⚠️  新字幕软字幕视频生成失败: {e}")
            result['new_soft_subtitle'] = no_subtitle_path

        # 5.2 生成新字幕硬字幕视频
        print("生成新字幕硬字幕视频...")
        new_hard_subtitle_path = os.path.join(self.output_dir, "output_new_hard_subtitle.mp4")
        subtitles_data = self.subtitle_processor.to_moviepy_format()
        subtitle_clips = self._create_subtitle_clips(video_with_audio, subtitles_data)
        final_with_subtitle = CompositeVideoClip([video_with_audio] + subtitle_clips)

        final_with_subtitle.write_videofile(
            new_hard_subtitle_path,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile=os.path.join(self.temp_dir, 'temp_audio_new_hard_sub.m4a'),
            remove_temp=True
        )
        print(f"✅ 新字幕硬字幕视频已生成: {new_hard_subtitle_path}")
        result['new_hard_subtitle'] = new_hard_subtitle_path

        # 6. 生成原字幕版本（如果存在）
        if self.original_srt_file and os.path.exists(self.original_srt_file):
            print("\n生成原字幕版本...")

            # 6.1 生成原字幕软字幕视频
            original_soft_subtitle_path = os.path.join(self.output_dir, "output_original_soft_subtitle.mp4")
            cmd = [
                'ffmpeg', '-y',
                '-i', no_subtitle_path,
                '-i', self.original_srt_file,
                '-c', 'copy',
                '-c:s', 'mov_text',
                '-metadata:s:s:0', 'language=chi',
                '-movflags', '+faststart',
                original_soft_subtitle_path
            ]
            try:
                subprocess.run(cmd, capture_output=True, check=True)
                print(f"✅ 原字幕软字幕视频已生成: {original_soft_subtitle_path}")
                result['original_soft_subtitle'] = original_soft_subtitle_path
            except subprocess.CalledProcessError as e:
                print(f"⚠️  原字幕软字幕视频生成失败: {e}")

            # 6.2 生成原字幕硬字幕视频
            print("生成原字幕硬字幕视频...")
            original_hard_subtitle_path = os.path.join(self.output_dir, "output_original_hard_subtitle.mp4")
            original_subtitles_data = self.original_subtitle_processor.to_moviepy_format()
            original_subtitle_clips = self._create_subtitle_clips(video_with_audio, original_subtitles_data)
            original_final_with_subtitle = CompositeVideoClip([video_with_audio] + original_subtitle_clips)

            original_final_with_subtitle.write_videofile(
                original_hard_subtitle_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=os.path.join(self.temp_dir, 'temp_audio_original_hard_sub.m4a'),
                remove_temp=True
            )
            print(f"✅ 原字幕硬字幕视频已生成: {original_hard_subtitle_path}")
            result['original_hard_subtitle'] = original_hard_subtitle_path

        # 释放内存
        original_clip.close()
        final_audio.close()
        video_with_audio.close()
        if 'final_with_subtitle' in locals():
            final_with_subtitle.close()
        if 'original_final_with_subtitle' in locals():
            original_final_with_subtitle.close()

        print(f"\n处理完成！")
        print(f"✅ 仅配音音频: {merged_audio_path}")
        if mixed_audio_path:
            print(f"✅ 伴奏混合音频: {mixed_audio_path}")
        if 'clipped_video' in result:
            print(f"✅ 剪辑后的原视频: {result['clipped_video']}")
        print(f"✅ 不带字幕视频: {no_subtitle_path}")
        print(f"✅ 新字幕软字幕视频: {result['new_soft_subtitle']}")
        print(f"✅ 新字幕硬字幕视频: {new_hard_subtitle_path}")
        if 'original_soft_subtitle' in result:
            print(f"✅ 原字幕软字幕视频: {result['original_soft_subtitle']}")
        if 'original_hard_subtitle' in result:
            print(f"✅ 原字幕硬字幕视频: {result['original_hard_subtitle']}")

        return result

    def cleanup(self):
        """清理临时文件"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            print(f"已清理临时文件: {self.temp_dir}")


def create_video_recomposer(
    original_video: str,
    srt_file: str,
    audio_zip: str,
    output_dir: str = "output",
    subtitle_style: dict = None,
    enable_ai_separation: bool = False,
    original_srt_file: str = None,
    auto_clip_video: bool = False
) -> VideoRecomposer:
    """
    创建视频重新生成器的便捷函数

    Args:
        original_video: 原视频文件路径
        srt_file: SRT字幕文件路径（新字幕）
        audio_zip: 配音ZIP文件路径
        output_dir: 输出目录
        subtitle_style: 字幕样式配置（可选）
        enable_ai_separation: 是否启用AI音频分离（默认False）
        original_srt_file: 原字幕文件路径（可选）
        auto_clip_video: 是否根据字幕时间自动剪辑视频（默认False）

    Returns:
        VideoRecomposer实例
    """
    # 验证输入文件
    if not os.path.exists(original_video):
        raise FileNotFoundError(f"原视频文件不存在: {original_video}")
    if not os.path.exists(srt_file):
        raise FileNotFoundError(f"新字幕文件不存在: {srt_file}")
    if not os.path.exists(audio_zip):
        raise FileNotFoundError(f"配音ZIP文件不存在: {audio_zip}")
    if original_srt_file and not os.path.exists(original_srt_file):
        raise FileNotFoundError(f"原字幕文件不存在: {original_srt_file}")

    return VideoRecomposer(
        original_video=original_video,
        srt_file=srt_file,
        audio_zip=audio_zip,
        output_dir=output_dir,
        subtitle_style=subtitle_style,
        enable_ai_separation=enable_ai_separation,
        original_srt_file=original_srt_file,
        auto_clip_video=auto_clip_video
    )
