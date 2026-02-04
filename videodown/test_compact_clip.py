#!/usr/bin/env python3.12
"""
紧凑剪辑测试脚本
使用累积偏移算法生成紧凑的视频
"""

import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'videorecomp/src'))

from compact_video_processor import CompactVideoClipper


def main():
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║        紧凑视频剪辑器 - 累积偏移算法                         ║
║                                                           ║
║    通过对比原字幕和新字幕，自动去除多余部分                ║
║    生成更紧凑、更短的视频                                   ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """)

    if len(sys.argv) < 4:
        print("使用方法:")
        print("  python test_compact_clip.py <视频.mp4> <原字幕.srt> <新字幕.srt> [精确模式]")
        print("\n示例:")
        print("  python test_compact_clip.py video.mp4 original.srt new.srt")
        print("  python test_compact_clip.py video.mp4 original.srt new.srt precise")
        print("\n参数说明:")
        print("  视频.mp4    - 原视频文件")
        print("  原字幕.srt   - 原字幕文件（中文）")
        print("  新字幕.srt   - 新字幕文件（英文）")
        print("  精确模式     - 可选，添加'precise'启用精确模式")
        print("\n效果:")
        print("  ✅ 自动计算字幕时间差")
        print("  ✅ 累积偏移，动态调整")
        print("  ✅ 生成紧凑视频（节省10-30%时长）")
        print("  ✅ 导出详细处理日志")
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
        # 创建紧凑剪辑器
        clipper = CompactVideoClipper(
            video_path=video_path,
            original_srt_path=original_srt,
            new_srt_path=new_srt,
            output_dir="output",
            use_precise_seek=use_precise
        )

        # 执行剪辑
        results = clipper.process()

        if results.get('success'):
            print("\n" + "="*60)
            print("✅ 紧凑剪辑成功！")
            print("="*60)

            stats = results.get('stats', {})
            print(f"\n📊 统计信息:")
            print(f"   匹配字幕: {stats.get('matched_subtitles')}/{stats.get('total_subtitles')}")
            print(f"   原视频时长: {stats.get('original_total_duration'):.2f}秒")
            print(f"   新视频时长: {stats.get('new_total_duration'):.2f}秒")
            print(f"   节省时间: {stats.get('time_saved'):.2f}秒")
            print(f"   紧凑比例: {(1 - stats.get('new_total_duration', 0) / max(stats.get('original_total_duration', 1), 1)) * 100:.1f}%")

            print(f"\n📁 输出文件:")
            print(f"   紧凑视频: {results.get('compact_video')}")
            print(f"   处理日志: output/processing_log.json")

            print(f"\n💡 提示:")
            print(f"   - 查看处理日志了解每条字幕的调整")
            print(f"   - 使用视频播放器验证音画同步")
            print(f"   - 如果效果不理想，可以启用精确模式重试")

        else:
            print(f"\n❌ 剪辑失败: {results.get('error')}")
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
