#!/bin/bash
# 快速查看最近生成的调整视频

echo "═══════════════════════════════════════════════════════════"
echo "            迭代调整剪辑 - 查看生成的视频"
echo "═══════════════════════════════════════════════════════════"
echo ""

# 项目目录
PROJECT_DIR="/Users/ruite_ios/Desktop/aiShortVideo/videorecomp/videodown"
cd "$PROJECT_DIR" || exit 1

echo "📁 全局输出目录的视频（output/）："
echo "─────────────────────────────────────────────────────────────"
if ls output/adjusted_*.mp4 1> /dev/null 2>&1; then
    ls -lht output/adjusted_*.mp4 | head -10 | awk '{printf "  %s %2s %5s %6s  %s\n", $6, $7, $8, $5, $9}'
    echo ""
    echo "  总数: $(ls output/adjusted_*.mp4 2>/dev/null | wc -l | tr -d ' ') 个视频"
else
    echo "  （暂无视频）"
fi

echo ""
echo "📁 任务目录的视频（最近5个）："
echo "─────────────────────────────────────────────────────────────"
TASK_VIDEOS=$(find videorecomp/backend/tasks -name "timeline_remapped_video.mp4" -type f 2>/dev/null | head -5)
if [ -n "$TASK_VIDEOS" ]; then
    echo "$TASK_VIDEOS" | while read video; do
        SIZE=$(ls -lh "$video" | awk '{print $5}')
        TIME=$(stat -f "%Sm" "$video" | cut -d' ' -f1-3)
        echo "  [$TIME] $SIZE"
        echo "    → $video"
    done
    TOTAL=$(find videorecomp/backend/tasks -name "timeline_remapped_video.mp4" -type f 2>/dev/null | wc -l | tr -d ' ')
    echo "  总数: $TOTAL 个视频"
else
    echo "  （暂无视频）"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "💡 提示："
echo "  - Web界面下载：点击'下载视频'按钮"
echo "  - 直接访问：使用上述路径"
echo "  - 详细说明：查看 VIDEO_SAVE_LOCATIONS.md"
echo "═══════════════════════════════════════════════════════════"
