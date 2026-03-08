# routes/auth.py
# 用户认证API - 登录/注册/登出

import os
import uuid
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify
import jwt
from models import db
from models.user import User

# 东八区时区
SHANGHAI_TZ = timezone(timedelta(hours=8))

# 配置
SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'fund_system_secret_key_2024')
TOKEN_EXPIRE_HOURS = 24 * 7  # Token 7天过期
INVITE_CODE = 'yangqi'  # 注册邀请码

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


def generate_token(user_id, username):
    """生成JWT Token"""
    payload = {
        'user_id': user_id,
        'username': username,
        'exp': datetime.now(SHANGHAI_TZ) + timedelta(hours=TOKEN_EXPIRE_HOURS),
        'iat': datetime.now(SHANGHAI_TZ)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
    return token


def decode_token(token):
    """解析JWT Token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


@auth_bp.route('/register', methods=['POST'])
def register():
    """用户注册"""
    data = request.get_json()
    
    username = data.get('username', '').strip()
    password = data.get('password', '')
    invite_code = data.get('invite_code', '').strip()
    nickname = data.get('nickname', '').strip()
    email = data.get('email', '').strip()
    
    # 验证必填字段
    if not username:
        return jsonify({'success': False, 'message': '请输入用户名'}), 400
    if len(username) < 3 or len(username) > 20:
        return jsonify({'success': False, 'message': '用户名长度需3-20字符'}), 400
    if not password:
        return jsonify({'success': False, 'message': '请输入密码'}), 400
    if len(password) < 6:
        return jsonify({'success': False, 'message': '密码长度至少6位'}), 400
    
    # 验证邀请码
    if invite_code != INVITE_CODE:
        return jsonify({'success': False, 'message': '邀请码错误'}), 403
    
    # 检查用户名是否已存在
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({'success': False, 'message': '用户名已存在'}), 400
    
    # 创建用户
    user = User(
        username=username,
        nickname=nickname or username,
        email=email,
        invite_code=invite_code,
        status=1
    )
    user.set_password(password)
    
    db.session.add(user)
    db.session.commit()
    
    # 生成Token
    token = generate_token(user.id, user.username)
    
    return jsonify({
        'success': True,
        'message': '注册成功',
        'data': {
            'token': token,
            'user': user.to_dict()
        }
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.get_json()
    
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'success': False, 'message': '请输入用户名和密码'}), 400
    
    # 查找用户
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'success': False, 'message': '用户名或密码错误'}), 401
    
    # 验证密码
    if not user.check_password(password):
        return jsonify({'success': False, 'message': '用户名或密码错误'}), 401
    
    # 检查状态
    if user.status != 1:
        return jsonify({'success': False, 'message': '账号已被禁用'}), 403
    
    # 更新最后登录时间
    user.last_login = datetime.now(SHANGHAI_TZ)
    db.session.commit()
    
    # 生成Token
    token = generate_token(user.id, user.username)
    
    return jsonify({
        'success': True,
        'message': '登录成功',
        'data': {
            'token': token,
            'user': user.to_dict()
        }
    })


@auth_bp.route('/verify', methods=['GET'])
def verify_token():
    """验证Token"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': '未提供Token'}), 401
    
    token = auth_header.split(' ')[1]
    payload = decode_token(token)
    
    if not payload:
        return jsonify({'success': False, 'message': 'Token已过期或无效'}), 401
    
    # 获取用户信息
    user = User.query.get(payload['user_id'])
    if not user or user.status != 1:
        return jsonify({'success': False, 'message': '用户不存在或已禁用'}), 401
    
    return jsonify({
        'success': True,
        'data': {
            'user': user.to_dict()
        }
    })


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """退出登录 (前端删除Token即可)"""
    return jsonify({'success': True, 'message': '已退出登录'})


@auth_bp.route('/change-password', methods=['POST'])
def change_password():
    """修改密码"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': '未登录'}), 401
    
    token = auth_header.split(' ')[1]
    payload = decode_token(token)
    if not payload:
        return jsonify({'success': False, 'message': 'Token已过期'}), 401
    
    data = request.get_json()
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    
    if not old_password or not new_password:
        return jsonify({'success': False, 'message': '请输入旧密码和新密码'}), 400
    
    if len(new_password) < 6:
        return jsonify({'success': False, 'message': '新密码长度至少6位'}), 400
    
    user = User.query.get(payload['user_id'])
    if not user.check_password(old_password):
        return jsonify({'success': False, 'message': '旧密码错误'}), 400
    
    user.set_password(new_password)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '密码修改成功'})
