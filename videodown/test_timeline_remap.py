#!/usr/bin/env python3.12
"""
时间轴重映射测试 - 按照新字幕时间轴重新组织视频
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'videorecomp/src'))

from timeline_remap_clipper import TimelineRemapClipper


def main():
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║        时间轴重映射剪辑器 - 按新字幕时间轴组织            ║
║                                                           ║
║    匹配每条新字幕到原视频                                    ║
║    按照新字幕的时间轴提取片段                                ║
║    拼接成新视频，时长匹配新字幕                               ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """)

    if len(sys.argv) < 4:
        print("使用方法:")
        print("  python test_timeline_remap.py <视频.mp4> <原字幕.srt> <新字幕.srt>")
        print("\n示例:")
        print("  python test_timeline_remap.py video.mp4 original.srt new.srt")
        print("\n算法规则:")
        print("  1. 为每条新字幕在原字幕中找匹配（基于文本相似度）")
        print("  2. 提取原视频中对应的片段")
        print("  3. 按照新字幕的时间轴排列片段")
        print("  4. 拼接成新视频")
        print("\n预期效果:")
        print("  - 新视频时长接近新字幕总时长")
        print("  - 如果新字幕比原字幕短，新视频也比原视频短")
        print("  - 内容与新字幕匹配")
        sys.exit(1)

    video_path = sys.argv[1]
    original_srt = sys.argv[2]
    new_srt = sys.argv[3]

    # 验证文件
    for path, desc in [(video_path, "视频"), (original_srt, "原字幕"), (new_srt, "新字幕")]:
        if not os.path.exists(path):
            print(f"❌ {desc}文件不存在: {path}")
            sys.exit(1)

    print(f"配置:")
    print(f"  视频: {video_path}")
    print(f"  原字幕: {original_srt}")
    print(f"  新字幕: {new_srt}")
    print(f"\n开始处理...\n")

    try:
        clipper = TimelineRemapClipper(
            video_path=video_path,
            original_srt_path=original_srt,
            new_srt_path=new_srt,
            output_dir="output"
        )

        results = clipper.process()

        if results.get('success'):
            print("\n" + "="*60)
            print("✅ 时间轴重映射成功！")
            print("="*60)

            stats = results.get('stats', {})
            print(f"\n📊 处理统计:")
            print(f"   新字幕总数: {stats['total_new_subtitles']}")
            print(f"   成功匹配: {stats['matched_segments']}")
            print(f"   匹配率: {stats['match_rate']}")
            print(f"   原视频/字幕时长: {stats['original_video_duration']:.2f}秒")
            print(f"   新字幕总时长: {stats['new_subtitle_total_duration']:.2f}秒")

            print(f"\n📁 输出文件:")
            print(f"   重映射视频: {results['remapped_video']}")
            print(f"   处理日志: output/timeline_remap_log.json")

            print(f"\n💡 效果:")
            print(f"   - 新视频时长: {results['final_duration']:.2f}秒")
            print(f"   - 原视频时长: {results['original_duration']:.2f}秒")
            print(f"   - 时长变化: {results['duration_change']:+.2f}秒")
        else:
            print(f"\n❌ 处理失败: {results.get('error')}")

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
