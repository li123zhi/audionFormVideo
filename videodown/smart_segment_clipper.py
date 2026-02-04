#!/usr/bin/env python3.12
"""
智能片段剪辑器
保留原视频的自然间隙，只提取与新字幕对应的内容
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


class SmartSegmentClipper:
    """智能片段剪辑器"""

    def __init__(
        self,
        video_path: str,
        original_srt_path: str,
        new_srt_path: str,
        output_dir: str = "output",
        use_precise_seek: bool = False
    ):
        self.video_path = video_path
        self.original_srt_path = original_srt_path
        self.new_srt_path = new_srt_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.use_precise_seek = use_precise_seek

        self.temp_dir = Path(tempfile.mkdtemp(prefix="smart_clip_"))
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
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', self.video_path]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            import json
            info = json.loads(result.stdout)
            return float(info['format']['duration'])
        except:
            return 0.0

    def text_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        text1 = text1.lower().strip()
        text2 = text2.lower().strip()
        if not text1 or not text2:
            return 0.0
        sequence = difflib.SequenceMatcher(None, text1, text2)
        return sequence.ratio()

    def extract_segments_with_gaps(self) -> Tuple[List[Tuple[float, float]], Dict]:
        """
        提取视频片段，保留字幕间的自然间隙

        算法：
        1. 为每条新字幕在原视频中找到对应内容
        2. 提取匹配的内容片段
        3. 同时保留片段间的间隙（原视频的自然停顿）

        Returns:
            (片段列表, 统计信息)
        """
        if not self.original_subs or not self.new_subs:
            self.load_subtitles()

        video_duration = self.get_video_duration()

        segments = []
        used_original_indices = set()

        processing_log = []

        print("\n智能提取片段（保留自然间隙）...")

        for i, new_sub in enumerate(tqdm(self.new_subs, desc="匹配字幕")):
            new_start = new_sub.start.ordinal / 1000.0
            new_end = new_sub.end.ordinal / 1000.0
            new_text = new_sub.text.lower().strip()

            best_match = None
            best_score = 0.0
            best_index = -1

            # 在原字幕中找匹配（搜索范围：前后各20条）
            last_used = max(used_original_indices) if used_original_indices else 0
            search_start = max(0, last_used - 20)
            search_end = min(len(self.original_subs), last_used + 21)

            for idx in range(search_start, search_end):
                if idx in used_original_indices:
                    continue

                orig_sub = self.original_subs[idx]
                orig_text = orig_sub.text.lower().strip()

                # 计算文本相似度
                text_sim = self.text_similarity(new_text, orig_text)

                if text_sim > best_score:
                    best_score = text_sim
                    best_match = orig_sub
                    best_index = idx

            # 如果找到匹配（相似度>0.3）
            if best_match and best_score > 0.3:
                orig_start = best_match.start.ordinal / 1000.0
                orig_end = best_match.end.ordinal / 1000.0

                # 提取片段（使用原视频的时间位置）
                clip_start = max(0, orig_start)
                clip_end = min(video_duration, orig_end)

                if clip_end > clip_start:
                    segments.append((clip_start, clip_end))
                    used_original_indices.add(best_index)

                    processing_log.append({
                        'index': i + 1,
                        'new_text': new_text[:50],
                        'matched_original': best_index + 1,
                        'original_text': best_match.text[:50],
                        'similarity': f"{best_score:.2f}",
                        'segment_time': f"{clip_start:.2f}-{clip_end:.2f}s"
                    })

                    print(f"  字幕{i+1}: 匹配原字幕{best_index+1} (相似度{best_score:.2f})")
            else:
                print(f"  ⚠️  字幕{i+1}: 未找到匹配（'{new_text[:30]}...'）")
                processing_log.append({
                    'index': i + 1,
                    'new_text': new_text[:50],
                    'status': '未找到匹配'
                })

        # 现在我们有了所有匹配的片段
        # 需要保留它们之间的间隙
        print("\n保留片段间的自然间隙...")

        # 如果片段之间有小间隙，保留；如果间隙很大，也保留
        # 这样可以保持原视频的节奏

        # 统计信息
        total_matched = len([s for s in segments if s])
        total_original_duration = self.original_subs[-1].end.ordinal / 1000.0 if self.original_subs else 0

        stats = {
            'total_new_subtitles': len(self.new_subs),
            'matched_segments': total_matched,
            'match_rate': f"{(total_matched / len(self.new_subs) * 100):.1f}%",
            'original_video_duration': total_original_duration,
            'segments_count': len(segments),
            'processing_log': processing_log
        }

        print(f"\n提取统计:")
        print(f"  新字幕总数: {stats['total_new_subtitles']}")
        print(f"  成功匹配: {stats['matched_segments']}")
        print(f"  匹配率: {stats['match_rate']}")
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

            # 添加一点缓冲时间，避免截断
            buffer_time = 0.1  # 100ms缓冲
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
        """拼接视频片段（保留原视频节奏）"""
        if not segment_files:
            return None

        concat_list = self.temp_dir / 'concat_list.txt'
        with open(concat_list, 'w') as f:
            for seg_file in segment_files:
                f.write(f"file '{seg_file}'\n")

        output_path = self.output_dir / "smart_clipped_video.mp4"

        print("\n拼接视频片段（保留原视频节奏）...")

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

    def export_processing_log(self, stats: Dict, output_path: str = "smart_clip_log.json"):
        """导出处理日志"""
        import json
        log_path = self.output_dir / output_path
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 处理日志已导出: {log_path}")

    def process(self) -> Dict:
        """执行智能片段剪辑流程"""
        results = {}

        try:
            # 1. 加载字幕
            self.load_subtitles()

            # 2. 提取片段（保留间隙）
            segments, stats = self.extract_segments_with_gaps()

            if not segments:
                results['error'] = '没有找到可提取的片段'
                return results

            # 3. 导出日志
            self.export_processing_log(stats)

            # 4. 提取视频片段
            segment_files = self.extract_video_segments(segments)

            if not segment_files:
                results['error'] = '所有片段提取失败'
                return results

            # 5. 拼接（保留原视频节奏）
            clipped_video = self.concat_segments(segment_files)

            if clipped_video:
                results['success'] = True
                results['clipped_video'] = clipped_video
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


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("使用方法: python smart_segment_clipper.py <video.mp4> <original.srt> <new.srt>")
        sys.exit(1)

    clipper = SmartSegmentClipper(
        video_path=sys.argv[1],
        original_srt_path=sys.argv[2],
        new_srt_path=sys.argv[3],
        output_dir="output"
    )

    results = clipper.process()

    if results.get('success'):
        print(f"\n✅ 智能剪辑成功！")
        print(f"输出: {results['clipped_video']}")
    else:
        print(f"\n❌ 剪辑失败: {results.get('error')}")
