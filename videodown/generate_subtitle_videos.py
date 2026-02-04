#!/usr/bin/env python3.12
"""
本地生成软字幕和硬字幕视频
"""

import sys
import os
import subprocess
import json
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Optional

def check_ffmpeg():
    """检查FFmpeg是否安装"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except:
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

def create_soft_subtitle_video(
    video_path: str,
    srt_path: str,
    output_path: str
) -> bool:
    """
    创建软字幕视频（字幕嵌入到视频容器中）

    Args:
        video_path: 原视频路径
        srt_path: SRT字幕文件路径
        output_path: 输出视频路径

    Returns:
        是否成功
    """
    print(f"\n🎬 正在生成软字幕视频...")
    print(f"   输入视频: {video_path}")
    print(f"   字幕文件: {srt_path}")
    print(f"   输出视频: {output_path}")

    # 使用ffmpeg将字幕嵌入到视频容器中
    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-i', srt_path,
        '-c', 'copy',
        '-c:s', 'mov_text',
        '-map', '0:v:0',
        '-map', '0:a:0?',
        '-map', '1:s:0',
        '-metadata:s:s:0', 'language=chi',  # 设置字幕语言
        output_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if result.returncode == 0 and os.path.exists(output_path):
            duration = get_video_duration(output_path)
            print(f"   ✅ 软字幕视频生成成功！时长: {duration:.2f}秒")
            return True
        else:
            print(f"   ❌ 生成失败")
            if result.stderr:
                print(f"   错误: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print(f"   ⏱️  生成超时")
        return False
    except Exception as e:
        print(f"   ❌ 出错: {e}")
        return False

def create_hard_subtitle_video(
    video_path: str,
    srt_path: str,
    output_path: str,
    subtitle_config: Optional[Dict] = None
) -> bool:
    """
    创建硬字幕视频（字幕烧录到画面上）

    Args:
        video_path: 原视频路径
        srt_path: SRT字幕文件路径
        output_path: 输出视频路径
        subtitle_config: 字幕样式配置

    Returns:
        是否成功
    """
    print(f"\n🎬 正在生成硬字幕视频...")
    print(f"   输入视频: {video_path}")
    print(f"   字幕文件: {srt_path}")
    print(f"   输出视频: {output_path}")

    temp_srt = None
    try:
        # 创建一个临时SRT文件，避免路径中的特殊字符问题
        temp_dir = tempfile.mkdtemp()
        temp_srt = os.path.join(temp_dir, 'subtitle.srt')
        shutil.copy2(srt_path, temp_srt)

        # 默认字幕样式
        default_config = {
            'fontSize': 24,
            'fontColor': '#FFFFFF',
            'bold': False,
            'italic': False,
            'outline': True,
            'shadow': True
        }

        if subtitle_config:
            default_config.update(subtitle_config)

        # 构建字幕滤镜
        style_parts = []

        # 字体大小
        style_parts.append(f"FontSize={default_config['fontSize']}")

        # 字体颜色（移除#号）
        color = default_config['fontColor'].lstrip('#')
        style_parts.append(f"FontColor={color}")

        # 字体样式
        if default_config['bold']:
            style_parts.append("Bold=1")
        if default_config['italic']:
            style_parts.append("Italic=1")

        # 描边
        if default_config['outline']:
            style_parts.append("BorderStyle=1")
            style_parts.append("Outline=2")
            style_parts.append("OutlineColour=&H000000&H000000&")

        # 阴影
        if default_config['shadow']:
            style_parts.append("Shadow=1")
            style_parts.append("ShadowColour=&H000000&H000000&")

        subtitle_style = ",".join(style_parts)

        # 使用ffmpeg将字幕烧录到视频上
        # 注意：使用libx264重新编码会降低质量，增加时间
        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-vf', f"subtitles={temp_srt}:force_style='{subtitle_style}'",
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'copy',
            output_path
        ]

        try:
            print(f"   字幕样式: {subtitle_style}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)  # 硬字幕需要更多时间

            # 清理临时文件
            try:
                shutil.rmtree(temp_dir)
            except:
                pass

            if result.returncode == 0 and os.path.exists(output_path):
                duration = get_video_duration(output_path)
                print(f"   ✅ 硬字幕视频生成成功！时长: {duration:.2f}秒")
                return True
            else:
                print(f"   ❌ 生成失败")
                if result.stderr:
                    print(f"   错误: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            print(f"   ⏱️  生成超时")
            # 清理临时文件
            if temp_srt and os.path.exists(temp_srt):
                try:
                    os.remove(temp_srt)
                except:
                    pass
            return False
        except Exception as e:
            print(f"   ❌ 出错: {e}")
            # 清理临时文件
            if temp_srt and os.path.exists(temp_srt):
                try:
                    os.remove(temp_srt)
                except:
                    pass
            return False

    except Exception as e:
        print(f"   ❌ 出错: {e}")
        # 清理临时文件
        if temp_srt and os.path.exists(temp_srt):
            try:
                os.remove(temp_srt)
            except:
                pass
        return False

def main():
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║        本地视频字幕工具 - 生成软硬字幕视频                ║
║                                                           ║
║    上传原视频和新字幕，生成两个版本的视频                     ║
║    - 软字幕视频：字幕嵌入容器，可随时开关                      ║
║    - 硬字幕视频：字幕烧录画面，无法关闭                        ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """)

    if len(sys.argv) < 3:
        print("使用方法:")
        print("  python generate_subtitle_videos.py <视频.mp4> <字幕.srt> [输出目录]")
        print("\n示例:")
        print("  python generate_subtitle_videos.py video.mp4 subtitle.srt")
        print("  python generate_subtitle_videos.py video.mp4 subtitle.srt ./output")
        print("\n说明:")
        print("  - 软字幕视频: 字幕嵌入到视频容器中，播放时可开关")
        print("  - 硬字幕视频: 字幕烧录到画面上，无法关闭")
        print("  - 字幕样式: 可在脚本中配置")
        sys.exit(1)

    video_path = sys.argv[1]
    srt_path = sys.argv[2]
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "output"

    # 验证文件
    if not os.path.exists(video_path):
        print(f"❌ 视频文件不存在: {video_path}")
        sys.exit(1)

    if not os.path.exists(srt_path):
        print(f"❌ 字幕文件不存在: {srt_path}")
        sys.exit(1)

    # 检查FFmpeg
    if not check_ffmpeg():
        print("❌ FFmpeg未安装！")
        print("请先安装FFmpeg:")
        print("  macOS: brew install ffmpeg")
        print("  Ubuntu: sudo apt install ffmpeg")
        print("  Windows: 从 https://ffmpeg.org/download.html 下载")
        sys.exit(1)

    # 创建输出目录
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    video_name = Path(video_path).stem

    print(f"\n📂 输出目录: {output_path}")
    print(f"🎬 视频名称: {video_name}")

    # 字幕样式配置
    subtitle_config = {
        'fontSize': 24,
        'fontColor': '#FFFFFF',
        'bold': False,
        'italic': False,
        'outline': True,
        'shadow': True
    }

    # 生成软字幕视频
    soft_output = output_path / f"{video_name}_soft_subtitle.mp4"
    success_soft = create_soft_subtitle_video(video_path, srt_path, str(soft_output))

    # 生成硬字幕视频
    hard_output = output_path / f"{video_name}_hard_subtitle.mp4"
    success_hard = create_hard_subtitle_video(
        video_path,
        srt_path,
        str(hard_output),
        subtitle_config
    )

    # 总结
    print("\n" + "="*60)
    print("处理完成！")
    print("="*60)

    print(f"\n📁 输出文件:")

    if success_soft:
        print(f"   ✅ 软字幕视频: {soft_output}")
    else:
        print(f"   ❌ 软字幕视频: 生成失败")

    if success_hard:
        print(f"   ✅ 硬字幕视频: {hard_output}")
    else:
        print(f"   ❌ 硬字幕视频: 生成失败")

    print(f"\n💡 使用建议:")
    print(f"   - 软字幕视频：推荐使用，兼容性好，可开关字幕")
    print(f"   - 硬字幕视频：用于不支持软字幕的平台")
    print(f"   - 两个视频可以同时保留，根据需要选择使用")

    print(f"\n📝 字幕样式:")
    print(f"   - 字体大小: {subtitle_config['fontSize']}")
    print(f"   - 字体颜色: {subtitle_config['fontColor']}")
    print(f"   - 加粗: {'是' if subtitle_config['bold'] else '否'}")
    print(f"   - 斜体: {'是' if subtitle_config['italic'] else '否'}")
    print(f"   - 描边: {'是' if subtitle_config['outline'] else '否'}")
    print(f"   - 阴影: {'是' if subtitle_config['shadow'] else '否'}")

    print("\n")


if __name__ == "__main__":
    main()
