# config/unified_config.py
# 统一配置管理
# 所有配置项都应在此文件中定义，避免分散在多个文件中

import os
from typing import Optional
from functools import lru_cache


class UnifiedConfig:
    """统一配置管理类"""
    
    # ==================== 环境配置 ====================
    ENV: str = os.getenv('FLASK_ENV', 'development')
    DEBUG: bool = ENV != 'production'
    
    # ==================== 服务器配置 ====================
    HOST: str = '::'
    PORT: int = 5000
    
    # ==================== 数据库配置 ====================
    DB_HOST: str = os.getenv('DB_HOST', '192.168.31.174')
    DB_PORT: int = int(os.getenv('DB_PORT', '3306'))
    DB_USER: str = os.getenv('DB_USER', 'root')
    DB_PASSWORD: str = os.getenv('DB_PASSWORD', 'yangqi')
    DB_NAME: str = os.getenv('DB_DATABASE', 'fund_db')
    
    # 数据库连接池配置
    DB_POOL_SIZE: int = int(os.getenv('DB_POOL_SIZE', '10'))
    DB_POOL_RECYCLE: int = int(os.getenv('DB_POOL_RECYCLE', '3600'))
    DB_MAX_OVERFLOW: int = int(os.getenv('DB_MAX_OVERFLOW', '20'))
    DB_POOL_TIMEOUT: int = int(os.getenv('DB_POOL_TIMEOUT', '30'))
    
    # ==================== Redis 配置 ====================
    REDIS_HOST: str = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT: int = int(os.getenv('REDIS_PORT', '6379'))
    REDIS_DB: int = int(os.getenv('REDIS_DB', '0'))
    REDIS_PASSWORD: Optional[str] = os.getenv('REDIS_PASSWORD', None)
    
    # ==================== API 配置 ====================
    # MiniMax API
    MINIMAX_API_KEY: str = os.getenv('MINIMAX_API_KEY', '')
    MINIMAX_BASE_URL: str = os.getenv('MINIMAX_BASE_URL', 'https://api.minimaxi.com/v1')
    
    # Kimi API
    KIMI_API_KEY: str = os.getenv('KIMI_API_KEY', '')
    KIMI_BASE_URL: str = os.getenv('KIMI_BASE_URL', 'https://api.kimi.com/coding')
    
    # ==================== 前端配置 ====================
    FRONTEND_URL: str = os.getenv('FRONTEND_URL', 'http://localhost:5173')
    
    # ==================== 安全配置 ====================
    SECRET_KEY: str = os.getenv('SECRET_KEY', 'your-secret-key-here')
    
    # ==================== CORS 配置 ====================
    CORS_ORIGINS: list = ['*']
    
    # ==================== 日志配置 ====================
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE: str = os.getenv('LOG_FILE', 'logs/app.log')
    
    # ==================== 定时任务配置 ====================
    # 基金估值抓取间隔（分钟）
    ESTIMATION_INTERVAL: int = int(os.getenv('ESTIMATION_INTERVAL', '3'))
    # 股票行情同步间隔（秒）
    STOCK_REALTIME_INTERVAL: int = int(os.getenv('STOCK_REALTIME_INTERVAL', '60'))
    
    @classmethod
    def get_db_url(cls) -> str:
        """获取数据库连接 URL"""
        return f"mysql+pymysql://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}?charset=utf8mb4"
    
    @classmethod
    def get_redis_url(cls) -> str:
        """获取 Redis 连接 URL"""
        if cls.REDIS_PASSWORD:
            return f"redis://:{cls.REDIS_PASSWORD}@{cls.REDIS_HOST}:{cls.REDIS_PORT}/{cls.REDIS_DB}"
        return f"redis://{cls.REDIS_HOST}:{cls.REDIS_PORT}/{cls.REDIS_DB}"
    
    @classmethod
    def get_engine_options(cls) -> dict:
        """获取 SQLAlchemy 引擎配置"""
        return {
            'pool_size': cls.DB_POOL_SIZE,
            'pool_recycle': cls.DB_POOL_RECYCLE,
            'pool_pre_ping': True,
            'max_overflow': cls.DB_MAX_OVERFLOW,
            'pool_timeout': cls.DB_POOL_TIMEOUT,
        }
    
    @classmethod
    def load_from_env(cls):
        """从环境变量加载配置（用于覆盖默认配置）"""
        env = os.getenv('FLASK_ENV', 'development')
        
        # 根据环境覆盖配置
        if env == 'production':
            cls.PORT = 51717
            cls.FRONTEND_URL = 'http://hannicusworld.asia:11717'
            cls.DEBUG = False
        elif env == 'test':
            cls.DEBUG = True
            cls.PORT = 5000
        
        return cls


# 创建全局配置实例
unified_config = UnifiedConfig.load_from_env()
