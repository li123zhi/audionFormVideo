#!/bin/bash
# 后端API服务 - 环境设置脚本

set -e

echo "========================================"
echo "视频重新生成工具 - 后端API环境设置"
echo "========================================"
echo ""

# 检查Python版本
echo "检查Python版本..."
PYTHON_CMD=""

for cmd in python3.12 python3.13 python3.14 python3; do
    if command -v $cmd &> /dev/null; then
        VERSION=$($cmd --version 2>&1 | awk '{print $2}')
        MAJOR=$(echo $VERSION | cut -d. -f1)
        MINOR=$(echo $VERSION | cut -d. -f2)

        if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 12 ]; then
            PYTHON_CMD=$cmd
            echo "找到Python $VERSION: $cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "错误: 需要Python 3.12或更高版本"
    exit 1
fi

# 创建虚拟环境
echo ""
echo "创建Python虚拟环境..."
if [ -d "venv" ]; then
    echo "虚拟环境已存在，删除旧环境..."
    rm -rf venv
fi
$PYTHON_CMD -m venv venv
echo "虚拟环境创建成功 (Python $VERSION)"

# 激活虚拟环境
echo ""
echo "激活虚拟环境..."
source venv/bin/activate

# 升级pip
echo ""
echo "升级pip..."
pip install --upgrade pip -q

# 安装依赖
echo ""
echo "安装项目依赖..."
pip install -r requirements.txt

# 创建必要的目录
echo ""
echo "创建必要的目录..."
mkdir -p uploads downloads tasks

echo ""
echo "========================================"
echo "后端环境设置完成！"
echo "========================================"
echo ""
echo "使用方法:"
echo "  1. 激活虚拟环境: source venv/bin/activate"
echo "  2. 启动API服务: python app.py"
echo "  3. 退出虚拟环境: deactivate"
echo ""
echo "API服务地址: http://localhost:5000"
echo ""
