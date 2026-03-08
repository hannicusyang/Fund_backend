# models/fund_estimation.py
from . import db
from datetime import datetime, timezone, timedelta
import time

# 东八区时区
SHANGHAI_TZ = timezone(timedelta(hours=8))

def get_shanghai_now():
    """获取当前东八区时间"""
    return datetime.now(SHANGHAI_TZ)


class FundEstimation(db.Model):
    __tablename__ = 'fund_estimation'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fund_code = db.Column(db.String(20), nullable=False)
    fund_name = db.Column(db.String(255), nullable=False)
    estimation_date = db.Column(
        db.Date,
        nullable=False,
        comment='估算所针对的日期 (T日)'
    )
    last_nav_date = db.Column(db.Date, comment='上一交易日净值日期 (T-1日)')
    estimated_nav = db.Column(db.DECIMAL(18, 6))
    estimated_growth_rate = db.Column(db.DECIMAL(10, 4))
    published_nav = db.Column(db.DECIMAL(18, 6))
    published_growth_rate = db.Column(db.DECIMAL(10, 4))
    estimation_bias = db.Column(db.DECIMAL(10, 4))
    last_nav = db.Column(db.DECIMAL(18, 6), comment='T-1日单位净值')
    fetch_time = db.Column(db.DateTime, nullable=False, default=get_shanghai_now)

    # ✅ 移除了 UniqueConstraint('fund_code', 'estimation_date')
    __table_args__ = (
        db.Index('idx_estimation_date', 'estimation_date'),
        db.Index('idx_fetch_time', 'fetch_time'),
        db.Index('idx_fund_code', 'fund_code'),
    )