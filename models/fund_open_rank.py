# models/fund_open_rank.py

from . import db
from datetime import datetime, timezone

def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class FundOpenRankAll(db.Model):
    __tablename__ = 'fund_open_rank_all'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    rank = db.Column(db.Integer, nullable=True)
    fund_code = db.Column(db.String(20), nullable=False, index=True)
    fund_name = db.Column(db.String(100), nullable=False)
    date = db.Column(db.String(10), nullable=True)  # ← 新增：存储如 '01-13' 的字符串
    net_value = db.Column(db.Float, nullable=True)
    accumulated_net_value = db.Column(db.Float, nullable=True)
    daily_growth_rate = db.Column(db.Float, nullable=True)  # 存储为数值（如 2.5 表示 2.5%）
    weekly_growth_rate = db.Column(db.Float, nullable=True)
    monthly_1_growth_rate = db.Column(db.Float, nullable=True)
    monthly_3_growth_rate = db.Column(db.Float, nullable=True)
    monthly_6_growth_rate = db.Column(db.Float, nullable=True)
    yearly_1_growth_rate = db.Column(db.Float, nullable=True)
    yearly_2_growth_rate = db.Column(db.Float, nullable=True)
    yearly_3_growth_rate = db.Column(db.Float, nullable=True)
    ytd_growth_rate = db.Column(db.Float, nullable=True)
    since_inception_growth_rate = db.Column(db.Float, nullable=True)
    custom_growth_rate = db.Column(db.Float, nullable=True)
    fee_rate = db.Column(db.Float, nullable=True)
    is_checked = db.Column(db.Boolean, default=False)
    update_time = db.Column(
        db.DateTime,
        default=utc_now,
        onupdate=utc_now
    )