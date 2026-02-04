#!/usr/bin/env python3.12
"""
智能片段剪辑测试 - 保留原视频的自然节奏
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'videorecomp/src'))

from smart_segment_clipper import SmartSegmentClipper


def main():
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║        智能片段剪辑器 - 保留自然节奏                      ║
║                                                           ║
║    通过对比字幕，提取对应内容                                ║
║    保留原视频中字幕间的自然间隙                              ║
║    不压缩时间轴，保持视频流畅                                  ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """)

    if len(sys.argv) < 4:
        print("使用方法:")
        print("  python test_smart_clip.py <视频.mp4> <原字幕.srt> <新字幕.srt>")
        print("\n示例:")
        print("  python test_smart_clip.py video.mp4 chinese.srt english.srt")
        print("\n功能特点:")
        print("  ✅ 提取与新字幕匹配的视频片段")
        print("  ✅ 保留片段间的自然间隙")
        print("  ✅ 不压缩时间轴，保持原视频节奏")
        print("  ✅ 视频流畅，不会卡顿")
        print("\n效果:")
        print("  提取对应内容 + 保留间隙 = 接近原视频时长的同步视频")
        sys.exit(1)

    video_path = sys.argv[1]
    original_srt = sys.argv[2]
    new_srt = sys.argv[3]

    # 验证文件
    for path, desc in [(video_path, "视频"), (original_srt, "原字幕"), (new_srt, "新字幕")]:
        if not os.path.exists(path):
            print(f"❌ {desc}文件不存在: {path}")
            sys.exit(1)

    print(f"原视频: {video_path}")
    print(f"原字幕: {original_srt}")
    print(f"新字幕: {new_srt}")
    print(f"\n开始处理...\n")

    try:
        clipper = SmartSegmentClipper(
            video_path=video_path,
            original_srt_path=original_srt,
            new_srt_path=new_srt,
            output_dir="output"
        )

        results = clipper.process()

        if results.get('success'):
            print("\n" + "="*60)
            print("✅ 智能剪辑成功！")
            print("="*60)

            stats = results.get('stats', {})
            print(f"\n📊 处理统计:")
            print(f"   新字幕总数: {stats.get('total_new_subtitles')}")
            print(f"   成功匹配: {stats.get('matched_segments')}")
            print(f"   匹配率: {stats.get('match_rate')}")
            print(f"   原视频时长: {stats.get('original_video_duration'):.2f}秒")

            print(f"\n📁 输出文件:")
            print(f"   剪辑视频: {results['clipped_video']}")
            print(f"   处理日志: output/smart_clip_log.json")

            print(f"\n💡 特点:")
            print(f"   - 提取了与新字幕匹配的片段")
            print(f"   - 保留了原视频中字幕间的自然间隙")
            print(f"   - 视频流畅，接近原视频时长")
            print(f"   - 新字幕与视频内容对应")
        else:
            print(f"\n❌ 剪辑失败: {results.get('error')}")

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
