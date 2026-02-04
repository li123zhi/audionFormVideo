#!/usr/bin/env python3.12
"""
紧凑视频剪辑处理器 - 累积偏移算法
通过对比原字幕和新字幕，减掉时间差值，生成更紧凑的视频
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


class CompactVideoClipper:
    """紧凑视频剪辑器 - 累积偏移算法"""

    def __init__(
        self,
        video_path: str,
        original_srt_path: str,
        new_srt_path: str,
        output_dir: str = "output",
        use_precise_seek: bool = False
    ):
        """
        初始化紧凑剪辑器

        Args:
            video_path: 原视频路径
            original_srt_path: 原字幕路径
            new_srt_path: 新字幕路径
            output_dir: 输出目录
            use_precise_seek: 是否使用精确seek
        """
        self.video_path = video_path
        self.original_srt_path = original_srt_path
        self.new_srt_path = new_srt_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.use_precise_seek = use_precise_seek

        self.temp_dir = Path(tempfile.mkdtemp(prefix="compact_clip_"))
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

    def get_video_duration(self) -> float:
        """获取视频时长"""
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            self.video_path
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            import json
            info = json.loads(result.stdout)
            duration = float(info['format']['duration'])
            return duration
        except:
            return 0.0

    def find_matching_original_subtitle(
        self,
        new_sub: pysrt.SubRipItem,
        cumulative_offset: float,
        used_indices: set
    ) -> Optional[Tuple[int, pysrt.SubRipItem]]:
        """
        为新字幕找到最佳匹配的原字幕（考虑累积偏移）

        Args:
            new_sub: 新字幕
            cumulative_offset: 累积时间偏移（秒）
            used_indices: 已使用的原字幕索引

        Returns:
            (原字幕索引, 原字幕) 或 None
        """
        new_start = new_sub.start.ordinal / 1000.0
        new_end = new_sub.end.ordinal / 1000.0
        new_text = new_sub.text.lower().strip()

        best_match = None
        best_score = 0
        best_index = -1

        # 考虑累积偏移后的目标时间
        target_start = new_start + cumulative_offset
        target_end = new_end + cumulative_offset

        for idx, orig_sub in enumerate(self.original_subs):
            # 跳过已使用的字幕
            if idx in used_indices:
                continue

            orig_start = orig_sub.start.ordinal / 1000.0
            orig_end = orig_sub.end.ordinal / 1000.0
            orig_text = orig_sub.text.lower().strip()

            # 计算时间接近度得分
            time_diff = abs(orig_start - target_start)
            if time_diff > 10:  # 时间差超过10秒，不太可能匹配
                continue

            # 计算文本相似度（简单版）
            text_similarity = 0
            if new_text and orig_text:
                # 检查是否有相同的词
                new_words = set(new_text.split())
                orig_words = set(orig_text.split())
                if new_words & orig_words:  # 有交集
                    text_similarity = len(new_words & orig_words) / max(len(new_words), 1)

            # 综合得分（时间接近度 + 文本相似度）
            # 时间越近得分越高，文本越相似得分越高
            time_score = max(0, 1 - time_diff / 10)  # 0-1之间
            total_score = time_score * 0.7 + text_similarity * 0.3

            if total_score > best_score:
                best_score = total_score
                best_match = orig_sub
                best_index = idx

        # 只接受得分足够高的匹配
        if best_score > 0.3:
            return best_index, best_match

        return None

    def calculate_compact_segments(self) -> Tuple[List[Tuple[float, float]], Dict]:
        """
        计算紧凑的视频片段（累积偏移算法）

        Returns:
            (片段列表, 统计信息)
        """
        if not self.original_subs or not self.new_subs:
            self.load_subtitles()

        video_duration = self.get_video_duration()
        segments = []
        used_indices = set()
        cumulative_offset = 0.0  # 累积时间偏移

        print("\n使用累积偏移算法分析字幕...")

        # 记录每条字幕的处理信息
        processing_log = []

        for i, new_sub in enumerate(tqdm(self.new_subs, desc="分析字幕")):
            new_start = new_sub.start.ordinal / 1000.0
            new_end = new_sub.end.ordinal / 1000.0
            new_duration = new_end - new_start

            # 找到匹配的原字幕
            match_result = self.find_matching_original_subtitle(
                new_sub,
                cumulative_offset,
                used_indices
            )

            if match_result:
                orig_idx, orig_sub = match_result

                orig_start = orig_sub.start.ordinal / 1000.0
                orig_end = orig_sub.end.ordinal / 1000.0
                orig_duration = orig_end - orig_start

                # 计算时间差
                start_diff = new_start - (orig_start - cumulative_offset)
                duration_diff = new_duration - orig_duration

                # 提取原字幕片段（原始时间位置）
                clip_start = max(0, orig_start)
                clip_end = min(video_duration, orig_end)

                if clip_end > clip_start:
                    segments.append((clip_start, clip_end))
                    used_indices.add(orig_idx)

                    # 更新累积偏移
                    # 如果新字幕更短，后面的字幕需要向前移
                    cumulative_offset -= duration_diff

                    processing_log.append({
                        'index': i + 1,
                        'new_text': new_sub.text[:50],
                        'original_time': f"{orig_start:.2f}-{orig_end:.2f}",
                        'new_time_adjusted': f"{new_start + cumulative_offset:.2f}-{new_end + cumulative_offset:.2f}",
                        'duration_diff': f"{duration_diff:+.2f}s",
                        'cumulative_offset': f"{cumulative_offset:+.2f}s"
                    })

                    print(f"  字幕{i+1}: 原时长{orig_duration:.2f}s → 新时长{new_duration:.2f}s "
                          f"(差{duration_diff:+.2f}s, 累积偏移{cumulative_offset:+.2f}s)")
            else:
                print(f"  ⚠️  字幕{i+1}: 未找到匹配的原字幕")
                processing_log.append({
                    'index': i + 1,
                    'new_text': new_sub.text[:50],
                    'status': '未找到匹配'
                })

        # 统计信息
        stats = {
            'total_subtitles': len(self.new_subs),
            'matched_subtitles': len(segments),
            'final_cumulative_offset': cumulative_offset,
            'original_total_duration': self.original_subs[-1].end.ordinal / 1000.0 if self.original_subs else 0,
            'new_total_duration': (self.new_subs[-1].end.ordinal / 1000.0 + cumulative_offset) if self.new_subs else 0,
            'time_saved': abs(cumulative_offset),
            'processing_log': processing_log
        }

        print(f"\n统计信息:")
        print(f"  匹配字幕: {stats['matched_subtitles']}/{stats['total_subtitles']}")
        print(f"  原视频总时长: {stats['original_total_duration']:.2f}秒")
        print(f"  新视频总时长: {stats['new_total_duration']:.2f}秒")
        print(f"  节省时间: {stats['time_saved']:.2f}秒")
        print(f"  紧凑比例: {(1 - stats['new_total_duration'] / stats['original_total_duration']) * 100:.1f}%")

        return segments, stats

    def extract_video_segments(self, segments: List[Tuple[float, float]]) -> List[str]:
        """提取视频片段"""
        segment_files = []

        print(f"\n提取视频片段（使用{'精确' if self.use_precise_seek else '快速'}模式）...")

        for i, (start, end) in enumerate(tqdm(segments, desc="提取片段")):
            temp_segment = self.temp_dir / f'segment_{i:03d}.mp4'
            duration = end - start

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

        output_path = self.output_dir / "compact_video.mp4"

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

    def export_processing_log(self, stats: Dict, output_path: str = "processing_log.json"):
        """导出处理日志"""
        import json

        log_path = self.output_dir / output_path
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 处理日志已导出: {log_path}")

    def process(self) -> Dict:
        """执行紧凑剪辑流程"""
        results = {}

        try:
            # 1. 加载字幕
            self.load_subtitles()

            # 2. 计算紧凑片段（累积偏移算法）
            segments, stats = self.calculate_compact_segments()

            if not segments:
                results['error'] = '没有找到可提取的片段'
                return results

            # 3. 导出处理日志
            self.export_processing_log(stats)

            # 4. 提取视频片段
            segment_files = self.extract_video_segments(segments)

            if not segment_files:
                results['error'] = '所有片段提取失败'
                return results

            # 5. 拼接片段
            compact_video = self.concat_segments(segment_files)

            if compact_video:
                results['success'] = True
                results['compact_video'] = compact_video
                results['stats'] = stats
                results['segment_count'] = len(segment_files)
            else:
                results['error'] = '视频拼接失败'

            return results

        finally:
            # 清理临时文件
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)

    def cleanup(self):
        """清理临时文件"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)


# 测试函数
def test_compact_clipper():
    """测试紧凑剪辑器"""
    import sys

    if len(sys.argv) < 4:
        print("使用方法: python compact_video_processor.py <video.mp4> <original.srt> <new.srt>")
        return

    video_path = sys.argv[1]
    original_srt = sys.argv[2]
    new_srt = sys.argv[3]

    clipper = CompactVideoClipper(
        video_path=video_path,
        original_srt_path=original_srt,
        new_srt_path=new_srt,
        output_dir="output"
    )

    results = clipper.process()

    if results.get('success'):
        print(f"\n✅ 紧凑剪辑成功！")
        print(f"输出视频: {results['compact_video']}")
        print(f"统计信息: {results['stats']}")
    else:
        print(f"\n❌ 剪辑失败: {results.get('error')}")


if __name__ == "__main__":
    test_compact_clipper()
