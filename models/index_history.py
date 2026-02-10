"""
基准指数历史数据模型
存储沪深300、中证500等基准指数的历史净值数据
"""
from models import db
from datetime import datetime


class IndexHistory(db.Model):
    """基准指数历史数据"""
    __tablename__ = 'index_history'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    index_code = db.Column(db.String(20), nullable=False, index=True, comment='指数代码')
    index_name = db.Column(db.String(100), comment='指数名称')
    trade_date = db.Column(db.Date, nullable=False, index=True, comment='交易日期')
    close = db.Column(db.Float, comment='收盘点位')
    open = db.Column(db.Float, comment='开盘点位')
    high = db.Column(db.Float, comment='最高点位')
    low = db.Column(db.Float, comment='最低点位')
    volume = db.Column(db.BigInteger, comment='成交量')
    amount = db.Column(db.Float, comment='成交额')
    change_pct = db.Column(db.Float, comment='涨跌幅(%)')
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        db.UniqueConstraint('index_code', 'trade_date', name='uix_index_date'),
    )

    def __repr__(self):
        return f'<IndexHistory {self.index_code} {self.trade_date}>'


# 常用基准指数代码
BENCHMARK_INDICES = {
    '000300': '沪深300',
    '000905': '中证500',
    '000001': '上证指数',
    '399006': '创业板指',
    '000016': '上证50',
    '000852': '中证1000'
}
