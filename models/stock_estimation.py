from . import db
from datetime import datetime, timezone, timedelta

# 东八区时区
SHANGHAI_TZ = timezone(timedelta(hours=8))

def get_shanghai_now():
    """获取当前东八区时间"""
    return datetime.now(SHANGHAI_TZ)


class StockEstimation(db.Model):
    """股票实时行情数据表"""
    __tablename__ = 'stock_estimation'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    stock_code = db.Column(db.String(20), nullable=False, comment='股票代码')
    stock_name = db.Column(db.String(100), nullable=False, comment='股票名称')
    
    # 价格数据
    latest_price = db.Column(db.DECIMAL(18, 4), comment='最新价')
    change_amount = db.Column(db.DECIMAL(18, 4), comment='涨跌额')
    change_percent = db.Column(db.DECIMAL(10, 4), comment='涨跌幅%')
    prev_close = db.Column(db.DECIMAL(18, 4), comment='昨收')
    open_price = db.Column(db.DECIMAL(18, 4), comment='今开')
    high = db.Column(db.DECIMAL(18, 4), comment='最高')
    low = db.Column(db.DECIMAL(18, 4), comment='最低')
    
    # 成交量数据
    volume = db.Column(db.DECIMAL(20, 2), comment='成交量(手)')
    turnover = db.Column(db.DECIMAL(20, 4), comment='成交额(元)')
    turnover_rate = db.Column(db.DECIMAL(10, 4), comment='换手率%')
    amplitude = db.Column(db.DECIMAL(10, 4), comment='振幅%')
    volume_ratio = db.Column(db.DECIMAL(10, 4), comment='量比')
    
    # 估值数据
    pe_dynamic = db.Column(db.DECIMAL(10, 4), comment='市盈率-动态')
    pb_ratio = db.Column(db.DECIMAL(10, 4), comment='市净率')
    total_market_cap = db.Column(db.DECIMAL(20, 4), comment='总市值(元)')
    circulating_market_cap = db.Column(db.DECIMAL(20, 4), comment='流通市值(元)')
    
    # 其他指标
    change_speed = db.Column(db.DECIMAL(10, 4), comment='涨速')
    change_5min = db.Column(db.DECIMAL(10, 4), comment='5分钟涨跌%')
    change_60d = db.Column(db.DECIMAL(10, 4), comment='60日涨跌幅%')
    change_ytd = db.Column(db.DECIMAL(10, 4), comment='年初至今涨跌幅%')
    
    # 数据时间
    trade_date = db.Column(db.Date, comment='交易日期')
    fetch_time = db.Column(db.DateTime, nullable=False, default=get_shanghai_now, comment='数据获取时间')
    
    # 索引
    __table_args__ = (
        db.Index('idx_stock_code', 'stock_code'),
        db.Index('idx_trade_date', 'trade_date'),
        db.Index('idx_fetch_time', 'fetch_time'),
    )