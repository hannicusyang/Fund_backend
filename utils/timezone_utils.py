# 时区工具
from datetime import datetime, timezone, timedelta

# 东八区时区
SHANGHAI_TZ = timezone(timedelta(hours=8))

def now():
    """获取当前东八区时间"""
    return datetime.now(SHANGHAI_TZ)

def utcnow():
    """获取当前UTC时间（兼容旧代码）"""
    return datetime.utcnow()
