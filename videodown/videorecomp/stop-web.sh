#!/bin/bash
# 视频重新生成工具 - 停止Web应用脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}正在停止所有服务...${NC}"

# 从PID文件读取并停止
if [ -f ".backend.pid" ]; then
    BACKEND_PID=$(cat .backend.pid)
    if ps -p $BACKEND_PID > /dev/null 2>&1; then
        kill -9 $BACKEND_PID 2>/dev/null
        echo -e "${GREEN}✓ 后端服务已停止 (PID: $BACKEND_PID)${NC}"
    fi
    rm -f .backend.pid
fi

if [ -f ".frontend.pid" ]; then
    FRONTEND_PID=$(cat .frontend.pid)
    if ps -p $FRONTEND_PID > /dev/null 2>&1; then
        kill -9 $FRONTEND_PID 2>/dev/null
        echo -e "${GREEN}✓ 前端服务已停止 (PID: $FRONTEND_PID)${NC}"
    fi
    rm -f .frontend.pid
fi

# 通过进程名杀死进程
pkill -9 -f "python.*backend/app.py" 2>/dev/null && echo -e "${GREEN}✓ 清理后端残留进程${NC}" || true
pkill -9 -f "vite.*frontend" 2>/dev/null && echo -e "${GREEN}✓ 清理前端残留进程${NC}" || true

# 清理占用5001端口的进程
PORT_5001_PIDS=$(lsof -ti :5001 2>/dev/null)
if [ -n "$PORT_5001_PIDS" ]; then
    echo "$PORT_5001_PIDS" | xargs kill -9 2>/dev/null
    echo -e "${GREEN}✓ 清理端口5001占用${NC}"
fi

# 清理占用3000端口的进程
PORT_3000_PIDS=$(lsof -ti :3000 2>/dev/null)
if [ -n "$PORT_3000_PIDS" ]; then
    echo "$PORT_3000_PIDS" | xargs kill -9 2>/dev/null
    echo -e "${GREEN}✓ 清理端口3000占用${NC}"
fi

sleep 1
echo -e "${GREEN}所有服务已完全停止${NC}"
