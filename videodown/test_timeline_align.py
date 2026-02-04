#!/usr/bin/env python3.12
"""
时间轴对齐测试脚本
以新字幕时间轴为基准，剪辑原视频，让视频与字幕完美同步
"""

import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'videorecomp/src'))

from timeline_aligner import TimelineAligner


def main():
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║        时间轴对齐剪辑器 - 字幕同步专家                      ║
║                                                           ║
║    以新字幕时间轴为基准，剪辑原视频                           ║
║    让新视频与新字幕完美同步                                  ║
║    保留字幕间的自然间隙                                      ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """)

    if len(sys.argv) < 4:
        print("使用方法:")
        print("  python test_timeline_align.py <视频.mp4> <原字幕.srt> <新字幕.srt> [精确模式]")
        print("\n示例:")
        print("  python test_timeline_align.py video.mp4 original.srt new.srt")
        print("  python test_timeline_align.py video.mp4 original.srt new.srt precise")
        print("\n参数说明:")
        print("  视频.mp4    - 原视频文件")
        print("  原字幕.srt   - 原字幕文件（中文）")
        print("  新字幕.srt   - 新字幕文件（英文）")
        print("  精确模式     - 可选，添加'precise'启用精确模式")
        print("\n功能特点:")
        print("  ✅ 以新字幕时间轴为基准")
        print("  ✅ 智能匹配原视频中的对应内容")
        print("  ✅ 提取并拼接匹配的片段")
        print("  ✅ 保留字幕间的自然间隙")
        print("  ✅ 新字幕与视频完美同步")
        print("\n效果:")
        print("  新字幕显示的时间  ↔  视频中角色说话的时间")
        print("  完美对应，同步一致！")
        sys.exit(1)

    video_path = sys.argv[1]
    original_srt = sys.argv[2]
    new_srt = sys.argv[3]
    use_precise = len(sys.argv) > 4 and sys.argv[4] == 'precise'

    # 验证文件存在
    for path, desc in [(video_path, "视频"), (original_srt, "原字幕"), (new_srt, "新字幕")]:
        if not os.path.exists(path):
            print(f"❌ {desc}文件不存在: {path}")
            sys.exit(1)

    print(f"原视频: {video_path}")
    print(f"原字幕: {original_srt}")
    print(f"新字幕: {new_srt}")
    print(f"精确模式: {'启用' if use_precise else '关闭（快速）'}")
    print(f"\n开始处理...\n")

    try:
        # 创建时间轴对齐器
        aligner = TimelineAligner(
            video_path=video_path,
            original_srt_path=original_srt,
            new_srt_path=new_srt,
            output_dir="output",
            use_precise_seek=use_precise
        )

        # 执行对齐
        results = aligner.process()

        if results.get('success'):
            print("\n" + "="*60)
            print("✅ 时间轴对齐成功！")
            print("="*60)

            stats = results.get('stats', {})
            print(f"\n📊 对齐统计:")
            print(f"   新字幕总数: {stats.get('total_new_subtitles')}")
            print(f"   成功匹配: {stats.get('matched_segments')}")
            print(f"   匹配率: {stats.get('match_rate')}")
            print(f"   新字幕总时长: {stats.get('new_subtitle_total_duration'):.2f}秒")
            print(f"   提取片段数: {stats.get('extracted_segments_count')}")

            print(f"\n📁 输出文件:")
            print(f"   对齐视频: {results.get('aligned_video')}")
            print(f"   对齐日志: output/alignment_log.json")

            print(f"\n💡 使用说明:")
            print(f"   - 对齐后的视频已保存到: {results.get('aligned_video')}")
            print(f"   - 将新字幕文件与该视频一起使用")
            print(f"   - 新字幕的时间与视频内容完美同步")
            print(f"   - 角色说话时字幕正好出现")

            print(f"\n🎬 验证同步:")
            print(f"   1. 播放对齐后的视频")
            print(f"   2. 加载新字幕文件")
            print(f"   3. 检查字幕与说话是否同步")
            print(f"   4. 如果不同步，可以启用精确模式重试")

        else:
            print(f"\n❌ 对齐失败: {results.get('error')}")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 处理出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
