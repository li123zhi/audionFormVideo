#!/usr/bin/env python3.12
"""
字幕时间分析工具
分析原字幕和新字幕的时间戳差异，生成视频剪辑方案
"""

import os
import pysrt
from pathlib import Path
import json


class SubtitleTimingAnalyzer:
    """字幕时间分析器"""

    def __init__(self, original_srt_path: str, new_srt_path: str):
        """
        初始化分析器

        Args:
            original_srt_path: 原字幕文件路径（中文）
            new_srt_path: 新字幕文件路径（英文）
        """
        self.original_srt_path = original_srt_path
        self.new_srt_path = new_srt_path
        self.original_subs = None
        self.new_subs = None
        self.timing_diffs = []

    def load_subtitles(self):
        """加载两个字幕文件"""
        print("加载字幕文件...")
        self.original_subs = pysrt.open(self.original_srt_path)
        self.new_subs = pysrt.open(self.new_srt_path)

        print(f"原字幕: {len(self.original_subs)} 条")
        print(f"新字幕: {len(self.new_subs)} 条")

    def analyze_timing_differences(self):
        """分析时间戳差异"""
        print("\n分析时间戳差异...")

        # 确保字幕数量匹配
        min_count = min(len(self.original_subs), len(self.new_subs))

        for i in range(min_count):
            orig_sub = self.original_subs[i]
            new_sub = self.new_subs[i]

            orig_start = orig_sub.start.ordinal / 1000.0
            orig_end = orig_sub.end.ordinal / 1000.0
            orig_duration = orig_end - orig_start

            new_start = new_sub.start.ordinal / 1000.0
            new_end = new_sub.end.ordinal / 1000.0
            new_duration = new_end - new_start

            start_diff = new_start - orig_start
            end_diff = new_end - orig_end
            duration_diff = new_duration - orig_duration

            self.timing_diffs.append({
                'index': i + 1,
                'original_text': orig_sub.text,
                'new_text': new_sub.text,
                'original_start': orig_start,
                'original_end': orig_end,
                'original_duration': orig_duration,
                'new_start': new_start,
                'new_end': new_end,
                'new_duration': new_duration,
                'start_diff': start_diff,
                'end_diff': end_diff,
                'duration_diff': duration_diff
            })

        # 打印统计信息
        start_diffs = [d['start_diff'] for d in self.timing_diffs]
        duration_diffs = [d['duration_diff'] for d in self.timing_diffs]

        print(f"\n时间偏移统计:")
        print(f"  开始时间偏移: 最小={min(start_diffs):.3f}s, 最大={max(start_diffs):.3f}s, 平均={sum(start_diffs)/len(start_diffs):.3f}s")
        print(f"  持续时间偏移: 最小={min(duration_diffs):.3f}s, 最大={max(duration_diffs):.3f}s, 平均={sum(duration_diffs)/len(duration_diffs):.3f}s")

    def generate_clip_segments(self, merge_threshold=2.0) -> list:
        """
        生成视频剪辑片段列表

        Args:
            merge_threshold: 合并相邻片段的阈值（秒）

        Returns:
            片段列表 [(start, end), ...]
        """
        print(f"\n生成视频剪辑片段（合并阈值: {merge_threshold}秒）...")

        segments = []

        # 根据新字幕的时间戳生成片段
        for i, diff in enumerate(self.timing_diffs):
            start_time = diff['new_start']
            end_time = diff['new_end']

            # 确保时间有效
            if end_time > start_time:
                segments.append((start_time, end_time))

        # 合并相邻或接近的片段
        if segments:
            merged_segments = []
            current_start, current_end = segments[0]

            for start, end in segments[1:]:
                if start - current_end <= merge_threshold:
                    # 合并片段
                    current_end = end
                else:
                    merged_segments.append((current_start, current_end))
                    current_start, current_end = start, end

            merged_segments.append((current_start, current_end))

            print(f"\n生成了 {len(merged_segments)} 个视频片段:")
            for i, (start, end) in enumerate(merged_segments):
                print(f"  片段{i+1}: {start:.3f}s - {end:.3f}s (时长: {end-start:.3f}s)")

            return merged_segments

        return segments

    def export_ffmpeg_commands(self, video_path: str, output_dir: str = "output"):
        """
        导出FFmpeg命令用于剪辑视频

        Args:
            video_path: 原视频路径
            output_dir: 输出目录
        """
        segments = self.generate_clip_segments()

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 生成临时片段文件路径
        segment_files = []
        for i, (start, end) in enumerate(segments):
            segment_file = output_path / f"segment_{i:03d}.mp4"
            segment_files.append(str(segment_file))

            # 生成分片命令
            cmd = f"ffmpeg -y -ss {start:.3f} -i \"{video_path}\" -t {end-start:.3f} -c copy -avoid_negative_ts 1 \"{segment_file}\""
            print(f"\n片段{i+1}提取命令:")
            print(cmd)

        # 生成拼接列表文件
        concat_file = output_path / "concat_list.txt"
        with open(concat_file, 'w') as f:
            for segment_file in segment_files:
                f.write(f"file '{segment_file}'\n")

        # 生成最终拼接命令
        final_output = output_path / "clipped_video.mp4"
        concat_cmd = f"ffmpeg -y -f concat -safe 0 -i \"{concat_file}\" -c copy \"{final_output}\""
        print(f"\n拼接命令:")
        print(concat_cmd)

        print(f"\n✅ FFmpeg命令已生成，请按顺序执行以上命令")

    def export_analysis_report(self, output_path: str = "subtitle_analysis_report.json"):
        """导出分析报告"""
        report = {
            'original_subtitle': self.original_srt_path,
            'new_subtitle': self.new_srt_path,
            'original_count': len(self.original_subs) if self.original_subs else 0,
            'new_count': len(self.new_subs) if self.new_subs else 0,
            'timing_differences': self.timing_diffs,
            'summary': {
                'total_subtitles': len(self.timing_diffs),
                'avg_start_diff': sum(d['start_diff'] for d in self.timing_diffs) / len(self.timing_diffs) if self.timing_diffs else 0,
                'avg_duration_diff': sum(d['duration_diff'] for d in self.timing_diffs) / len(self.timing_diffs) if self.timing_diffs else 0,
            }
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 分析报告已保存到: {output_path}")


def main():
    """主函数"""
    import sys

    if len(sys.argv) < 3:
        print("使用方法:")
        print("  python analyze_subtitle_timings.py <原字幕.srt> <新字幕.srt> [视频文件.mp4]")
        print("\n示例:")
        print("  python analyze_subtitle_timings.py original.srt new.srt video.mp4")
        sys.exit(1)

    original_srt = sys.argv[1]
    new_srt = sys.argv[2]
    video_file = sys.argv[3] if len(sys.argv) > 3 else None

    # 创建分析器
    analyzer = SubtitleTimingAnalyzer(original_srt, new_srt)

    # 加载字幕
    analyzer.load_subtitles()

    # 分析时间差异
    analyzer.analyze_timing_differences()

    # 生成剪辑片段
    analyzer.generate_clip_segments()

    # 导出分析报告
    analyzer.export_analysis_report()

    # 如果提供了视频文件，生成FFmpeg命令
    if video_file:
        analyzer.export_ffmpeg_commands(video_file)


if __name__ == "__main__":
    main()
