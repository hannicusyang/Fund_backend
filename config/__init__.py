# config/__init__.py
from .mysql_config import DB_URL
from .logging_config import logger

# 可选：暴露更多配置项
__all__ = ['DB_URL', 'logger']