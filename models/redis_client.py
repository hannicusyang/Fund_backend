# models/redis_client.py
import redis
from config import *

def get_redis_client():
    """获取 Redis 客户端实例"""
    return redis.Redis(
        host=RedisConfig.REDIS_HOST,
        port=RedisConfig.REDIS_PORT,
        db=0,
        password=RedisConfig.REDIS_PASSWORD,
        decode_responses=True  # 自动解码为字符串
    )