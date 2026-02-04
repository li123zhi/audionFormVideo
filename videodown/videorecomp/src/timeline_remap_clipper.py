#!/usr/bin/env python3.12
"""
时间轴重映射剪辑器 - 按照新字幕时间轴重新组织视频
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


class TimelineRemapClipper:
    """时间轴重映射剪辑器"""

    def __init__(
        self,
        video_path: str,
        original_srt_path: str,
        new_srt_path: str,
        output_dir: str = "output",
        threshold: float = 0.5
    ):
        self.video_path = video_path
        self.original_srt_path = original_srt_path
        self.new_srt_path = new_srt_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.threshold = threshold

        self.temp_dir = Path(tempfile.mkdtemp(prefix="timeline_remap_"))
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

    def extract_segments_by_new_timeline(self) -> Tuple[List[Tuple[float, float, float]], Dict]:
        """
        按照新字幕时间轴提取视频片段

        Returns:
            (片段列表, 统计信息)
            片段格式: (新字幕开始时间, 新字幕结束时间, 原视频开始时间)
        """
        if not self.original_subs or not self.new_subs:
            self.load_subtitles()

        video_duration = self.get_video_duration()

        segments = []  # (新开始, 新结束, 原开始)
        processing_log = []

        print("\n按新字幕时间轴提取片段...")

        for i, new_sub in enumerate(tqdm(self.new_subs, desc="匹配字幕")):
            new_start = new_sub.start.ordinal / 1000.0
            new_end = new_sub.end.ordinal / 1000.0
            new_text = new_sub.text.lower().strip()

            best_match = None
            best_score = 0.0
            best_index = -1

            # 在原字幕中找匹配
            for idx, orig_sub in enumerate(self.original_subs):
                orig_text = orig_sub.text.lower().strip()
                text_sim = self.text_similarity(new_text, orig_text)

                if text_sim > best_score:
                    best_score = text_sim
                    best_match = orig_sub
                    best_index = idx

            # 如果找到匹配（相似度>0.3）
            if best_match and best_score > 0.3:
                orig_start = best_match.start.ordinal / 1000.0
                orig_end = best_match.end.ordinal / 1000.0

                # 计算需要的时长
                duration = new_end - new_start

                # 从原视频的 orig_start 位置提取 duration 秒
                segment_end = min(video_duration, orig_start + duration)

                if segment_end > orig_start:
                    segments.append((new_start, new_end, orig_start))
                    processing_log.append({
                        'index': i + 1,
                        'new_text': new_text[:50],
                        'new_time': f"{new_start:.3f}-{new_end:.3f}s",
                        'matched_original': best_index + 1,
                        'original_text': best_match.text[:50],
                        'original_time': f"{orig_start:.3f}-{orig_end:.3f}s",
                        'similarity': f"{best_score:.2f}",
                        'extract_from': f"{orig_start:.3f}s",
                        'extract_duration': f"{segment_end - orig_start:.3f}s"
                    })

                    print(f"  字幕{i+1}: 匹配原字幕{best_index+1} (相似度{best_score:.2f})")
                    print(f"    新时间轴: {new_start:.3f}s-{new_end:.3f}s")
                    print(f"    从原视频 {orig_start:.3f}s 提取 {segment_end - orig_start:.3f}s")
                else:
                    print(f"  ⚠️  字幕{i+1}: 片段时长无效")
                    processing_log.append({
                        'index': i + 1,
                        'new_text': new_text[:50],
                        'status': '片段时长无效'
                    })
            else:
                print(f"  ⚠️  字幕{i+1}: 未找到匹配（'{new_text[:30]}...'）")
                processing_log.append({
                    'index': i + 1,
                    'new_text': new_text[:50],
                    'status': '未找到匹配'
                })

        # 统计信息
        total_new_duration = self.new_subs[-1].end.ordinal / 1000.0 if self.new_subs else 0
        total_original_duration = self.original_subs[-1].end.ordinal / 1000.0 if self.original_subs else 0

        stats = {
            'total_new_subtitles': len(self.new_subs),
            'matched_segments': len(segments),
            'match_rate': f"{(len(segments) / len(self.new_subs) * 100):.1f}%",
            'original_video_duration': total_original_duration,
            'new_subtitle_total_duration': total_new_duration,
            'duration_difference': total_new_duration - total_original_duration,
            'segments_count': len(segments),
            'processing_log': processing_log
        }

        print(f"\n提取统计:")
        print(f"  新字幕总数: {stats['total_new_subtitles']}")
        print(f"  成功匹配: {stats['matched_segments']}")
        print(f"  匹配率: {stats['match_rate']}")
        print(f"  原视频/字幕时长: {stats['original_video_duration']:.2f}秒")
        print(f"  新字幕总时长: {stats['new_subtitle_total_duration']:.2f}秒")
        print(f"  时长差: {stats['duration_difference']:+.2f}秒")
        print(f"  提取片段数: {stats['segments_count']}")

        return segments, stats

    def create_timeline_video(self, segments: List[Tuple[float, float, float]]) -> Optional[str]:
        """
        按照新字幕时间轴创建视频

        Args:
            segments: (新开始, 新结束, 原开始) 列表

        Returns:
            输出视频路径
        """
        if not segments:
            print("没有可提取的片段")
            return None

        # 计算新视频的总时长
        total_duration = segments[-1][1]  # 最后一个片段的结束时间
        print(f"\n新视频目标时长: {total_duration:.2f}秒")

        # 创建每个片段的视频文件
        segment_files = []
        gap_fill_duration = 0.1  # 片段之间的间隙填充时长

        print("\n提取视频片段...")

        for i, (new_start, new_end, orig_start) in enumerate(tqdm(segments, desc="提取片段")):
            duration = new_end - new_start

            # 从原视频提取片段
            temp_segment = self.temp_dir / f'segment_{i:03d}.mp4'

            cmd = [
                'ffmpeg', '-y',
                '-ss', str(orig_start),
                '-i', self.video_path,
                '-t', str(duration),
                '-c', 'copy',
                '-avoid_negative_ts', '1',
                '-loglevel', 'error',
                str(temp_segment)
            ]

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

                if result.returncode == 0 and temp_segment.exists() and temp_segment.stat().st_size > 1000:
                    # 计算实际提取的时长
                    actual_duration = self.get_segment_duration(str(temp_segment))
                    print(f"  片段{i+1}: 提取 {duration:.3f}s (实际 {actual_duration:.3f}s)")
                    segment_files.append((str(temp_segment), new_start, duration))
                else:
                    print(f"  ⚠️  片段{i+1}提取失败")
                    return None
            except subprocess.TimeoutExpired:
                print(f"  ⚠️  片段{i+1}提取超时")
                return None
            except Exception as e:
                print(f"  ⚠️  片段{i+1}提取出错: {e}")
                return None

        # 创建带时间轴的视频
        output_path = self.temp_dir / 'timeline_video.mp4'

        print("\n创建时间轴视频...")
        print(f"  片段数量: {len(segment_files)}")
        print(f"  目标时长: {total_duration:.2f}秒")

        # 方案1：直接拼接所有片段（简单但可能有间隙）
        concat_list = self.temp_dir / 'concat_list.txt'
        with open(concat_list, 'w') as f:
            for seg_file, _, _ in segment_files:
                f.write(f"file '{seg_file}'\n")

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
                actual_duration = self.get_video_duration(str(output_path))
                print(f"✅ 时间轴视频创建成功")
                print(f"   目标时长: {total_duration:.2f}秒")
                print(f"   实际时长: {actual_duration:.2f}秒")
                return str(output_path)
            else:
                print(f"⚠️  时间轴视频创建失败")
                return None
        except subprocess.TimeoutExpired:
            print(f"⚠️  创建超时")
            return None
        except Exception as e:
            print(f"⚠️  创建出错: {e}")
            return None

    def get_segment_duration(self, segment_path: str) -> float:
        """获取片段时长"""
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', segment_path]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            import json
            info = json.loads(result.stdout)
            return float(info['format']['duration'])
        except:
            return 0.0

    def export_processing_log(self, stats: Dict, output_path: str = "timeline_remap_log.json"):
        """导出处理日志"""
        import json
        log_path = self.output_dir / output_path
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 处理日志已导出: {log_path}")

    def process(self) -> Dict:
        """执行时间轴重映射流程"""
        results = {}

        try:
            # 1. 加载字幕
            self.load_subtitles()

            print("\n" + "="*60)
            print("开始时间轴重映射...")
            print("="*60)

            original_video_duration = self.get_video_duration()
            print(f"原视频时长: {original_video_duration:.2f}秒")

            # 2. 按新字幕时间轴提取片段
            segments, stats = self.extract_segments_by_new_timeline()

            if not segments:
                results['error'] = '没有找到可提取的片段'
                return results

            # 3. 导出日志
            self.export_processing_log(stats)

            # 4. 创建时间轴视频
            timeline_video = self.create_timeline_video(segments)

            if timeline_video:
                # 复制到输出目录
                final_video = self.output_dir / "timeline_remapped_video.mp4"
                shutil.copy2(timeline_video, final_video)

                final_duration = self.get_video_duration(str(final_video))

                print("\n" + "="*60)
                print("✅ 时间轴重映射完成！")
                print("="*60)
                print(f"原视频时长: {original_video_duration:.2f}秒")
                print(f"新视频时长: {final_duration:.2f}秒")
                print(f"时长变化: {final_duration - original_video_duration:+.2f}秒")
                print(f"\n输出视频: {final_video}")

                results['success'] = True
                results['remapped_video'] = str(final_video)
                results['stats'] = stats
                results['final_duration'] = final_duration
                results['original_duration'] = original_video_duration
                results['duration_change'] = final_duration - original_video_duration
            else:
                results['error'] = '时间轴视频创建失败'

            return results

        except Exception as e:
            print(f"\n❌ 处理出错: {e}")
            import traceback
            traceback.print_exc()
            results['error'] = str(e)
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
        print("使用方法: python timeline_remap_clipper.py <video.mp4> <original.srt> <new.srt> [阈值]")
        sys.exit(1)

    threshold = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5

    clipper = TimelineRemapClipper(
        video_path=sys.argv[1],
        original_srt_path=sys.argv[2],
        new_srt_path=sys.argv[3],
        output_dir="output",
        threshold=threshold
    )

    results = clipper.process()

    if results.get('success'):
        print(f"\n✅ 时间轴重映射成功！")
        print(f"输出: {results['remapped_video']}")
        print(f"原视频时长: {results['original_duration']:.2f}秒")
        print(f"新视频时长: {results['final_duration']:.2f}秒")
        print(f"时长变化: {results['duration_change']:+.2f}秒")
    else:
        print(f"\n❌ 重映射失败: {results.get('error')}")
