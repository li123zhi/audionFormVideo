#!/bin/bash
# 视频重新生成工具 - Web应用一键启动脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR" || exit 1

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}视频重新生成工具 - Web应用${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查后端虚拟环境
if [ ! -d "backend/venv" ]; then
    echo -e "${YELLOW}后端虚拟环境不存在，正在设置...${NC}"
    cd backend
    ./setup.sh
    cd ..
fi

# 检查前端node_modules
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}前端依赖未安装，正在设置...${NC}"
    cd frontend
    ./setup.sh
    cd ..
fi

# 停止已运行的服务
echo -e "${YELLOW}清理旧服务和占用的端口...${NC}"

# 从PID文件停止（如果存在）
if [ -f ".backend.pid" ]; then
    OLD_PID=$(cat .backend.pid)
    if ps -p $OLD_PID > /dev/null 2>&1; then
        kill -9 $OLD_PID 2>/dev/null || true
        echo -e "${YELLOW}  • 停止旧后端进程 (PID: $OLD_PID)${NC}"
    fi
    rm -f .backend.pid
fi

if [ -f ".frontend.pid" ]; then
    OLD_PID=$(cat .frontend.pid)
    if ps -p $OLD_PID > /dev/null 2>&1; then
        kill -9 $OLD_PID 2>/dev/null || true
        echo -e "${YELLOW}  • 停止旧前端进程 (PID: $OLD_PID)${NC}"
    fi
    rm -f .frontend.pid
fi

# 通过进程名清理
pkill -9 -f "python.*backend/app.py" 2>/dev/null && echo -e "${YELLOW}  • 清理后端Python进程${NC}" || true
pkill -9 -f "vite.*frontend" 2>/dev/null && echo -e "${YELLOW}  • 清理前端Vite进程${NC}" || true

# 清理占用5001端口的进程
PORT_5001_PIDS=$(lsof -ti :5001 2>/dev/null)
if [ -n "$PORT_5001_PIDS" ]; then
    echo -e "${YELLOW}  • 发现端口5001被占用，正在清理...${NC}"
    echo "$PORT_5001_PIDS" | xargs kill -9 2>/dev/null || true
fi

# 清理占用3000端口的进程
PORT_3000_PIDS=$(lsof -ti :3000 2>/dev/null)
if [ -n "$PORT_3000_PIDS" ]; then
    echo -e "${YELLOW}  • 发现端口3000被占用，正在清理...${NC}"
    echo "$PORT_3000_PIDS" | xargs kill -9 2>/dev/null || true
fi

sleep 2
echo -e "${GREEN}✓ 所有旧服务和端口已清理${NC}"

# 启动后端
echo ""
echo -e "${GREEN}启动后端API服务...${NC}"
cd backend
source venv/bin/activate
# 直接在终端输出（python -u 禁用缓冲确保实时显示）
python -u app.py 2>&1 &
BACKEND_PID=$!
cd ..

# 等待后端启动
echo -e "${YELLOW}等待后端服务启动...${NC}"
sleep 3

# 检查后端是否启动成功
if ! ps -p $BACKEND_PID > /dev/null; then
    echo -e "${RED}后端启动失败！${NC}"
    echo -e "${RED}请检查上方的错误信息${NC}"
    exit 1
fi

echo -e "${GREEN}✓ 后端API服务已启动 (PID: $BACKEND_PID)${NC}"

# 启动前端
echo ""
echo -e "${GREEN}启动前端开发服务器...${NC}"
cd frontend
# 直接在终端输出
npm run dev 2>&1 &
FRONTEND_PID=$!
cd ..

# 等待前端启动
echo -e "${YELLOW}等待前端服务启动...${NC}"
sleep 3

# 检查前端是否启动成功
if ! ps -p $FRONTEND_PID > /dev/null; then
    echo -e "${RED}前端启动失败！${NC}"
    echo -e "${RED}请检查上方的错误信息${NC}"
    exit 1
fi

echo -e "${GREEN}✓ 前端开发服务器已启动 (PID: $FRONTEND_PID)${NC}"

# 保存PID到文件
echo $BACKEND_PID > .backend.pid
echo $FRONTEND_PID > .frontend.pid

# 显示启动信息
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}所有服务已成功启动！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}服务地址:${NC}"
echo -e "  • 前端应用: ${GREEN}http://localhost:3000${NC}"
echo -e "  • 后端API:  ${GREEN}http://localhost:5001${NC}"
echo ""
echo -e "${BLUE}进程信息:${NC}"
echo -e "  • 后端PID: $BACKEND_PID"
echo -e "  • 前端PID: $FRONTEND_PID"
echo ""
echo -e "${BLUE}日志输出:${NC}"
echo -e "  • 日志直接显示在终端"
echo ""
echo -e "${YELLOW}停止服务:${NC}"
echo -e "  • 运行: ${GREEN}./stop-web.sh${NC}"
echo -e "  • 或按: ${RED}Ctrl+C${NC}"
echo ""
echo -e "${GREEN}========================================${NC}"
echo ""

# 等待用户中断
trap "echo -e '${YELLOW}正在停止服务...${NC}'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; rm -f .backend.pid .frontend.pid; echo -e '${GREEN}服务已停止${NC}'; exit 0" INT TERM

# 持续监控进程
while true; do
    sleep 5

    # 检查后端是否还在运行
    if ! ps -p $BACKEND_PID > /dev/null 2>&1; then
        echo -e "${RED}后端服务已停止！${NC}"
        kill $FRONTEND_PID 2>/dev/null
        exit 1
    fi

    # 检查前端是否还在运行
    if ! ps -p $FRONTEND_PID > /dev/null 2>&1; then
        echo -e "${RED}前端服务已停止！${NC}"
        kill $BACKEND_PID 2>/dev/null
        exit 1
    fi
done
