#!/usr/bin/env python3.12
"""
累积时间差值调整剪辑器
按照新旧字幕的时间差，累积剪掉或增加时长
"""

import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import pysrt
import chardet
from tqdm import tqdm


class CumulativeTimeAdjustClipper:
    """累积时间差值调整剪辑器"""

    def __init__(
        self,
        video_path: str,
        original_srt_path: str,
        new_srt_path: str,
        output_dir: str = "output",
        threshold: float = 0.5,
        use_precise_seek: bool = False
    ):
        """
        初始化剪辑器

        Args:
            video_path: 原视频路径
            original_srt_path: 原字幕路径
            new_srt_path: 新字幕路径
            output_dir: 输出目录
            threshold: 时间差阈值（秒，默认0.5）
            use_precise_seek: 是否使用精确seek
        """
        self.video_path = video_path
        self.original_srt_path = original_srt_path
        self.new_srt_path = new_srt_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.threshold = threshold
        self.use_precise_seek = use_precise_seek

        self.temp_dir = Path(tempfile.mkdtemp(prefix="cumulative_adjust_"))
        self.original_subs = None
        self.new_subs = None

    def load_subtitle(self, srt_path: str) -> pysrt.SubRipFile:
        """加载字幕文件"""
        with open(srt_path, 'rb') as f:
            raw_data = f.read()
            result = chardet.detect(raw_data)
            encoding = result['encoding'] or 'utf-8'
        return pysrt.open(srt_path, encoding=encoding)

    def load_subtitles(self):
        """加载字幕文件"""
        print("加载字幕文件...")
        self.original_subs = self.load_subtitle(self.original_srt_path)
        self.new_subs = self.load_subtitle(self.new_srt_path)
        print(f"原字幕: {len(self.original_subs)} 条")
        print(f"新字幕: {len(self.new_subs)} 条")
        print(f"时间差阈值: {self.threshold}秒")

    def get_video_duration(self) -> float:
        """获取视频时长"""
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', self.video_path]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            import json
            info = json.loads(result.stdout)
            return float(info['format']['duration'])
        except:
            return 0.0

    def calculate_adjusted_segments(self) -> Tuple[List[Tuple[float, float]], Dict]:
        """
        计算累积调整后的片段

        算法：
        1. 对于每条字幕，计算时间差：旧字幕开始 - 新字幕开始
        2. 如果差值 > 阈值：剪掉这个差值（累积剪裁）
        3. 如果差值 < -阈值：增加这个差值（复制前面的画面填充）
        4. 调整后续所有字幕的时间戳
        5. 根据调整后的时间戳提取片段

        Returns:
            (片段列表, 统计信息)
        """
        if not self.original_subs or not self.new_subs:
            self.load_subtitles()

        video_duration = self.get_video_duration()

        # 创建调整后的字幕副本
        adjusted_original = []

        print("\n计算累积时间差值调整...")

        cumulative_offset = 0.0  # 累积时间偏移
        adjustment_log = []

        # 使用新字幕的数量，确保每个新字幕都有对应的旧字幕
        min_count = min(len(self.original_subs), len(self.new_subs))

        for i in range(min_count):
            orig_sub = self.original_subs[i]
            new_sub = self.new_subs[i]

            orig_start = orig_sub.start.ordinal / 1000.0
            orig_end = orig_sub.end.ordinal / 1000.0
            orig_duration = orig_end - orig_start

            new_start = new_sub.start.ordinal / 1000.0
            new_end = new_sub.end.ordinal / 1000.0

            # 计算时间差：旧字幕开始 - 新字幕开始
            time_diff = orig_start - new_start

            print(f"\n字幕{i+1}:")
            print(f"  原字幕: {orig_start:.3f}s - {orig_end:.3f}s ({orig_sub.text[:30]})")
            print(f"  新字幕: {new_start:.3f}s - {new_end:.3f}s ({new_sub.text[:30]})")
            print(f"  时间差: {time_diff:+.3f}s")

            # 判断是否需要调整
            if abs(time_diff) < self.threshold:
                # 差值在阈值内，不需要处理
                print(f"  → 差值({abs(time_diff):.3f}s) < 阈值({self.threshold}s)，不处理")
                adjusted_original.append({
                    'index': i,
                    'start': orig_start,
                    'end': orig_end,
                    'text': orig_sub.text,
                    'adjustment': 0.0,
                    'cumulative_offset': cumulative_offset
                })
            else:
                # 需要调整
                if time_diff > 0:
                    # 原字幕晚于新字幕，需要剪掉前面的时间
                    print(f"  → 剪掉 {time_diff:.3f}秒")
                    new_adjusted_start = orig_start - time_diff
                    new_adjusted_end = orig_end - time_diff

                    adjustment_log.append({
                        'index': i + 1,
                        'original_text': orig_sub.text[:50],
                        'new_text': new_sub.text[:50],
                        'time_diff': f"{time_diff:+.3f}s",
                        'action': '剪掉',
                        'adjustment': f"从 {orig_start:.3f}s 调整到 {new_adjusted_start:.3f}s",
                        'cumulative_offset': f"{cumulative_offset:.3f}s"
                    })
                else:
                    # 新字幕晚于原字幕，需要增加时间（复制前面的画面）
                    print(f"  → 增加 {abs(time_diff):.3f}秒")
                    new_adjusted_start = orig_start - time_diff  # time_diff是负数，所以减
                    new_adjusted_end = orig_end - time_diff

                    adjustment_log.append({
                        'index': i + 1,
                        'original_text': orig_sub.text[:50],
                        'new_text': new_sub.text[:50],
                        'time_diff': f"{time_diff:+.3f}s",
                        'action': '增加',
                        'adjustment': f"从 {orig_start:.3f}s 调整到 {new_adjusted_start:.3f}s",
                        'cumulative_offset': f"{cumulative_offset:.3f}s"
                    })

                # 使用调整后的时间
                adjusted_original.append({
                    'index': i,
                    'start': new_adjusted_start,
                    'end': new_adjusted_end,
                    'text': orig_sub.text,
                    'adjustment': time_diff,
                    'cumulative_offset': cumulative_offset
                })

                # 更新累积偏移
                cumulative_offset += time_diff

        # 根据调整后的时间戳提取片段
        segments = []
        for item in adjusted_original:
            start = max(0, item['start'])
            end = min(video_duration, item['end'])

            if end > start:
                segments.append((start, end))
                print(f"  片段: {start:.3f}s - {end:.3f}s (时长: {end-start:.3f}s)")

        # 统计信息
        stats = {
            'total_subtitles': min_count,
            'threshold': self.threshold,
            'total_adjustments': len([log for log in adjustment_log if log.get('action')]),
            'total_adjustment_time': cumulative_offset,
            'original_video_duration': video_duration,
            'segments_count': len(segments),
            'adjustment_log': adjustment_log
        }

        print(f"\n调整统计:")
        print(f"  总字幕数: {stats['total_subtitles']}")
        print(f"  需要调整的字幕: {stats['total_adjustments']}")
        print(f"  总调整时长: {stats['total_adjustment_time']:+.3f}秒")
        print(f"  原视频时长: {stats['original_video_duration']:.2f}秒")
        print(f"  提取片段数: {stats['segments_count']}")

        return segments, stats

    def extract_video_segments(self, segments: List[Tuple[float, float]]) -> List[str]:
        """提取视频片段"""
        segment_files = []

        print(f"\n提取视频片段（使用{'精确' if self.use_precise_seek else '快速'}模式）...")

        for i, (start, end) in enumerate(tqdm(segments, desc="提取片段")):
            temp_segment = self.temp_dir / f'segment_{i:03d}.mp4'
            duration = end - start

            # 添加缓冲时间避免截断
            buffer_time = 0.05
            start = max(0, start - buffer_time)
            end = min(self.get_video_duration(), end + buffer_time)

            if self.use_precise_seek:
                cmd = [
                    'ffmpeg', '-y',
                    '-ss', str(start),
                    '-i', self.video_path,
                    '-t', str(duration),
                    '-c:v', 'libx264',
                    '-c:a', 'aac',
                    '-preset', 'fast',
                    '-crf', '23',
                    '-loglevel', 'error',
                    str(temp_segment)
                ]
            else:
                cmd = [
                    'ffmpeg', '-y',
                    '-ss', str(start),
                    '-i', self.video_path,
                    '-t', str(duration),
                    '-c', 'copy',
                    '-avoid_negative_ts', '1',
                    '-loglevel', 'error',
                    str(temp_segment)
                ]

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300
                )

                if result.returncode == 0 and temp_segment.exists() and temp_segment.stat().st_size > 1000:
                    segment_files.append(str(temp_segment))
                else:
                    print(f"  ⚠️  片段{i+1}提取失败")
            except subprocess.TimeoutExpired:
                print(f"  ⚠️  片段{i+1}提取超时")
            except Exception as e:
                print(f"  ⚠️  片段{i+1}提取出错: {e}")

        return segment_files

    def concat_segments(self, segment_files: List[str]) -> Optional[str]:
        """拼接视频片段"""
        if not segment_files:
            return None

        concat_list = self.temp_dir / 'concat_list.txt'
        with open(concat_list, 'w') as f:
            for seg_file in segment_files:
                f.write(f"file '{seg_file}'\n")

        output_path = self.output_dir / "adjusted_video.mp4"

        print("\n拼接视频片段...")

        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(concat_list),
            '-c', 'copy',
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1000:
                print(f"✅ 视频拼接成功: {output_path}")
                return str(output_path)
            else:
                print(f"⚠️  视频拼接失败")
                return None
        except subprocess.TimeoutExpired:
            print(f"⚠️  拼接超时")
            return None
        except Exception as e:
            print(f"⚠️  拼接出错: {e}")
            return None

    def export_adjustment_log(self, stats: Dict, output_path: str = "adjustment_log.json"):
        """导出调整日志"""
        import json
        log_path = self.output_dir / output_path
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 调整日志已导出: {log_path}")

    def process(self) -> Dict:
        """执行累积时间差值调整流程"""
        results = {}

        try:
            # 1. 加载字幕
            self.load_subtitles()

            # 2. 计算调整后的片段
            segments, stats = self.calculate_adjusted_segments()

            if not segments:
                results['error'] = '没有可提取的片段'
                return results

            # 3. 导出日志
            self.export_adjustment_log(stats)

            # 4. 提取片段
            segment_files = self.extract_video_segments(segments)

            if not segment_files:
                results['error'] = '所有片段提取失败'
                return results

            # 5. 拼接
            adjusted_video = self.concat_segments(segment_files)

            if adjusted_video:
                results['success'] = True
                results['adjusted_video'] = adjusted_video
                results['stats'] = stats
                results['segment_count'] = len(segment_files)
            else:
                results['error'] = '视频拼接失败'

            return results

        finally:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)

    def cleanup(self):
        """清理临时文件"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("使用方法: python cumulative_adjust_clipper.py <video.mp4> <original.srt> <new.srt> [threshold] [precise]")
        print("\n示例:")
        print("  python cumulative_adjust_clipper.py video.mp4 original.srt new.srt")
        print("  python cumulative_adjust_clipper.py video.mp4 original.srt new.srt 0.5")
        print("  python cumulative_adjust_clipper.py video.mp4 original.srt new.srt 0.3 precise")
        print("\n参数:")
        print("  threshold: 时间差阈值（秒，默认0.5）")
        print("  precise: 是否使用精确模式")
        sys.exit(1)

    video_path = sys.argv[1]
    original_srt = sys.argv[2]
    new_srt = sys.argv[3]
    threshold = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5
    use_precise = len(sys.argv) > 5 and sys.argv[5] == 'precise'

    print(f"配置:")
    print(f"  视频: {video_path}")
    print(f"  原字幕: {original_srt}")
    print(f"  新字幕: {new_srt}")
    print(f"  阈值: {threshold}秒")
    print(f"  精确模式: {use_precise}")

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
        print(f"\n✅ 处理成功！")
        print(f"输出: {results['adjusted_video']}")
    else:
        print(f"\n❌ 处理失败: {results.get('error')}")
