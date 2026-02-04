#!/bin/bash
# 快捷启动脚本 - 自动进入videorecomp目录启动服务

cd "$(dirname "$0")/videorecomp" && ./start-web.sh
