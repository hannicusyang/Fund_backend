# models/fund_list.py
from . import db
from datetime import datetime


class FundList(db.Model):
    __tablename__ = 'fund_list'

    fund_code = db.Column(db.String(20), primary_key=True, comment='基金代码')
    pinyin_abbr = db.Column(db.String(100), comment='拼音缩写')
    fund_name = db.Column(db.String(255), comment='基金简称')
    fund_type = db.Column(db.String(100), comment='基金类型')
    pinyin_full = db.Column(db.String(255), comment='拼音全称')
    # 新增筛选字段
    min_amount = db.Column(db.Float, default=10, comment='起购金额(元)')
    establishment_date = db.Column(db.String(10), comment='成立日期')
    management_fee = db.Column(db.Float, default=0, comment='管理费率(年%)')
    custodian_fee = db.Column(db.Float, default=0, comment='托管费率(年%)')
    subscription_fee = db.Column(db.Float, default=0, comment='申购费率(%)')
    redemption_fee = db.Column(db.Float, default=0, comment='赎回费率(%)')
    fund_status = db.Column(db.String(20), default='开放', comment='基金状态')
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<FundList {self.fund_code}: {self.fund_name}>"