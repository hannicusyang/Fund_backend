# config/app_config.py
import os
from .env_config import config, ENV
from .mysql_config import DB_URL


class AppConfig:
    """Flask 应用的核心配置"""

    # 数据库
    SQLALCHEMY_DATABASE_URI = DB_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 数据库连接池配置
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,              # 连接池大小
        'pool_recycle': 3600,          # 连接回收时间（秒）
        'pool_pre_ping': True,         # 使用前检测连接
        'max_overflow': 20,            # 最大溢出连接数
        'pool_timeout': 30,            # 连接超时时间
    }

    # 安全（未来扩展用）
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')  # 生产环境请用环境变量

    # 调试模式
    DEBUG = config['DEBUG']

    # 前端地址（用于CORS等）
    FRONTEND_URL = config['FRONTEND_URL']

    # 其他 Flask 配置...
    JSON_AS_ASCII = False  # 中文 JSON 不转义