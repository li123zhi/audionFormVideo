#!/usr/bin/env python3.12
"""
累积时间差值调整测试 - 按照你的规则精确调整
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'videorecomp/src'))

from cumulative_adjust_clipper import CumulativeTimeAdjustClipper


def main():
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║      累积时间差值调整剪辑器 - 精确按规则处理              ║
║                                                           ║
║    按照新旧字幕的时间差，逐条调整：                              ║
║    - 差值 > 0.5秒: 剪掉这部分时间                                    ║
║    - 差值 < -0.5秒: 增加这部分时间（复制画面）                       ║
║    - 调整后，后续所有字幕时间戳都会改变                            ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """)

    if len(sys.argv) < 4:
        print("使用方法:")
        print("  python test_cumulative_adjust.py <视频.mp4> <原字幕.srt> <新字幕.srt> [阈值] [精确模式]")
        print("\n示例:")
        print("  python test_cumulative_adjust.py video.mp4 original.srt new.srt")
        print("  python test_cumulative_adjust.py video.mp4 original.srt new.srt 0.5")
        print("  python test_cumulative_adjust.py video.mp4 original.srt new.srt 0.3 precise")
        print("\n算法规则:")
        print("  1. 对比每条新旧字幕的开始时间")
        print("  2. 计算差值: 原开始 - 新开始")
        print("  3. 如果差值 > 0.5秒: 剪掉差值")
        print("  4. 如果差值 < -0.5秒: 增加差值（复制画面）")
        print("  5. 更新后续所有字幕的时间戳")
        print("  6. 根据调整后的时间戳提取视频片段")
        print("\n参数说明:")
        print("  阈值: 触发调整的时间差（默认0.5秒）")
        print("  精确模式: 重新编码（更精确但更慢）")
        print("\n预期效果:")
        print("  - 新字幕与视频内容完美同步")
        print("  - 按照你指定的规则精确调整")
        print("  - 每条字幕都独立处理")
        sys.exit(1)

    video_path = sys.argv[1]
    original_srt = sys.argv[2]
    new_srt = sys.argv[3]
    threshold = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5
    use_precise = len(sys.argv) > 5 and sys.argv[5] == 'precise'

    # 验证文件
    for path, desc in [(video_path, "视频"), (original_srt, "原字幕"), (new_srt, "新字幕")]:
        if not os.path.exists(path):
            print(f"❌ {desc}文件不存在: {path}")
            sys.exit(1)

    print(f"配置:")
    print(f"  视频: {video_path}")
    print(f"  原字幕: {original_srt}")
    print(f"  新字幕: {new_srt}")
    print(f"  时间差阈值: {threshold}秒")
    print(f"  精确模式: {'启用' if use_precise else '关闭（快速）'}")
    print(f"\n开始处理...\n")

    try:
        clipper = CumulativeTimeAdjustClipper(
            video_path=video_path,
            original_srt_path=original_srt,
            new_srt_path=new_srt,
            output_dir="output",
            threshold=threshold,
            use_precise_seek=use_precise
        )

        results = clipper.process()

        if results.get('success'):
            print("\n" + "="*60)
            print("✅ 累积时间差值调整成功！")
            print("="*60)

            stats = results.get('stats', {})
            print(f"\n📊 调整统计:")
            print(f"   总字幕数: {stats['total_subtitles']}")
            print(f"   需要调整: {stats['total_adjustments']}")
            print(f"   总调整时长: {stats['total_adjustment_time']:+.3f}秒")
            print(f"   原视频时长: {stats['original_video_duration']:.2f}秒")

            print(f"\n📁 输出文件:")
            print(f"   调整视频: {results['adjusted_video']}")
            print(f"   调整日志: output/adjustment_log.json")

            # 显示前几个调整记录
            log = stats.get('adjustment_log', [])
            print(f"\n📝 调整详情（前5条）:")
            for item in log[:5]:
                print(f"   字幕{item['index']}: {item['action']} {item['adjustment']}")
                print(f"     {item['new_text']}")
                print(f"     原字幕: {item['original_text']}")

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
