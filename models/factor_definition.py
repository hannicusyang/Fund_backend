# models/factor_definition.py
# 因子定义模型 - 多因子选股系统

from . import db
from datetime import datetime


class ScreeningStrategy(db.Model):
    """
    筛选策略表
    用户保存的多因子筛选策略
    """
    __tablename__ = 'screening_strategies'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # 策略信息
    user_id = db.Column(db.String(50), nullable=False, default='default', comment='用户ID')
    strategy_name = db.Column(db.String(100), nullable=False, comment='策略名称')
    strategy_desc = db.Column(db.Text, comment='策略描述')
    
    # 因子配置 (JSON格式)
    factor_config = db.Column(db.JSON, nullable=False, comment='因子配置')
    
    # 筛选设置
    sort_by = db.Column(db.String(50), default='score', comment='排序字段')
    sort_order = db.Column(db.String(10), default='desc', comment='排序方向')
    limit = db.Column(db.Integer, default=50, comment='结果数量限制')
    
    # 统计信息
    last_run_time = db.Column(db.DateTime, comment='上次运行时间')
    last_run_count = db.Column(db.Integer, comment='上次筛选结果数量')
    
    # 状态
    is_default = db.Column(db.Boolean, default=False, comment='是否默认策略')
    is_public = db.Column(db.Boolean, default=False, comment='是否公开')
    
    # 时间戳
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.strategy_name,
            'description': self.strategy_desc,
            'factors': self.factor_config,
            'sortBy': self.sort_by,
            'sortOrder': self.sort_order,
            'limit': self.limit,
            'lastRunTime': self.last_run_time.isoformat() if self.last_run_time else None,
            'lastRunCount': self.last_run_count,
            'isDefault': self.is_default,
            'isPublic': self.is_public,
            'createTime': self.create_time.isoformat() if self.create_time else None
        }
