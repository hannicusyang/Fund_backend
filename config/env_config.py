# config/env_config.py
import os

# 环境: development, test, production
ENV = os.getenv('FLASK_ENV', 'development')

# 各环境配置
ENV_CONFIGS = {
    'development': {
        'DEBUG': True,
        'HOST': '0.0.0.0',  # 监听所有IPv4地址
        'PORT': 5000,
        'FRONTEND_URL': 'http://localhost:5173',
        'DB_HOST': '10.60.134.151',
    },
    'test': {
        'DEBUG': True,
        'HOST': '0.0.0.0',
        'PORT': 5000,
        'FRONTEND_URL': 'http://test.example.com',
        'DB_HOST': '10.60.134.151',
    },
    'production': {
        'DEBUG': False,
        'HOST': '0.0.0.0',
        'PORT': 51717,
        'FRONTEND_URL': 'http://hannicusworld.asia:11717',
        'DB_HOST': '10.60.134.151',
    }
}

# 当前环境配置
config = ENV_CONFIGS[ENV]
