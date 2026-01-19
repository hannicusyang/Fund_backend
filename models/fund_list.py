# models/fund_list.py
from . import db
from datetime import datetime


class FundBasic(db.Model):
    __tablename__ = 'fund_list'

    fund_code = db.Column(db.String(20), primary_key=True, comment='基金代码')
    pinyin_abbr = db.Column(db.String(100), comment='拼音缩写')
    fund_name = db.Column(db.String(255), comment='基金简称')
    fund_type = db.Column(db.String(100), comment='基金类型')
    pinyin_full = db.Column(db.String(255), comment='拼音全称')
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<FundBasic {self.fund_code}: {self.fund_name}>"