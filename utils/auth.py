# utils/auth.py
# 从 JWT Token 获取当前用户ID

import os
import jwt
from functools import wraps
from flask import request, g

SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'fund_system_secret_key_2024')


def get_current_user_id():
    """从请求头获取当前用户ID"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    
    token = auth_header.split(' ')[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        # 返回字符串格式，确保与数据库一致
        user_id = payload.get('user_id')
        return str(user_id) if user_id is not None else None
    except:
        return None


def get_current_user_id_or_default():
    """获取当前用户ID，如果未登录返回 'default'"""
    user_id = get_current_user_id()
    return user_id if user_id else 'default'


def login_required(f):
    """装饰器：要求登录才能访问"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = get_current_user_id()
        if not user_id:
            from flask import jsonify
            return jsonify({'success': False, 'message': '请先登录'}), 401
        g.user_id = user_id
        return f(*args, **kwargs)
    return decorated
