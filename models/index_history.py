"""
基准指数历史数据模型
存储沪深300、中证500等基准指数的历史净值数据
支持多数据源：新浪、腾讯、东方财富
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
    volume = db.Column(db.BigInteger, comment='成交量（股）')
    amount = db.Column(db.Float, comment='成交额（元）')
    change_pct = db.Column(db.Float, comment='涨跌幅(%)')
    change_amount = db.Column(db.Float, comment='涨跌额')
    amplitude = db.Column(db.Float, comment='振幅(%)')
    turnover_rate = db.Column(db.Float, comment='换手率(%)')
    source = db.Column(db.String(20), default='em', comment='数据来源: sina-新浪, tx-腾讯, em-东方财富, hist-东财通用')
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
    '000852': '中证1000',
    '399001': '深证成指',
    '000688': '科创50',
}

# 指数代码市场前缀映射
INDEX_MARKET_PREFIX = {
    '000': 'sh',  # 上证
    '600': 'sh',
    '601': 'sh',
    '603': 'sh',
    '605': 'sh',
    '688': 'sh',  # 科创板
    '399': 'sz',  # 深证
    '002': 'sz',
    '003': 'sz',
    '300': 'sz',  # 创业板
}


def get_index_symbol(index_code):
    """
    获取指数代码的完整symbol（带市场前缀）
    例如: 000300 -> sh000300
    """
    index_code = str(index_code)
    # 根据代码前缀判断市场
    for prefix, market in INDEX_MARKET_PREFIX.items():
        if index_code.startswith(prefix):
            return f"{market}{index_code}"
    # 默认使用sh前缀
    return f"sh{index_code}"
