#!/bin/bash
# 使用示例：根据新字幕重新剪辑视频

# 设置你的文件路径（请修改为实际路径）
VIDEO_FILE="your_video.mp4"
ORIGINAL_SRT="original_chinese.srt"
NEW_SRT="new_english.srt"

echo "================================"
echo "视频重新剪辑 - 使用示例"
echo "================================"
echo ""

# 检查文件是否存在
if [ ! -f "$VIDEO_FILE" ]; then
    echo "❌ 视频文件不存在: $VIDEO_FILE"
    echo ""
    echo "请修改脚本中的文件路径为你的实际文件路径："
    echo "  VIDEO_FILE=\"你的视频.mp4\""
    echo "  ORIGINAL_SRT=\"原字幕.srt\""
    echo "  NEW_SRT=\"新字幕.srt\""
    exit 1
fi

if [ ! -f "$ORIGINAL_SRT" ]; then
    echo "❌ 原字幕文件不存在: $ORIGINAL_SRT"
    exit 1
fi

if [ ! -f "$NEW_SRT" ]; then
    echo "❌ 新字幕文件不存在: $NEW_SRT"
    exit 1
fi

echo "✅ 文件检查通过"
echo "  视频: $VIDEO_FILE"
echo "  原字幕: $ORIGINAL_SRT"
echo "  新字幕: $NEW_SRT"
echo ""

# 创建输出目录
mkdir -p output

# 执行视频剪辑
echo "开始处理..."
python quick_start_example.py "$VIDEO_FILE" "$ORIGINAL_SRT" "$NEW_SRT"

echo ""
echo "✅ 处理完成！"
echo "输出文件在 output/ 目录中"
