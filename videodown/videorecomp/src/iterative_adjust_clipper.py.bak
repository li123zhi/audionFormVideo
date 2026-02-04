#!/usr/bin/env python3.12
"""
迭代调整剪辑器 - 按节点逐步调整视频
按照用户的规则：每次对比后生成新视频，下次对比使用新视频
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


class IterativeAdjustClipper:
    """迭代调整剪辑器"""

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

        self.temp_dir = Path(tempfile.mkdtemp(prefix="iterative_clip_"))
        self.original_subs = None
        self.new_subs = None
        self.current_video = video_path  # 当前使用的视频
        self.current_subs = None  # 当前字幕（会随着调整而更新）
        self.video_offset = 0.0  # 视频累积偏移量（正数表示视频比原视频长，负数表示短）

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
        self.current_subs = list(self.original_subs)  # 复制一份，用于更新

        print(f"原字幕: {len(self.original_subs)} 条")
        print(f"新字幕: {len(self.new_subs)} 条")

    def get_video_duration(self, video_path: str) -> float:
        """获取视频时长"""
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', video_path]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            import json
            info = json.loads(result.stdout)
            return float(info['format']['duration'])
        except:
            return 0.0

    def update_subtitle_times(self, from_index: int, time_offset: float):
        """
        更新从from_index开始的所有字幕的时间戳

        Args:
            from_index: 从哪个索引开始更新
            time_offset: 时间偏移量（秒），正数表示时间前移，负数表示后移
        """
        print(f"  更新字幕{from_index+1}及之后的时间戳，偏移量: {time_offset:+.3f}秒")

        for i in range(from_index, len(self.current_subs)):
            sub = self.current_subs[i]

            # 转换为秒
            start_seconds = sub.start.ordinal / 1000.0
            end_seconds = sub.end.ordinal / 1000.0

            # 应用偏移
            new_start = max(0, start_seconds - time_offset)
            new_end = max(0, end_seconds - time_offset)

            # 转换回pysrt时间格式
            sub.start = pysrt.SubRipTime.from_ordinal(int(new_start * 1000))
            sub.end = pysrt.SubRipTime.from_ordinal(int(new_end * 1000))

    def clip_segment_at_point(
        self,
        video_path: str,
        clip_point: float,
        duration_to_remove: float
    ) -> Optional[str]:
        """
        在指定时间点前剪掉指定时长的视频

        Args:
            video_path: 输入视频路径
            clip_point: 剪切点（秒）
            duration_to_remove: 要剪掉的时长（秒）

        Returns:
            输出视频路径
        """
        # 计算实际要剪掉的片段
        remove_start = clip_point - duration_to_remove
        remove_end = clip_point

        if remove_start < 0:
            print(f"  ⚠️  剪掉起点{remove_start:.3f}秒 < 0，调整为从0开始")
            remove_start = 0
            duration_to_remove = remove_end - remove_start

        print(f"  剪掉 [{remove_start:.3f} - {remove_end:.3f}] 秒，时长: {duration_to_remove:.3f}秒")

        # 使用concat方式：保留 [0 - remove_start] 和 [remove_end - 结束]
        output_path = self.temp_dir / f'clip_{len(os.listdir(self.temp_dir))}.mp4'

        # 获取视频时长
        video_duration = self.get_video_duration(video_path)

        segments_to_extract = []
        segment_1_start = 0
        segment_1_end = remove_start
        segment_2_start = remove_end
        segment_2_end = video_duration

        # 提取第一段
        if segment_1_end > segment_1_start:
            segments_to_extract.append((segment_1_start, segment_1_end))

        # 提取第二段
        if segment_2_end > segment_2_start:
            segments_to_extract.append((segment_2_start, segment_2_end))

        if not segments_to_extract:
            print("  ⚠️  没有可提取的片段")
            return None

        # 提取所有片段
        segment_files = []
        for i, (start, end) in enumerate(segments_to_extract):
            temp_segment = self.temp_dir / f'temp_seg_{i}.mp4'
            duration = end - start

            cmd = [
                'ffmpeg', '-y',
                '-ss', str(start),
                '-i', video_path,
                '-t', str(duration),
                '-c', 'copy',
                '-avoid_negative_ts', '1',
                '-loglevel', 'error',
                str(temp_segment)
            ]

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode == 0 and temp_segment.exists() and temp_segment.stat().st_size > 1000:
                    segment_files.append(str(temp_segment))
                else:
                    print(f"  ⚠️  片段{i+1}提取失败")
                    return None
            except Exception as e:
                print(f"  ⚠️  片段{i+1}提取出错: {e}")
                return None

        # 拼接片段
        concat_list = self.temp_dir / 'concat_list.txt'
        with open(concat_list, 'w') as f:
            for seg_file in segment_files:
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
                print(f"  ✅ 视频剪辑成功")
                return str(output_path)
            else:
                print(f"  ⚠️  视频剪辑失败")
                return None
        except Exception as e:
            print(f"  ⚠️  视频剪辑出错: {e}")
            return None

    def extend_segment_at_point(
        self,
        video_path: str,
        extend_point: float,
        duration_to_add: float
    ) -> Optional[str]:
        """
        在指定时间点前增加指定时长的视频（使用该节点的画面）

        Args:
            video_path: 输入视频路径
            extend_point: 延长点（秒）
            duration_to_add: 要增加的时长（秒）

        Returns:
            输出视频路径
        """
        print(f"  在{extend_point:.3f}秒前增加 {duration_to_add:.3f}秒（使用该节点画面）")

        # 提取 extend_point 位置的一帧，并延长 duration_to_add 秒
        freeze_frame = self.temp_dir / f'freeze_{len(os.listdir(self.temp_dir))}.mp4'

        # 先提取一帧图片
        temp_frame = self.temp_dir / 'frame.png'
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(extend_point),
            '-i', video_path,
            '-vframes', '1',
            '-q:v', '2',
            str(temp_frame)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0 or not temp_frame.exists():
                print(f"  ⚠️  提取帧失败")
                return None
        except Exception as e:
            print(f"  ⚠️  提取帧出错: {e}")
            return None

        # 使用该帧创建视频（从原视频获取音频参数）
        cmd = [
            'ffmpeg', '-y',
            '-loop', '1',
            '-i', str(temp_frame),
            '-t', str(duration_to_add),
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-tune', 'stillimage',
            '-crf', '23',
            '-pix_fmt', 'yuv420p',
            '-an',  # 无音频
            str(freeze_frame)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0 or not freeze_frame.exists():
                print(f"  ⚠️  创建冻结帧视频失败")
                return None
        except Exception as e:
            print(f"  ⚠️  创建冻结帧视频出错: {e}")
            return None

        # 获取视频时长
        video_duration = self.get_video_duration(video_path)

        # 分割视频：[0 - extend_point] + [freeze_frame] + [extend_point - 结束]
        segment_1_start = 0
        segment_1_end = extend_point
        segment_2_start = extend_point
        segment_2_end = video_duration

        segments_to_extract = []
        if segment_1_end > segment_1_start:
            segments_to_extract.append((segment_1_start, segment_1_end))
        if segment_2_end > segment_2_start:
            segments_to_extract.append((segment_2_start, segment_2_end))

        # 提取片段
        segment_files = []
        for i, (start, end) in enumerate(segments_to_extract):
            temp_segment = self.temp_dir / f'temp_seg_{i}.mp4'
            duration = end - start

            cmd = [
                'ffmpeg', '-y',
                '-ss', str(start),
                '-i', video_path,
                '-t', str(duration),
                '-c', 'copy',
                '-avoid_negative_ts', '1',
                '-loglevel', 'error',
                str(temp_segment)
            ]

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode == 0 and temp_segment.exists() and temp_segment.stat().st_size > 1000:
                    segment_files.append(str(temp_segment))
                else:
                    print(f"  ⚠️  片段{i+1}提取失败")
                    return None
            except Exception as e:
                print(f"  ⚠️  片段{i+1}提取出错: {e}")
                return None

        # 插入冻结帧
        segment_files.insert(1, str(freeze_frame))

        # 拼接所有片段
        output_path = self.temp_dir / f'extend_{len(os.listdir(self.temp_dir))}.mp4'
        concat_list = self.temp_dir / 'concat_list.txt'
        with open(concat_list, 'w') as f:
            for seg_file in segment_files:
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
                print(f"  ✅ 视频延长成功")
                return str(output_path)
            else:
                print(f"  ⚠️  视频延长失败")
                return None
        except Exception as e:
            print(f"  ⚠️  视频延长出错: {e}")
            return None

    def process(self) -> Dict:
        """执行迭代调整剪辑流程"""
        results = {}
        adjustment_log = []

        try:
            # 1. 加载字幕
            self.load_subtitles()

            print("\n" + "="*60)
            print("开始迭代调整...")
            print("="*60)

            original_video_duration = self.get_video_duration(self.video_path)
            print(f"原视频时长: {original_video_duration:.2f}秒")

            # 2. 逐个对比调整
            total_adjustments = 0
            total_adjustment_time = 0.0
            cumulative_offset = 0.0  # 累积偏移量：视频相对于原字幕时间的变化

            min_count = min(len(self.original_subs), len(self.new_subs))

            for i in tqdm(range(min_count), desc="对比字幕"):
                # 使用原始字幕时间（不更新）
                orig_sub = self.original_subs[i]
                orig_start = orig_sub.start.ordinal / 1000.0
                orig_end = orig_sub.end.ordinal / 1000.0

                new_sub = self.new_subs[i]
                new_start = new_sub.start.ordinal / 1000.0
                new_end = new_sub.end.ordinal / 1000.0

                # 计算在当前视频中的实际位置
                # 原字幕时间 + 累积偏移 = 当前视频中的位置
                curr_video_start = orig_start + cumulative_offset

                # 计算差值：当前视频中的位置 - 新字幕时间
                time_diff = curr_video_start - new_start

                print(f"\n对比{i+1}:")
                print(f"  原字幕{i+1}: {orig_start:.3f}s")
                print(f"  新字幕{i+1}: {new_start:.3f}s")
                print(f"  当前视频中的位置: {curr_video_start:.3f}s (累积偏移: {cumulative_offset:+.3f}s)")
                print(f"  差值: {time_diff:+.3f}秒")

                # 如果差值的绝对值小于阈值，不处理
                if abs(time_diff) < self.threshold:
                    print(f"  |差值| < {self.threshold}，不处理")
                    adjustment_log.append({
                        'index': i + 1,
                        'time_diff': f"{time_diff:+.3f}",
                        'action': '跳过',
                        'reason': f'差值{time_diff:+.3f}秒 < 阈值{self.threshold}秒'
                    })
                    continue

                # 需要调整
                total_adjustments += 1

                if time_diff > 0:
                    # 当前视频位置晚于新字幕时间，需要剪掉
                    print(f"  差值 > 0，需要剪掉 {time_diff:.3f}秒")

                    # 在 curr_video_start 节点前剪掉 time_diff 秒
                    # 即剪掉 [curr_video_start - time_diff, curr_video_start]
                    new_video = self.clip_segment_at_point(
                        self.current_video,
                        curr_video_start,
                        time_diff
                    )

                    if new_video:
                        self.current_video = new_video
                        total_adjustment_time += time_diff
                        cumulative_offset -= time_diff  # 视频变短了，偏移量减少

                        adjustment_log.append({
                            'index': i + 1,
                            'time_diff': f"{time_diff:+.3f}",
                            'action': '剪掉',
                            'adjustment': f"剪掉{time_diff:.3f}秒",
                            'new_video': new_video,
                            'clip_point': f"{curr_video_start:.3f}s",
                            'cumulative_offset': f"{cumulative_offset:+.3f}s"
                        })
                    else:
                        print(f"  ⚠️  剪掉失败")
                        adjustment_log.append({
                            'index': i + 1,
                            'time_diff': f"{time_diff:+.3f}",
                            'action': '剪掉失败',
                            'error': '视频剪辑失败'
                        })

                else:  # time_diff < 0
                    # 当前视频位置早于新字幕时间，需要增加
                    duration_to_add = abs(time_diff)
                    print(f"  差值 < 0，需要增加 {duration_to_add:.3f}秒")

                    # 在 curr_video_start 节点前增加 duration_to_add 秒
                    new_video = self.extend_segment_at_point(
                        self.current_video,
                        curr_video_start,
                        duration_to_add
                    )

                    if new_video:
                        self.current_video = new_video
                        total_adjustment_time -= duration_to_add  # 负数，表示增加了时长
                        cumulative_offset += duration_to_add  # 视频变长了，偏移量增加

                        adjustment_log.append({
                            'index': i + 1,
                            'time_diff': f"{time_diff:+.3f}",
                            'action': '增加',
                            'adjustment': f"增加{duration_to_add:.3f}秒",
                            'new_video': new_video,
                            'extend_point': f"{curr_video_start:.3f}s",
                            'cumulative_offset': f"{cumulative_offset:+.3f}s"
                        })
                    else:
                        print(f"  ⚠️  增加失败")
                        adjustment_log.append({
                            'index': i + 1,
                            'time_diff': f"{time_diff:+.3f}",
                            'action': '增加失败',
                            'error': '视频延长失败'
                        })

            # 3. 复制最终视频到输出目录
            final_video = self.output_dir / "iterative_adjusted_video.mp4"
            shutil.copy2(self.current_video, final_video)

            final_duration = self.get_video_duration(str(final_video))

            print("\n" + "="*60)
            print("✅ 迭代调整完成！")
            print("="*60)
            print(f"原视频时长: {original_video_duration:.2f}秒")
            print(f"调整后时长: {final_duration:.2f}秒")
            print(f"时长变化: {final_duration - original_video_duration:+.2f}秒")
            print(f"总调整次数: {total_adjustments}")
            print(f"累积偏移量: {cumulative_offset:+.3f}秒")
            print(f"\n输出视频: {final_video}")

            # 4. 导出调整日志
            self.export_adjustment_log(adjustment_log, {
                'original_duration': original_video_duration,
                'final_duration': final_duration,
                'total_adjustments': total_adjustments,
                'total_adjustment_time': total_adjustment_time,
                'cumulative_offset': cumulative_offset
            })

            results['success'] = True
            results['adjusted_video'] = str(final_video)
            results['stats'] = {
                'original_duration': original_video_duration,
                'final_duration': final_duration,
                'duration_change': final_duration - original_video_duration,
                'total_adjustments': total_adjustments,
                'total_adjustment_time': total_adjustment_time,
                'adjustment_log': adjustment_log
            }

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

    def export_adjustment_log(self, adjustment_log: List[Dict], stats: Dict):
        """导出调整日志"""
        import json
        log_data = {
            'stats': stats,
            'adjustments': adjustment_log
        }
        log_path = self.output_dir / "iterative_adjustment_log.json"
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
        print(f"✅ 调整日志已导出: {log_path}")

    def cleanup(self):
        """清理临时文件"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("使用方法: python iterative_adjust_clipper.py <video.mp4> <original.srt> <new.srt> [阈值]")
        sys.exit(1)

    threshold = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5

    clipper = IterativeAdjustClipper(
        video_path=sys.argv[1],
        original_srt_path=sys.argv[2],
        new_srt_path=sys.argv[3],
        output_dir="output",
        threshold=threshold
    )

    results = clipper.process()

    if results.get('success'):
        print(f"\n✅ 迭代调整成功！")
        print(f"输出: {results['adjusted_video']}")
    else:
        print(f"\n❌ 调整失败: {results.get('error')}")
