# models/fund_nav_history.py
from . import db
from datetime import datetime, timezone, timedelta

# 东八区时区
SHANGHAI_TZ = timezone(timedelta(hours=8))

def get_shanghai_now():
    """获取当前东八区时间"""
    return datetime.now(SHANGHAI_TZ)


class FundNavHistory(db.Model):
    __tablename__ = 'fund_nav_history'

    fund_code = db.Column(db.String(20), primary_key=True, comment='基金代码')
    nav_date = db.Column(db.Date, primary_key=True, comment='净值日期')
    fund_name = db.Column(db.String(255), nullable=False, comment='基金简称')
    net_value = db.Column(db.DECIMAL(18, 6), comment='单位净值')
    daily_growth_rate = db.Column(db.DECIMAL(10, 4), comment='日增长率 (%)')
    update_time = db.Column(db.DateTime, default=get_shanghai_now, comment='数据更新时间')

    __table_args__ = (
        db.Index('idx_fund_code', 'fund_code'),
        db.Index('idx_nav_date', 'nav_date'),
    )

    def __repr__(self):
        return f"<FundNavHistory {self.fund_code} @ {self.nav_date}>"