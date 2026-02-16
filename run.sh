#!/bin/bash
# 启动脚本 - 支持环境切换

# 用法: ./run.sh [development|test|production]
# 默认: development

ENV=${1:-development}

export FLASK_ENV=$ENV

echo "启动环境: $ENV"
python3 app.py
