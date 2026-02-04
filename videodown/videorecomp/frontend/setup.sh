#!/bin/bash
# 前端应用 - 环境设置脚本

set -e

echo "========================================"
echo "视频重新生成工具 - 前端环境设置"
echo "========================================"
echo ""

# 检查Node.js
echo "检查Node.js..."
if ! command -v node &> /dev/null; then
    echo "错误: 未安装Node.js"
    echo "请安装Node.js 18+: https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node --version)
echo "找到Node.js: $NODE_VERSION"

# 检查npm
if ! command -v npm &> /dev/null; then
    echo "错误: 未安装npm"
    exit 1
fi

NPM_VERSION=$(npm --version)
echo "找到npm: $NPM_VERSION"

# 安装依赖
echo ""
echo "安装前端依赖..."
npm install

echo ""
echo "========================================"
echo "前端环境设置完成！"
echo "========================================"
echo ""
echo "使用方法:"
echo "  开发模式: npm run dev"
echo "  构建生产版本: npm run build"
echo "  预览生产版本: npm run preview"
echo ""
echo "开发服务器地址: http://localhost:3000"
echo ""
