#!/usr/bin/env python3.12
"""
快速开始示例：根据新字幕重新剪辑视频

这个脚本演示了如何使用字幕时间分析工具和视频重新剪辑工具
来达到更好的音画同步效果。
"""

import os
import sys
from pathlib import Path


def print_section(title: str):
    """打印章节标题"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)


def step1_analyze_subtitles(original_srt: str, new_srt: str):
    """
    步骤1：分析字幕时间差异
    """
    print_section("步骤1：分析字幕时间差异")

    from analyze_subtitle_timings import SubtitleTimingAnalyzer

    # 创建分析器
    analyzer = SubtitleTimingAnalyzer(original_srt, new_srt)

    # 加载字幕
    analyzer.load_subtitles()

    # 分析时间差异
    analyzer.analyze_timing_differences()

    # 生成剪辑片段
    segments = analyzer.generate_clip_segments(merge_threshold=0.5)

    # 导出分析报告
    analyzer.export_analysis_report("output/subtitle_analysis_report.json")

    print("\n✅ 分析完成！查看报告了解详细信息")

    return analyzer


def step2_reclip_video(video_path: str, new_srt: str, output_dir: str = "output"):
    """
    步骤2：重新剪辑视频
    """
    print_section("步骤2：根据新字幕重新剪辑视频")

    from reclip_video_by_subtitles import VideoReclipper

    # 创建剪辑器
    clipper = VideoReclipper(
        video_path=video_path,
        new_subtitle_path=new_srt,
        output_dir=output_dir
    )

    # 执行剪辑
    results = clipper.process(
        merge_gap=0.5,        # 合并0.5秒以内的间隙
        embed_subtitle=True,  # 嵌入字幕
        hard_subtitle=False   # 使用软字幕
    )

    if results:
        print("\n✅ 视频剪辑完成！生成文件：")
        for name, path in results.items():
            print(f"   - {name}: {path}")

    return results


def verify_results(results: dict):
    """
    验证结果
    """
    print_section("验证结果")

    if not results:
        print("❌ 没有生成任何文件")
        return

    for name, path in results.items():
        if path and os.path.exists(path):
            size = os.path.getsize(path) / (1024 * 1024)  # MB
            print(f"✅ {name}: {os.path.basename(path)} ({size:.2f} MB)")
        else:
            print(f"❌ {name}: 文件不存在")


def main():
    """主函数"""
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║        视频重新剪辑工具 - 快速开始示例                      ║
║                                                           ║
║    根据新字幕时间戳重新剪辑视频，达到音画同步效果            ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """)

    # 检查命令行参数
    if len(sys.argv) < 4:
        print("使用方法:")
        print("  python quick_start_example.py <原视频.mp4> <原字幕.srt> <新字幕.srt>")
        print("\n示例:")
        print("  python quick_start_example.py video.mp4 original.srt new.srt")
        print("\n这个脚本将：")
        print("  1. 分析两个字幕的时间差异")
        print("  2. 根据新字幕时间戳重新剪辑视频")
        print("  3. 嵌入新字幕到剪辑后的视频")
        print("\n输出文件将保存在 output/ 目录")
        sys.exit(1)

    video_path = sys.argv[1]
    original_srt = sys.argv[2]
    new_srt = sys.argv[3]

    # 验证文件存在
    for path, desc in [(video_path, "视频"), (original_srt, "原字幕"), (new_srt, "新字幕")]:
        if not os.path.exists(path):
            print(f"❌ {desc}文件不存在: {path}")
            sys.exit(1)

    # 创建输出目录
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    print(f"原视频: {video_path}")
    print(f"原字幕: {original_srt}")
    print(f"新字幕: {new_srt}")
    print(f"输出目录: {output_dir}")

    try:
        # 步骤1：分析字幕时间差异
        analyzer = step1_analyze_subtitles(original_srt, new_srt)

        # 步骤2：重新剪辑视频
        results = step2_reclip_video(video_path, new_srt, str(output_dir))

        # 验证结果
        verify_results(results)

        print_section("完成")
        print("✅ 所有步骤完成！")
        print(f"\n请检查 output/ 目录中的文件")
        print("建议使用视频播放器验证音画同步效果")

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
