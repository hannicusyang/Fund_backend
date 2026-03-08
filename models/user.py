# models/user.py
# 用户模型 - 支持多用户认证

from . import db
from datetime import datetime, timezone, timedelta

# 东八区时区
SHANGHAI_TZ = timezone(timedelta(hours=8))

def get_shanghai_now():
    """获取当前东八区时间"""
    return datetime.now(SHANGHAI_TZ)
from werkzeug.security import generate_password_hash, check_password_hash


class User(db.Model):
    """用户表"""
    __tablename__ = 'users'
    __table_args__ = (
        db.Index('idx_username', 'username'),
        {'comment': '系统用户表'}
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False, comment='用户名')
    password_hash = db.Column(db.String(255), nullable=False, comment='密码哈希')
    nickname = db.Column(db.String(50), comment='昵称')
    email = db.Column(db.String(100), comment='邮箱')
    invite_code = db.Column(db.String(36), comment='邀请码')
    status = db.Column(db.Integer, default=1, comment='状态: 1正常 0禁用')
    created_at = db.Column(db.DateTime, default=get_shanghai_now, comment='创建时间')
    last_login = db.Column(db.DateTime, comment='最后登录时间')

    def set_password(self, password):
        """设置密码"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'nickname': self.nickname,
            'email': self.email,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }

    def __repr__(self):
        return f'<User {self.username}>'
