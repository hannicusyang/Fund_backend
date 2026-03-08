# models/fund_portfolio.py
from . import db
from datetime import datetime, timezone, timedelta

# 东八区时区
SHANGHAI_TZ = timezone(timedelta(hours=8))

def get_shanghai_now():
    """获取当前东八区时间"""
    return datetime.now(SHANGHAI_TZ)


class FundPortfolio(db.Model):
    """用户基金组合表"""
    __tablename__ = 'fund_portfolio'
    __table_args__ = (
        db.Index('idx_user_id', 'user_id'),
        {'comment': '用户基金组合'}
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(36), nullable=False, default='default', comment='用户ID')
    name = db.Column(db.String(100), nullable=False, comment='组合名称')
    goal = db.Column(db.String(20), default='balanced', comment='投资目标: conservative-保守, balanced-平衡, aggressive-进取')
    strategy = db.Column(db.String(30), default='equal', comment='配置策略')
    amount = db.Column(db.DECIMAL(18, 4), default=100000, comment='投资金额')
    
    # 组合指标（保存时的快照）
    expected_return = db.Column(db.DECIMAL(10, 4), comment='预期年化收益')
    volatility = db.Column(db.DECIMAL(10, 4), comment='组合波动率')
    sharpe_ratio = db.Column(db.DECIMAL(10, 4), comment='夏普比率')
    risk_level = db.Column(db.String(20), comment='风险等级')
    weighted_fee_rate = db.Column(db.DECIMAL(10, 4), comment='加权手续费率')
    
    is_default = db.Column(db.Boolean, default=False, comment='是否默认组合')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    created_at = db.Column(db.DateTime, default=get_shanghai_now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=get_shanghai_now, onupdate=datetime.utcnow, comment='更新时间')

    # 关联关系
    items = db.relationship('FundPortfolioItem', backref='portfolio', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<FundPortfolio {self.id}: {self.name}>"


class FundPortfolioItem(db.Model):
    """基金组合明细表"""
    __tablename__ = 'fund_portfolio_item'
    __table_args__ = (
        db.Index('idx_portfolio_id', 'portfolio_id'),
        db.Index('idx_fund_code', 'fund_code'),
        db.UniqueConstraint('portfolio_id', 'fund_code', name='uk_portfolio_fund'),
        {'comment': '基金组合明细'}
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    portfolio_id = db.Column(db.BigInteger, db.ForeignKey('fund_portfolio.id', ondelete='CASCADE'), nullable=False, comment='组合ID')
    fund_code = db.Column(db.String(20), nullable=False, comment='基金代码')
    fund_name = db.Column(db.String(100), comment='基金名称')
    weight = db.Column(db.DECIMAL(5, 2), nullable=False, comment='配置权重(%)')
    amount = db.Column(db.DECIMAL(18, 4), comment='投资金额')
    
    # 保存时的基金指标快照
    yearly_return = db.Column(db.DECIMAL(10, 4), comment='年度收益率')
    monthly_return = db.Column(db.DECIMAL(10, 4), comment='月度收益率')
    weekly_return = db.Column(db.DECIMAL(10, 4), comment='周收益率')
    fee_rate = db.Column(db.DECIMAL(10, 4), comment='费率')
    
    created_at = db.Column(db.DateTime, default=get_shanghai_now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=get_shanghai_now, onupdate=datetime.utcnow, comment='更新时间')

    def __repr__(self):
        return f"<FundPortfolioItem {self.portfolio_id}: {self.fund_code} {self.weight}%>"
