#!/usr/bin/env python3.12
"""
简单测试：分析示例字幕的时间差异
"""

from analyze_subtitle_timings import SubtitleTimingAnalyzer


def main():
    print("="*60)
    print("  字幕时间分析测试")
    print("="*60)

    # 使用示例字幕文件
    original_srt = "example_original.srt"
    new_srt = "example_new.srt"

    # 创建分析器
    analyzer = SubtitleTimingAnalyzer(original_srt, new_srt)

    # 加载字幕
    analyzer.load_subtitles()

    # 分析时间差异
    analyzer.analyze_timing_differences()

    # 生成剪辑片段
    segments = analyzer.generate_clip_segments(merge_threshold=0.5)

    # 导出分析报告
    analyzer.export_analysis_report("output/test_analysis_report.json")

    print("\n✅ 测试完成！")
    print("   查看输出目录了解详细分析结果")


if __name__ == "__main__":
    import os
    os.makedirs("output", exist_ok=True)
    main()
