#!/usr/bin/env python3.12
"""
时间轴对齐剪辑器
以新字幕时间轴为基准，剪辑原视频，让视频与字幕完美同步
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
import difflib


class TimelineAligner:
    """时间轴对齐剪辑器"""

    def __init__(
        self,
        video_path: str,
        original_srt_path: str,
        new_srt_path: str,
        output_dir: str = "output",
        use_precise_seek: bool = False
    ):
        """
        初始化时间轴对齐器

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

        self.temp_dir = Path(tempfile.mkdtemp(prefix="timeline_align_"))
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

    def text_similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度

        Returns:
            0-1之间的相似度分数
        """
        # 清理文本
        text1 = text1.lower().strip()
        text2 = text2.lower().strip()

        if not text1 or not text2:
            return 0.0

        # 使用SequenceMatcher计算相似度
        sequence = difflib.SequenceMatcher(None, text1, text2)
        return sequence.ratio()

    def find_matching_segment(
        self,
        new_sub: pysrt.SubRipItem,
        used_original_indices: set,
        last_original_index: int
    ) -> Optional[Tuple[int, float, float]]:
        """
        为新字幕找到原视频中的匹配片段

        Args:
            new_sub: 新字幕
            used_original_indices: 已使用的原字幕索引
            last_original_index: 上一个匹配的原字幕索引

        Returns:
            (原字幕索引, 开始时间, 结束时间) 或 None
        """
        new_text = new_sub.text.lower().strip()
        new_start = new_sub.start.ordinal / 1000.0
        new_end = new_sub.end.ordinal / 1000.0
        new_duration = new_end - new_start

        best_match = None
        best_score = 0.0
        best_index = -1
        best_start = 0.0
        best_end = 0.0

        # 搜索范围：从上一个匹配位置开始，前后各搜索10条字幕
        search_start = max(0, last_original_index - 10)
        search_end = min(len(self.original_subs), last_original_index + 11)

        for idx in range(search_start, search_end):
            if idx in used_original_indices:
                continue

            orig_sub = self.original_subs[idx]
            orig_text = orig_sub.text.lower().strip()
            orig_start = orig_sub.start.ordinal / 1000.0
            orig_end = orig_sub.end.ordinal / 1000.0
            orig_duration = orig_end - orig_start

            # 计算文本相似度
            text_sim = self.text_similarity(new_text, orig_text)

            # 如果文本相似度太低，跳过
            if text_sim < 0.3:
                continue

            # 计算时长相似度（时长差异越小越好）
            duration_diff = abs(new_duration - orig_duration)
            duration_sim = max(0, 1 - duration_diff / max(new_duration, orig_duration))

            # 综合得分（文本相似度更重要）
            total_score = text_sim * 0.7 + duration_sim * 0.3

            if total_score > best_score:
                best_score = total_score
                best_match = orig_sub
                best_index = idx
                best_start = orig_start
                best_end = orig_end

        # 只接受得分足够高的匹配
        if best_score > 0.4:
            return best_index, best_start, best_end

        return None

    def extract_aligned_segments(self) -> Tuple[List[Tuple[float, float]], Dict]:
        """
        提取与新字幕时间轴对齐的视频片段

        算法：
        1. 以新字幕时间轴为基准
        2. 为每条新字幕找到原视频中的对应内容
        3. 按新字幕的顺序提取片段
        4. 保留新字幕之间的自然间隙

        Returns:
            (片段列表, 统计信息)
        """
        if not self.original_subs or not self.new_subs:
            self.load_subtitles()

        video_duration = self.get_video_duration()

        segments = []
        used_original_indices = set()
        last_original_index = 0

        processing_log = []

        print("\n以新字幕时间轴为基准，提取匹配的视频片段...")

        for i, new_sub in enumerate(tqdm(self.new_subs, desc="对齐字幕")):
            new_start = new_sub.start.ordinal / 1000.0
            new_end = new_sub.end.ordinal / 1000.0
            new_duration = new_end - new_start
            new_text = new_sub.text

            # 找到匹配的原字幕片段
            match_result = self.find_matching_segment(
                new_sub,
                used_original_indices,
                last_original_index
            )

            if match_result:
                orig_idx, orig_start, orig_end = match_result

                # 使用原视频的时间位置（不是新字幕的时间）
                clip_start = max(0, orig_start)
                clip_end = min(video_duration, orig_end)

                if clip_end > clip_start:
                    segments.append((clip_start, clip_end))
                    used_original_indices.add(orig_idx)
                    last_original_index = orig_idx

                    text_sim = self.text_similarity(new_text, self.original_subs[orig_idx].text)

                    processing_log.append({
                        'index': i + 1,
                        'new_text': new_text[:50],
                        'original_index': orig_idx + 1,
                        'original_text': self.original_subs[orig_idx].text[:50],
                        'original_time': f"{orig_start:.2f}-{orig_end:.2f}",
                        'new_time': f"{new_start:.2f}-{new_end:.2f}",
                        'text_similarity': f"{text_sim:.2f}",
                        'extracted_segment': f"{clip_start:.2f}-{clip_end:.2f}"
                    })

                    print(f"  字幕{i+1}: 匹配到原字幕{orig_idx+1} "
                          f"(相似度{text_sim:.2f}, 片段{clip_start:.2f}-{clip_end:.2f}s)")
            else:
                print(f"  ⚠️  字幕{i+1}: 未找到匹配内容（'{new_text[:30]}...'）")
                processing_log.append({
                    'index': i + 1,
                    'new_text': new_text[:50],
                    'status': '未找到匹配'
                })

        # 统计信息
        total_matched = len([s for s in segments if s])
        total_new_duration = self.new_subs[-1].end.ordinal / 1000.0 if self.new_subs else 0

        stats = {
            'total_new_subtitles': len(self.new_subs),
            'matched_segments': total_matched,
            'match_rate': f"{(total_matched / len(self.new_subs) * 100):.1f}%",
            'new_subtitle_total_duration': total_new_duration,
            'extracted_segments_count': len(segments),
            'processing_log': processing_log
        }

        print(f"\n对齐统计:")
        print(f"  新字幕总数: {stats['total_new_subtitles']}")
        print(f"  成功匹配: {stats['matched_segments']}")
        print(f"  匹配率: {stats['match_rate']}")
        print(f"  新字幕总时长: {stats['new_subtitle_total_duration']:.2f}秒")
        print(f"  提取片段数: {stats['extracted_segments_count']}")

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

        output_path = self.output_dir / "aligned_video.mp4"

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

    def export_processing_log(self, stats: Dict, output_path: str = "alignment_log.json"):
        """导出处理日志"""
        import json

        log_path = self.output_dir / output_path
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 对齐日志已导出: {log_path}")

    def process(self) -> Dict:
        """执行时间轴对齐流程"""
        results = {}

        try:
            # 1. 加载字幕
            self.load_subtitles()

            # 2. 提取对齐的视频片段
            segments, stats = self.extract_aligned_segments()

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
            aligned_video = self.concat_segments(segment_files)

            if aligned_video:
                results['success'] = True
                results['aligned_video'] = aligned_video
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


def test_timeline_aligner():
    """测试时间轴对齐器"""
    import sys

    if len(sys.argv) < 4:
        print("使用方法: python timeline_aligner.py <video.mp4> <original.srt> <new.srt>")
        print("\n功能:")
        print("  以新字幕时间轴为基准，剪辑原视频")
        print("  让新视频与新字幕完美同步")
        print("  保留字幕间的自然间隙")
        return

    video_path = sys.argv[1]
    original_srt = sys.argv[2]
    new_srt = sys.argv[3]

    aligner = TimelineAligner(
        video_path=video_path,
        original_srt_path=original_srt,
        new_srt_path=new_srt,
        output_dir="output"
    )

    results = aligner.process()

    if results.get('success'):
        print(f"\n✅ 时间轴对齐成功！")
        print(f"输出视频: {results['aligned_video']}")
        print(f"统计信息: {results['stats']}")
    else:
        print(f"\n❌ 对齐失败: {results.get('error')}")


if __name__ == "__main__":
    test_timeline_aligner()
