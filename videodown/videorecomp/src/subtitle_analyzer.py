#!/usr/bin/env python3.12
"""
增强的字幕分析器 - 提供详细的时间分析和可视化数据
"""

import pysrt
import chardet
from typing import List, Dict, Tuple
import json


class SubtitleAnalyzer:
    """字幕时间分析器 - 增强版"""

    def __init__(self, original_srt_path: str = None, new_srt_path: str = None):
        """
        初始化分析器

        Args:
            original_srt_path: 原字幕文件路径（可选）
            new_srt_path: 新字幕文件路径（可选）
        """
        self.original_srt_path = original_srt_path
        self.new_srt_path = new_srt_path
        self.original_subs = None
        self.new_subs = None
        self.analysis_result = {}

    def load_subtitle(self, srt_path: str) -> pysrt.SubRipFile:
        """加载单个字幕文件"""
        # 检测编码
        with open(srt_path, 'rb') as f:
            raw_data = f.read()
            result = chardet.detect(raw_data)
            encoding = result['encoding'] or 'utf-8'

        # 加载字幕
        subs = pysrt.open(srt_path, encoding=encoding)
        return subs

    def load_subtitles(self):
        """加载字幕文件"""
        if self.original_srt_path:
            print(f"加载原字幕: {self.original_srt_path}")
            self.original_subs = self.load_subtitle(self.original_srt_path)

        if self.new_srt_path:
            print(f"加载新字幕: {self.new_srt_path}")
            self.new_subs = self.load_subtitle(self.new_srt_path)

    def analyze_single_subtitle(self, subs: pysrt.SubRipFile) -> Dict:
        """分析单个字幕文件的时间特征"""
        if not subs or len(subs) == 0:
            return {}

        # 计算时间间隔
        gaps = []
        durations = []
        for i in range(len(subs)):
            sub = subs[i]
            start = sub.start.ordinal / 1000.0
            end = sub.end.ordinal / 1000.0
            duration = end - start
            durations.append(duration)

            if i > 0:
                prev_end = subs[i-1].end.ordinal / 1000.0
                gap = start - prev_end
                gaps.append(gap)

        return {
            'count': len(subs),
            'total_duration': subs[-1].end.ordinal / 1000.0,
            'avg_duration': sum(durations) / len(durations) if durations else 0,
            'min_duration': min(durations) if durations else 0,
            'max_duration': max(durations) if durations else 0,
            'avg_gap': sum(gaps) / len(gaps) if gaps else 0,
            'min_gap': min(gaps) if gaps else 0,
            'max_gap': max(gaps) if gaps else 0,
        }

    def compare_subtitles(self) -> Dict:
        """
        对比原字幕和新字幕的时间差异

        Returns:
            详细的分析结果字典
        """
        if not self.original_subs or not self.new_subs:
            return {'error': '需要加载两个字幕文件才能对比'}

        # 获取最小数量
        min_count = min(len(self.original_subs), len(self.new_subs))

        details = []
        start_diffs = []
        duration_diffs = []
        end_diffs = []

        for i in range(min_count):
            orig_sub = self.original_subs[i]
            new_sub = self.new_subs[i]

            orig_start = orig_sub.start.ordinal / 1000.0
            orig_end = orig_sub.end.ordinal / 1000.0
            orig_duration = orig_end - orig_start
            orig_text = orig_sub.text

            new_start = new_sub.start.ordinal / 1000.0
            new_end = new_sub.end.ordinal / 1000.0
            new_duration = new_end - new_start
            new_text = new_sub.text

            start_diff = new_start - orig_start
            end_diff = new_end - orig_end
            duration_diff = new_duration - orig_duration

            start_diffs.append(start_diff)
            end_diffs.append(end_diff)
            duration_diffs.append(duration_diff)

            details.append({
                'index': i + 1,
                'original': {
                    'text': orig_text,
                    'start': round(orig_start, 3),
                    'end': round(orig_end, 3),
                    'duration': round(orig_duration, 3)
                },
                'new': {
                    'text': new_text,
                    'start': round(new_start, 3),
                    'end': round(new_end, 3),
                    'duration': round(new_duration, 3)
                },
                'differences': {
                    'start_diff': round(start_diff, 3),
                    'end_diff': round(end_diff, 3),
                    'duration_diff': round(duration_diff, 3)
                }
            })

        # 统计信息
        analysis = {
            'summary': {
                'original_count': len(self.original_subs),
                'new_count': len(self.new_subs),
                'compared_count': min_count,
                'start_offset': {
                    'min': round(min(start_diffs), 3) if start_diffs else 0,
                    'max': round(max(start_diffs), 3) if start_diffs else 0,
                    'avg': round(sum(start_diffs) / len(start_diffs), 3) if start_diffs else 0,
                },
                'duration_offset': {
                    'min': round(min(duration_diffs), 3) if duration_diffs else 0,
                    'max': round(max(duration_diffs), 3) if duration_diffs else 0,
                    'avg': round(sum(duration_diffs) / len(duration_diffs), 3) if duration_diffs else 0,
                },
                'end_offset': {
                    'min': round(min(end_diffs), 3) if end_diffs else 0,
                    'max': round(max(end_diffs), 3) if end_diffs else 0,
                    'avg': round(sum(end_diffs) / len(end_diffs), 3) if end_diffs else 0,
                }
            },
            'details': details
        }

        self.analysis_result = analysis
        return analysis

    def generate_visualization_data(self) -> Dict:
        """
        生成前端可视化所需的数据

        Returns:
            可视化数据字典
        """
        if not self.analysis_result:
            self.compare_subtitles()

        details = self.analysis_result.get('details', [])

        # 时间轴数据
        timeline_data = []
        for detail in details:
            timeline_data.append({
                'index': detail['index'],
                'original_start': detail['original']['start'],
                'original_end': detail['original']['end'],
                'new_start': detail['new']['start'],
                'new_end': detail['new']['end'],
                'original_text': detail['original']['text'][:50] + '...' if len(detail['original']['text']) > 50 else detail['original']['text'],
                'new_text': detail['new']['text'][:50] + '...' if len(detail['new']['text']) > 50 else detail['new']['text'],
            })

        # 偏移分布数据
        start_diffs = [d['differences']['start_diff'] for d in details]
        duration_diffs = [d['differences']['duration_diff'] for d in details]

        # 创建直方图数据
        def create_histogram(data, bin_count=20):
            if not data:
                return {'bins': [], 'counts': []}

            min_val = min(data)
            max_val = max(data)
            bin_size = (max_val - min_val) / bin_count

            bins = [round(min_val + i * bin_size, 3) for i in range(bin_count + 1)]
            counts = [0] * bin_count

            for val in data:
                bin_idx = min(int((val - min_val) / bin_size), bin_count - 1)
                counts[bin_idx] += 1

            return {
                'bins': bins,
                'counts': counts,
                'min': round(min_val, 3),
                'max': round(max_val, 3),
                'avg': round(sum(data) / len(data), 3)
            }

        return {
            'timeline': timeline_data,
            'start_diff_histogram': create_histogram(start_diffs),
            'duration_diff_histogram': create_histogram(duration_diffs),
            'summary': self.analysis_result.get('summary', {})
        }

    def recommend_clip_parameters(self) -> Dict:
        """
        基于分析结果推荐剪辑参数

        Returns:
            推荐参数字典
        """
        if not self.analysis_result:
            self.compare_subtitles()

        summary = self.analysis_result.get('summary', {})
        start_offset = summary.get('start_offset', {})
        duration_offset = summary.get('duration_offset', {})

        # 计算推荐的合并间隙
        avg_gap = abs(start_offset.get('avg', 0))
        max_gap = abs(start_offset.get('max', 0))

        # 推荐策略
        if avg_gap < 0.3:
            merge_gap = 0.5
            reason = "时间偏移较小，使用小间隙保持精确度"
        elif avg_gap < 1.0:
            merge_gap = 1.0
            reason = "时间偏移中等，平衡流畅度和精确度"
        else:
            merge_gap = 2.0
            reason = "时间偏移较大，使用大间隙确保流畅性"

        # 推荐剪辑策略
        if duration_offset.get('avg', 0) > 0:
            strategy = "新字幕较长，建议保留更多画面"
        elif duration_offset.get('avg', 0) < 0:
            strategy = "新字幕较短，建议紧凑剪辑"
        else:
            strategy = "时长相近，标准剪辑策略"

        return {
            'merge_gap': merge_gap,
            'reason': reason,
            'strategy': strategy,
            'confidence': 'high' if avg_gap < 0.5 else 'medium' if avg_gap < 1.5 else 'low',
            'statistics': {
                'avg_start_offset': start_offset.get('avg', 0),
                'max_start_offset': start_offset.get('max', 0),
                'avg_duration_change': duration_offset.get('avg', 0),
            }
        }

    def export_report(self, output_path: str = None):
        """导出分析报告为JSON"""
        if not self.analysis_result:
            self.compare_subtitles()

        report = {
            'analysis': self.analysis_result,
            'visualization': self.generate_visualization_data(),
            'recommendations': self.recommend_clip_parameters()
        }

        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)

        return report


def analyze_subtitles_for_api(original_srt: str, new_srt: str) -> Dict:
    """
    API专用：分析字幕并返回完整报告

    Args:
        original_srt: 原字幕文件路径
        new_srt: 新字幕文件路径

    Returns:
        分析报告字典
    """
    analyzer = SubtitleAnalyzer(original_srt, new_srt)
    analyzer.load_subtitles()
    report = analyzer.export_report()
    return report
