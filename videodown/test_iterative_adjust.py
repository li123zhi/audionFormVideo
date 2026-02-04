#!/usr/bin/env python3.12
"""
迭代调整剪辑测试 - 按节点逐步调整
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'videorecomp/src'))

from iterative_adjust_clipper import IterativeAdjustClipper


def main():
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║        迭代调整剪辑器 - 按节点逐步调整                    ║
║                                                           ║
║    按顺序对比每条新旧字幕：                                  ║
║    - 计算时间差: 当前开始 - 新开始                          ║
║    - 差值 > 0.5秒: 在节点前剪掉差值                         ║
║    - 差值 < -0.5秒: 在节点前增加差值（冻结帧）              ║
║    - 每次调整后生成新视频                                   ║
║    - 下次对比使用新视频                                     ║
║    - 更新后续所有字幕时间戳                                 ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """)

    if len(sys.argv) < 4:
        print("使用方法:")
        print("  python test_iterative_adjust.py <视频.mp4> <原字幕.srt> <新字幕.srt> [阈值]")
        print("\n示例:")
        print("  python test_iterative_adjust.py video.mp4 original.srt new.srt")
        print("  python test_iterative_adjust.py video.mp4 original.srt new.srt 0.5")
        print("\n算法规则:")
        print("  1. 逐条对比新旧字幕的开始时间")
        print("  2. 计算差值: 当前开始 - 新开始")
        print("  3. 如果差值 > 0.5秒: 在该节点前剪掉差值")
        print("  4. 如果差值 < -0.5秒: 在该节点前增加差值（使用该节点画面）")
        print("  5. 生成新视频，更新后续字幕时间戳")
        print("  6. 下一次对比使用新视频")
        print("\n参数说明:")
        print("  阈值: 触发调整的时间差（默认0.5秒）")
        print("\n预期效果:")
        print("  - 新字幕与视频内容完美同步")
        print("  - 每次调整后立即生成新视频")
        print("  - 逐步逼近新字幕时间轴")
        sys.exit(1)

    video_path = sys.argv[1]
    original_srt = sys.argv[2]
    new_srt = sys.argv[3]
    threshold = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5

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
    print(f"\n开始处理...\n")

    try:
        clipper = IterativeAdjustClipper(
            video_path=video_path,
            original_srt_path=original_srt,
            new_srt_path=new_srt,
            output_dir="output",
            threshold=threshold
        )

        results = clipper.process()

        if results.get('success'):
            print("\n" + "="*60)
            print("✅ 迭代调整成功！")
            print("="*60)

            stats = results.get('stats', {})
            print(f"\n📊 调整统计:")
            print(f"   原视频时长: {stats['original_duration']:.2f}秒")
            print(f"   调整后时长: {stats['final_duration']:.2f}秒")
            print(f"   时长变化: {stats['duration_change']:+.2f}秒")
            print(f"   总调整次数: {stats['total_adjustments']}")
            print(f"   总调整时长: {stats['total_adjustment_time']:+.3f}秒")

            print(f"\n📁 输出文件:")
            print(f"   调整视频: {results['adjusted_video']}")
            print(f"   调整日志: output/iterative_adjustment_log.json")

            # 显示调整记录
            log = stats.get('adjustment_log', [])
            print(f"\n📝 调整详情:")
            for item in log:
                if item['action'] not in ['跳过', '剪掉失败', '增加失败']:
                    print(f"   字幕{item['index']}: {item['action']} {item['adjustment']}")
                    if 'clip_point' in item:
                        print(f"     剪切点: {item['clip_point']}")
                    if 'extend_point' in item:
                        print(f"     延长点: {item['extend_point']}")

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
