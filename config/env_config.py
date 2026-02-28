# config/env_config.py
import os

# 环境: development, test, production
ENV = os.getenv('FLASK_ENV', 'development')

# MiniMax API 配置
# 使用Anthropic兼容格式
MINIMAX_API_KEY = os.getenv('MINIMAX_API_KEY', 'sk-cp-wnncftw40-0FXBvMvNkPQeIaJdDQ6iCb5DGT1PlwWY0BfCHsvpruGqrd0RX8B0p8SROBNdHvEjAgAhslgNHXw6pqe6ZQVbCW87MHk5GrGMYArT6BOr2jc4w')
MINIMAX_BASE_URL = os.getenv('MINIMAX_BASE_URL', 'https://api.minimaxi.com/anthropic')

# 各环境配置
ENV_CONFIGS = {
    'development': {
        'DEBUG': True,
        'HOST': '::',  # 监听所有IPv4和IPv6地址
        'PORT': 5000,
        'FRONTEND_URL': 'http://localhost:5173',
        'DB_HOST': '10.60.134.151',
    },
    'test': {
        'DEBUG': True,
        'HOST': '::',
        'PORT': 5000,
        'FRONTEND_URL': 'http://test.example.com',
        'DB_HOST': '10.60.134.151',
    },
    'production': {
        'DEBUG': False,
        'HOST': '::',
        'PORT': 51717,
        'FRONTEND_URL': 'http://hannicusworld.asia:11717',
        'DB_HOST': '10.60.134.151'
    }
}

# 当前环境配置
config = ENV_CONFIGS[ENV]
