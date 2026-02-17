#!/bin/bash
# 停止脚本

ENV=${1:-development}
PID_DIR="$(dirname "$0")/pids"

echo "=========================================="
echo "  基金管理系统 - 后端停止"
echo "=========================================="

if [ -f "$PID_DIR/backend-$ENV.pid" ]; then
    PID=$(cat "$PID_DIR/backend-$ENV.pid")
    if kill -0 $PID 2>/dev/null; then
        echo "正在停止后端服务 (PID: $PID)..."
        kill $PID
        sleep 1
        if kill -0 $PID 2>/dev/null; then
            kill -9 $PID
        fi
        echo "后端服务已停止"
    else
        echo "后端服务未运行"
    fi
    rm -f "$PID_DIR/backend-$ENV.pid"
else
    echo "未找到PID文件，请确认服务是否在运行"
    # 尝试通过端口查找
    PID=$(lsof -ti:5000 2>/dev/null)
    if [ -n "$PID" ]; then
        echo "发现进程 $PID 正在使用端口5000，是否停止? (y/n)"
        read -r answer
        if [ "$answer" = "y" ]; then
            kill $PID
            echo "已停止"
        fi
    fi
fi
