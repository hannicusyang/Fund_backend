#!/bin/bash
# 启动脚本 - 支持多环境，后台运行

# 用法: ./start.sh [development|test|production]
# 默认: development

ENV=${1:-development}
LOG_DIR="$(dirname "$0")/logs"
PID_DIR="$(dirname "$0")/pids"

# 创建日志和PID目录
mkdir -p "$LOG_DIR" "$PID_DIR"

# 设置Flask环境
export FLASK_ENV=$ENV

echo "=========================================="
echo "  基金管理系统 - 后端启动"
echo "=========================================="
echo "启动环境: $ENV"
echo "日志文件: $LOG_DIR/backend-$ENV.log"
echo "PID文件: $PID_DIR/backend-$ENV.pid"
echo "=========================================="

# 检查是否已运行
if [ -f "$PID_DIR/backend-$ENV.pid" ]; then
    OLD_PID=$(cat "$PID_DIR/backend-$ENV.pid")
    if kill -0 $OLD_PID 2>/dev/null; then
        echo "警告: 后端服务已在运行 (PID: $OLD_PID)"
        echo "如需重启，请先执行 ./stop.sh"
        exit 1
    else
        rm -f "$PID_DIR/backend-$ENV.pid"
    fi
fi

# 启动后端
nohup python3 app.py > "$LOG_DIR/backend-$ENV.log" 2>&1 &
PID=$!
echo $PID > "$PID_DIR/backend-$ENV.pid"

sleep 2

# 检查是否启动成功
if kill -0 $PID 2>/dev/null; then
    echo "后端服务启动成功 (PID: $PID)"
    echo "访问地址: http://localhost:5000"
else
    echo "错误: 后端服务启动失败"
    echo "请查看日志: $LOG_DIR/backend-$ENV.log"
    rm -f "$PID_DIR/backend-$ENV.pid"
    exit 1
fi
