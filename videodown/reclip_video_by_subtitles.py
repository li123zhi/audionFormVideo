#!/usr/bin/env python3.12
"""
视频重新剪辑工具
根据新字幕时间戳重新剪辑原视频，达到音画同步
"""

import os
import sys
import pysrt
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Tuple
import chardet


class VideoReclipper:
    """视频重新剪辑器"""

    def __init__(
        self,
        video_path: str,
        new_subtitle_path: str,
        output_dir: str = "output"
    ):
        """
        初始化视频重新剪辑器

        Args:
            video_path: 原视频文件路径
            new_subtitle_path: 新字幕文件路径（目标时间戳）
            output_dir: 输出目录
        """
        self.video_path = video_path
        self.new_subtitle_path = new_subtitle_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.temp_dir = Path(tempfile.mkdtemp(prefix="video_reclip_"))
        self.new_subs = None

    def load_subtitle(self):
        """加载新字幕文件"""
        print(f"加载字幕文件: {self.new_subtitle_path}")

        # 检测编码
        with open(self.new_subtitle_path, 'rb') as f:
            raw_data = f.read()
            result = chardet.detect(raw_data)
            encoding = result['encoding'] or 'utf-8'

        self.new_subs = pysrt.open(self.new_subtitle_path, encoding=encoding)
        print(f"✅ 加载了 {len(self.new_subs)} 条字幕")

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
            print("警告: 无法获取视频时长")
            return 0.0

    def extract_segments(self) -> List[Tuple[float, float]]:
        """
        根据新字幕提取视频片段

        Returns:
            片段列表 [(start, end), ...]
        """
        if not self.new_subs:
            self.load_subtitle()

        segments = []
        video_duration = self.get_video_duration()

        print(f"\n根据新字幕生成视频片段...")

        for sub in self.new_subs:
            start_time = sub.start.ordinal / 1000.0
            end_time = sub.end.ordinal / 1000.0

            # 确保时间在视频范围内
            start_time = max(0, start_time)
            end_time = min(video_duration, end_time)

            if end_time > start_time:
                segments.append((start_time, end_time))

        print(f"生成了 {len(segments)} 个片段")

        return segments

    def merge_adjacent_segments(
        self,
        segments: List[Tuple[float, float]],
        gap_threshold: float = 0.5
    ) -> List[Tuple[float, float]]:
        """
        合并相邻的片段

        Args:
            segments: 片段列表
            gap_threshold: 间隙阈值（秒），小于此值则合并

        Returns:
            合并后的片段列表
        """
        if not segments:
            return []

        merged = []
        current_start, current_end = segments[0]

        for start, end in segments[1:]:
            if start - current_end <= gap_threshold:
                # 合并片段
                current_end = end
            else:
                merged.append((current_start, current_end))
                current_start, current_end = start, end

        merged.append((current_start, current_end))

        print(f"合并后剩余 {len(merged)} 个片段")

        return merged

    def extract_video_segments(
        self,
        segments: List[Tuple[float, float]],
        merge_gap: float = 0.5
    ) -> List[str]:
        """
        提取视频片段

        Args:
            segments: 时间片段列表
            merge_gap: 合并间隙阈值

        Returns:
            提取的片段文件路径列表
        """
        # 合并相邻片段
        merged_segments = self.merge_adjacent_segments(segments, merge_gap)

        segment_files = []

        print(f"\n提取视频片段...")

        for i, (start, end) in enumerate(merged_segments):
            output_file = self.temp_dir / f"segment_{i:03d}.mp4"
            duration = end - start

            print(f"片段{i+1}: {start:.3f}s - {end:.3f}s (时长: {duration:.3f}s)")

            # 使用ffmpeg提取片段（使用-c copy快速提取）
            cmd = [
                'ffmpeg', '-y',
                '-ss', str(start),
                '-i', self.video_path,
                '-t', str(duration),
                '-c', 'copy',
                '-avoid_negative_ts', '1',
                str(output_file)
            ]

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5分钟超时
                )

                if result.returncode == 0 and output_file.exists() and output_file.stat().st_size > 1000:
                    segment_files.append(str(output_file))
                    print(f"  ✅ 提取成功: {output_file.name}")
                else:
                    print(f"  ⚠️  提取失败: {result.stderr}")
            except subprocess.TimeoutExpired:
                print(f"  ⚠️  提取超时")
            except Exception as e:
                print(f"  ⚠️  提取出错: {e}")

        return segment_files

    def concat_segments(self, segment_files: List[str], output_name: str = "reclipped_video.mp4") -> str:
        """
        拼接视频片段

        Args:
            segment_files: 片段文件路径列表
            output_name: 输出文件名

        Returns:
            拼接后的视频文件路径
        """
        if not segment_files:
            raise ValueError("没有可拼接的片段")

        # 创建拼接列表文件
        concat_list = self.temp_dir / "concat_list.txt"
        with open(concat_list, 'w') as f:
            for segment_file in segment_files:
                f.write(f"file '{segment_file}'\n")

        # 拼接视频
        output_path = self.output_dir / output_name

        print(f"\n拼接视频片段...")

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

    def embed_subtitle(
        self,
        video_path: str,
        subtitle_path: str,
        output_name: str = "final_with_subtitle.mp4",
        hard_subtitle: bool = True
    ) -> str:
        """
        为视频添加字幕

        Args:
            video_path: 视频文件路径
            subtitle_path: 字幕文件路径
            output_name: 输出文件名
            hard_subtitle: 是否硬字幕（True=烧录到画面，False=软字幕）

        Returns:
            带字幕的视频文件路径
        """
        output_path = self.output_dir / output_name

        print(f"\n添加{'硬' if hard_subtitle else '软'}字幕...")

        if hard_subtitle:
            # 硬字幕（烧录到画面）
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vf', f"subtitles='{subtitle_path}'",
                '-c:a', 'copy',
                str(output_path)
            ]
        else:
            # 软字幕（可开关）
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', subtitle_path,
                '-c', 'copy',
                '-c:s', 'mov_text',
                '-metadata:s:s:0', 'language=eng',
                '-movflags', '+faststart',
                str(output_path)
            ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1000:
                print(f"✅ 字幕添加成功: {output_path}")
                return str(output_path)
            else:
                print(f"⚠️  字幕添加失败: {result.stderr}")
                return None
        except subprocess.TimeoutExpired:
            print(f"⚠️  字幕添加超时")
            return None
        except Exception as e:
            print(f"⚠️  字幕添加出错: {e}")
            return None

    def process(
        self,
        merge_gap: float = 0.5,
        embed_subtitle: bool = True,
        hard_subtitle: bool = False
    ) -> dict:
        """
        执行完整的视频重新剪辑流程

        Args:
            merge_gap: 合并相邻片段的间隙阈值（秒）
            embed_subtitle: 是否嵌入字幕
            hard_subtitle: 是否硬字幕

        Returns:
            处理结果字典
        """
        results = {}

        try:
            # 1. 加载字幕
            self.load_subtitle()

            # 2. 生成片段
            segments = self.extract_segments()

            # 3. 提取片段
            segment_files = self.extract_video_segments(segments, merge_gap)

            if not segment_files:
                raise ValueError("没有成功提取任何视频片段")

            # 4. 拼接片段
            reclipped_video = self.concat_segments(segment_files)

            if not reclipped_video:
                raise ValueError("视频拼接失败")

            results['reclipped_video'] = reclipped_video

            # 5. 嵌入字幕
            if embed_subtitle:
                video_with_subtitle = self.embed_subtitle(
                    reclipped_video,
                    self.new_subtitle_path,
                    output_name="final_with_subtitle.mp4",
                    hard_subtitle=hard_subtitle
                )

                if video_with_subtitle:
                    results['video_with_subtitle'] = video_with_subtitle

            print(f"\n✅ 视频重新剪辑完成！")
            print(f"   输出目录: {self.output_dir}")

            return results

        except Exception as e:
            print(f"❌ 处理失败: {e}")
            import traceback
            traceback.print_exc()
            return results

        finally:
            # 清理临时文件
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                print(f"\n已清理临时文件: {self.temp_dir}")

    def cleanup(self):
        """清理临时文件"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='根据新字幕时间戳重新剪辑视频')
    parser.add_argument('video', help='原视频文件路径')
    parser.add_argument('subtitle', help='新字幕文件路径')
    parser.add_argument('-o', '--output', default='output', help='输出目录（默认：output）')
    parser.add_argument('-m', '--merge-gap', type=float, default=0.5, help='合并相邻片段的间隙阈值（秒，默认：0.5）')
    parser.add_argument('--no-subtitle', action='store_true', help='不嵌入字幕')
    parser.add_argument('--hard-subtitle', action='store_true', help='使用硬字幕（烧录到画面）')

    args = parser.parse_args()

    # 创建剪辑器
    clipper = VideoReclipper(
        video_path=args.video,
        new_subtitle_path=args.subtitle,
        output_dir=args.output
    )

    # 执行处理
    results = clipper.process(
        merge_gap=args.merge_gap,
        embed_subtitle=not args.no_subtitle,
        hard_subtitle=args.hard_subtitle
    )

    # 打印结果
    print("\n生成文件:")
    for name, path in results.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
