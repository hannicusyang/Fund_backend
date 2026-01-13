# config/app_config.py
from .mysql_config import DB_URL


class AppConfig:
    """Flask 应用的核心配置"""

    # 数据库
    SQLALCHEMY_DATABASE_URI = DB_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 安全（未来扩展用）
    SECRET_KEY = 'your-secret-key-here'  # 生产环境请用环境变量

    # 调试模式
    DEBUG = False

    # 其他 Flask 配置...
    JSON_AS_ASCII = False  # 中文 JSON 不转义