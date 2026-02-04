#!/usr/bin/env python3.12
"""
视频重新生成工具 - 主程序入口
"""

import argparse
import sys
import os
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.video_processor import create_video_recomposer


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='视频重新生成工具 - 将原视频与新配音和字幕合并',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 基本用法
  python main.py -v video.mp4 -s subtitles.srt -a audio.zip

  # 指定输出目录
  python main.py -v video.mp4 -s subtitles.srt -a audio.zip -o my_output

  # 使用相对路径
  python main.py -v input/original.mp4 -s subs/translated.srt -a voiceover.zip
        """
    )

    parser.add_argument(
        '-v', '--video',
        required=True,
        help='原视频文件路径 (mp4, avi, mov等)'
    )

    parser.add_argument(
        '-s', '--srt',
        required=True,
        help='SRT字幕文件路径'
    )

    parser.add_argument(
        '-a', '--audio',
        required=True,
        help='配音ZIP文件路径 (包含mp3/mp4等音频文件)'
    )

    parser.add_argument(
        '-o', '--output',
        default='output',
        help='输出目录 (默认: output)'
    )

    parser.add_argument(
        '--keep-temp',
        action='store_true',
        help='保留临时文件 (用于调试)'
    )

    parser.add_argument(
        '--font-size',
        type=int,
        default=32,
        help='字幕字体大小 (默认: 32)'
    )

    parser.add_argument(
        '--margin-v',
        type=int,
        default=100,
        help='字幕底部边距 (默认: 100)'
    )

    parser.add_argument(
        '--outline',
        type=int,
        default=0,
        help='字幕描边宽度 (默认: 0，无描边)'
    )

    parser.add_argument(
        '--text-color',
        default='&HFFFFFF',
        help='字幕颜色 (ASS格式, 默认: &HFFFFFF 白色)'
    )

    parser.add_argument(
        '--outline-color',
        default='&H000000',
        help='描边颜色 (ASS格式, 默认: &H000000 黑色)'
    )

    parser.add_argument(
        '--extract-audio',
        action='store_true',
        help='提取原视频的所有音轨并保存为ZIP文件（默认已启用）'
    )

    parser.add_argument(
        '--separate-audio',
        action='store_true',
        help='（已废弃）AI 音频分离现在默认自动执行'
    )

    args = parser.parse_args()

    # 转换为绝对路径
    video_path = os.path.abspath(args.video)
    srt_path = os.path.abspath(args.srt)
    audio_path = os.path.abspath(args.audio)
    output_dir = os.path.abspath(args.output)

    # 验证文件
    if not os.path.exists(video_path):
        print(f"错误: 视频文件不存在: {video_path}")
        sys.exit(1)

    if not os.path.exists(srt_path):
        print(f"错误: 字幕文件不存在: {srt_path}")
        sys.exit(1)

    if not os.path.exists(audio_path):
        print(f"错误: 配音ZIP文件不存在: {audio_path}")
        sys.exit(1)

    if not audio_path.lower().endswith('.zip'):
        print(f"警告: 配音文件可能不是ZIP格式: {audio_path}")

    try:
        print("=" * 60)
        print("视频重新生成工具")
        print("=" * 60)
        print(f"原视频: {video_path}")
        print(f"字幕文件: {srt_path}")
        print(f"配音文件: {audio_path}")
        print(f"输出目录: {output_dir}")
        print("=" * 60)
        print()

        # 创建字幕样式配置
        subtitle_style = {
            'font_size': args.font_size,
            'margin_v': args.margin_v,
            'outline': args.outline,
            'primary_colour': args.text_color,
            'outline_colour': args.outline_color,
        }

        # 创建处理器
        recomposer = create_video_recomposer(
            original_video=video_path,
            srt_file=srt_path,
            audio_zip=audio_path,
            output_dir=output_dir,
            subtitle_style=subtitle_style,
            enable_ai_separation=args.separate_audio
        )

        # 提取原视频音轨（默认已启用）
        # AI 音频分离（可选）

        # 执行处理
        hard_subtitle_path, soft_subtitle_path, no_subtitle_path, merged_audio_path, mixed_audio_path = recomposer.process()

        print()
        print("=" * 60)
        print("处理成功完成！")
        print("=" * 60)
        print(f"输出文件:")
        print(f"  - 硬字幕视频: {hard_subtitle_path}")
        print(f"  - 软字幕视频: {soft_subtitle_path}")
        print(f"  - 不带字幕视频: {no_subtitle_path}")
        if mixed_audio_path:
            print(f"  - 伴奏混合音频: {mixed_audio_path}")
        print(f"  - 仅配音音频: {merged_audio_path}")
        print("=" * 60)

        # 清理临时文件
        if not args.keep_temp:
            recomposer.cleanup()

    except KeyboardInterrupt:
        print("\n\n操作已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
