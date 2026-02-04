#!/usr/bin/env python3.12
"""
增强的视频剪辑处理器 - 支持批量处理和智能剪辑
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


class EnhancedVideoClipper:
    """增强的视频剪辑器"""

    def __init__(
        self,
        video_path: str,
        original_srt_path: str,
        new_srt_path: str,
        output_dir: str = "output",
        merge_gap: float = 2.0,
        use_precise_seek: bool = False
    ):
        """
        初始化剪辑器

        Args:
            video_path: 原视频路径
            original_srt_path: 原字幕路径
            new_srt_path: 新字幕路径
            output_dir: 输出目录
            merge_gap: 合并间隙阈值（秒）
            use_precise_seek: 是否使用精确seek
        """
        self.video_path = video_path
        self.original_srt_path = original_srt_path
        self.new_srt_path = new_srt_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.merge_gap = merge_gap
        self.use_precise_seek = use_precise_seek

        self.temp_dir = Path(tempfile.mkdtemp(prefix="enhanced_clip_"))
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

    def analyze_and_extract_segments(self) -> List[Tuple[float, float]]:
        """
        分析字幕并提取视频片段

        Returns:
            片段列表 [(start, end), ...]
        """
        if not self.original_subs or not self.new_subs:
            self.load_subtitles()

        video_duration = self.get_video_duration()
        segments_to_extract = []
        used_original_indices = set()

        print("\n分析字幕时间匹配...")

        # 对每个新字幕，找到最佳匹配的原字幕片段
        for idx, new_sub in enumerate(tqdm(self.new_subs, desc="匹配字幕")):
            new_start = new_sub.start.ordinal / 1000.0
            new_end = new_sub.end.ordinal / 1000.0
            new_duration = new_end - new_start

            best_overlap = None
            best_overlap_duration = 0
            best_orig_idx = -1

            for orig_idx, orig_sub in enumerate(self.original_subs):
                if orig_idx in used_original_indices:
                    continue

                orig_start = orig_sub.start.ordinal / 1000.0
                orig_end = orig_sub.end.ordinal / 1000.0

                # 计算重叠
                overlap_start = max(new_start, orig_start)
                overlap_end = min(new_end, orig_end)
                overlap_duration = overlap_end - overlap_start

                if overlap_duration > 0.3 and overlap_duration > best_overlap_duration:
                    best_overlap = (overlap_start, overlap_end)
                    best_overlap_duration = overlap_duration
                    best_orig_idx = orig_idx

            if best_overlap and best_orig_idx >= 0:
                used_original_indices.add(best_orig_idx)

                clip_start = max(0, best_overlap[0])
                clip_end = min(video_duration, best_overlap[1])

                # 如果新字幕更长，向后扩展
                if new_duration > (clip_end - clip_start):
                    extension = new_duration - (clip_end - clip_start)
                    clip_end = min(video_duration, clip_end + extension)

                if clip_end > clip_start:
                    segments_to_extract.append((clip_start, clip_end))

        print(f"找到 {len(segments_to_extract)} 个原始片段")

        # 按开始时间排序
        segments_to_extract.sort(key=lambda x: x[0])

        # 合并相邻片段
        merged_segments = []
        if segments_to_extract:
            current_start, current_end = segments_to_extract[0]

            for start, end in segments_to_extract[1:]:
                if start - current_end <= self.merge_gap:
                    current_end = end
                else:
                    merged_segments.append((current_start, current_end))
                    current_start, current_end = start, end

            merged_segments.append((current_start, current_end))

        print(f"合并后剩余 {len(merged_segments)} 个片段")
        return merged_segments

    def extract_video_segments(self, segments: List[Tuple[float, float]]) -> List[str]:
        """
        提取视频片段

        Args:
            segments: 时间片段列表

        Returns:
            提取的片段文件路径列表
        """
        segment_files = []

        print(f"\n提取视频片段（使用{'精确' if self.use_precise_seek else '快速'}模式）...")

        for i, (start, end) in enumerate(tqdm(segments, desc="提取片段")):
            temp_segment = self.temp_dir / f'segment_{i:03d}.mp4'
            duration = end - start

            if self.use_precise_seek:
                # 精确模式：重新编码
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
                # 快速模式：流复制
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
        """
        拼接视频片段

        Args:
            segment_files: 片段文件路径列表

        Returns:
            拼接后的视频文件路径
        """
        if not segment_files:
            return None

        # 创建拼接列表文件
        concat_list = self.temp_dir / 'concat_list.txt'
        with open(concat_list, 'w') as f:
            for seg_file in segment_files:
                f.write(f"file '{seg_file}'\n")

        # 拼接视频
        output_path = self.output_dir / "clipped_video.mp4"

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
                print(f"⚠️  视频拼接失败: {result.stderr}")
                return None
        except subprocess.TimeoutExpired:
            print(f"⚠️  拼接超时")
            return None
        except Exception as e:
            print(f"⚠️  拼接出错: {e}")
            return None

    def process(self) -> Dict:
        """
        执行完整的剪辑流程

        Returns:
            处理结果字典
        """
        results = {}

        try:
            # 1. 加载字幕
            self.load_subtitles()

            # 2. 分析并提取片段
            segments = self.analyze_and_extract_segments()

            if not segments:
                results['error'] = '没有找到可提取的片段'
                return results

            # 3. 提取视频片段
            segment_files = self.extract_video_segments(segments)

            if not segment_files:
                results['error'] = '所有片段提取失败'
                return results

            # 4. 拼接片段
            clipped_video = self.concat_segments(segment_files)

            if clipped_video:
                results['success'] = True
                results['clipped_video'] = clipped_video
                results['segment_count'] = len(segment_files)
                results['merge_gap'] = self.merge_gap
                results['precise_mode'] = self.use_precise_seek
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


class BatchVideoProcessor:
    """批量视频处理器"""

    def __init__(self, output_dir: str = "output"):
        """
        初始化批量处理器

        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results = []

    def process_single(
        self,
        video_path: str,
        original_srt_path: str,
        new_srt_path: str,
        merge_gap: float = 2.0,
        use_precise_seek: bool = False
    ) -> Dict:
        """
        处理单个视频

        Args:
            video_path: 视频路径
            original_srt_path: 原字幕路径
            new_srt_path: 新字幕路径
            merge_gap: 合并间隙阈值
            use_precise_seek: 是否精确模式

        Returns:
            处理结果
        """
        video_name = Path(video_path).stem
        task_output_dir = self.output_dir / video_name

        clipper = EnhancedVideoClipper(
            video_path=video_path,
            original_srt_path=original_srt_path,
            new_srt_path=new_srt_path,
            output_dir=str(task_output_dir),
            merge_gap=merge_gap,
            use_precise_seek=use_precise_seek
        )

        result = clipper.process()
        result['video_name'] = video_name
        result['video_path'] = video_path

        return result

    def process_batch(
        self,
        tasks: List[Dict],
        merge_gap: float = 2.0,
        use_precise_seek: bool = False
    ) -> List[Dict]:
        """
        批量处理多个视频

        Args:
            tasks: 任务列表，每个任务包含 video_path, original_srt_path, new_srt_path
            merge_gap: 合并间隙阈值
            use_precise_seek: 是否精确模式

        Returns:
            处理结果列表
        """
        print(f"\n开始批量处理 {len(tasks)} 个视频...")

        results = []

        for i, task in enumerate(tqdm(tasks, desc="批量处理")):
            print(f"\n[{i+1}/{len(tasks)}] 处理: {Path(task['video_path']).name}")

            result = self.process_single(
                video_path=task['video_path'],
                original_srt_path=task['original_srt_path'],
                new_srt_path=task['new_srt_path'],
                merge_gap=merge_gap,
                use_precise_seek=use_precise_seek
            )

            results.append(result)

            if result.get('success'):
                print(f"  ✅ 成功: {result.get('clipped_video')}")
            else:
                print(f"  ❌ 失败: {result.get('error')}")

        self.results = results
        return results

    def generate_report(self, output_path: str = "batch_report.json"):
        """生成批量处理报告"""
        import json

        report = {
            'total': len(self.results),
            'successful': sum(1 for r in self.results if r.get('success')),
            'failed': sum(1 for r in self.results if not r.get('success')),
            'results': self.results
        }

        report_path = self.output_dir / output_path
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 批量处理报告已保存: {report_path}")
        print(f"   总计: {report['total']}")
        print(f"   成功: {report['successful']}")
        print(f"   失败: {report['failed']}")

        return report
