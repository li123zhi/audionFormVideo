#!/bin/bash
# 快捷停止脚本 - 自动进入videorecomp目录停止服务

cd "$(dirname "$0")/videorecomp" && ./stop-web.sh
