# models/stock_screening.py
# 多因子选股数据模型 - 完整版

from . import db
from datetime import datetime, date, timezone, timedelta

# 东八区时区
SHANGHAI_TZ = timezone(timedelta(hours=8))

def get_shanghai_now():
    """获取当前东八区时间"""
    return datetime.now(SHANGHAI_TZ)


class StockScreeningData(db.Model):
    """多因子选股数据表 - 存储筛选所需的全部字段"""
    __tablename__ = 'stock_screening_data'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # 基础信息
    stock_code = db.Column(db.String(20), nullable=False, comment='股票代码')
    stock_name = db.Column(db.String(100), nullable=False, comment='股票名称')
    
    # 价格数据
    latest_price = db.Column(db.DECIMAL(18, 4), comment='最新价')
    open_price = db.Column(db.DECIMAL(18, 4), comment='开盘价')
    high = db.Column(db.DECIMAL(18, 4), comment='最高价')
    low = db.Column(db.DECIMAL(18, 4), comment='最低价')
    pre_close = db.Column(db.DECIMAL(18, 4), comment='昨收价')
    
    # 涨跌幅数据
    change_percent = db.Column(db.DECIMAL(10, 4), comment='涨跌幅%')
    change_amount = db.Column(db.DECIMAL(18, 4), comment='涨跌额')
    
    # 成交量数据
    volume = db.Column(db.DECIMAL(20, 2), comment='成交量(手)')
    turnover = db.Column(db.DECIMAL(20, 4), comment='成交额(万元)')
    turnover_rate = db.Column(db.DECIMAL(10, 4), comment='换手率%')
    
    # ===== 估值因子 =====
    pe = db.Column(db.DECIMAL(10, 4), comment='市盈率PE')
    pb = db.Column(db.DECIMAL(10, 4), comment='市净率PB')
    ps = db.Column(db.DECIMAL(10, 4), comment='市销率PS')
    pcf = db.Column(db.DECIMAL(10, 4), comment='市现率PCF')
    dividend_yield = db.Column(db.DECIMAL(10, 4), comment='股息率%')
    
    # ===== 动量因子 =====
    change_5d = db.Column(db.DECIMAL(10, 4), comment='5日涨跌幅%')
    change_10d = db.Column(db.DECIMAL(10, 4), comment='10日涨跌幅%')
    change_20d = db.Column(db.DECIMAL(10, 4), comment='20日涨跌幅%')
    change_60d = db.Column(db.DECIMAL(10, 4), comment='60日涨跌幅%')
    mom_1m = db.Column(db.DECIMAL(10, 4), comment='1月动量%')
    mom_3m = db.Column(db.DECIMAL(10, 4), comment='3月动量%')
    mom_6m = db.Column(db.DECIMAL(10, 4), comment='6月动量%')
    high_52w_ratio = db.Column(db.DECIMAL(10, 4), comment='52周新高比%')
    mom_accel = db.Column(db.DECIMAL(10, 4), comment='动量加速度%')
    
    # ===== 质量因子 =====
    roe = db.Column(db.DECIMAL(10, 4), comment='净资产收益率ROE%')
    roa = db.Column(db.DECIMAL(10, 4), comment='总资产收益率ROA%')
    gross_margin = db.Column(db.DECIMAL(10, 4), comment='毛利率%')
    net_profit_margin = db.Column(db.DECIMAL(10, 4), comment='净利率%')
    asset_turnover = db.Column(db.DECIMAL(10, 4), comment='资产周转率')
    
    # ===== 成长因子 =====
    revenue_growth = db.Column(db.DECIMAL(10, 4), comment='营收增长率%')
    profit_growth = db.Column(db.DECIMAL(10, 4), comment='利润增长率%')
    revenue_cagr_3y = db.Column(db.DECIMAL(10, 4), comment='营收3年CAGR%')
    profit_cagr_3y = db.Column(db.DECIMAL(10, 4), comment='利润3年CAGR%')
    
    # ===== 波动因子 =====
    volatility = db.Column(db.DECIMAL(10, 4), comment='年化波动率%')
    atr = db.Column(db.DECIMAL(10, 4), comment='ATR')
    max_drawdown = db.Column(db.DECIMAL(10, 4), comment='最大回撤%')
    downside_vol = db.Column(db.DECIMAL(10, 4), comment='下行波动率%')
    
    # ===== 技术因子 =====
    rsi = db.Column(db.DECIMAL(10, 4), comment='RSI')
    macd = db.Column(db.DECIMAL(10, 4), comment='MACD')
    ma_bull = db.Column(db.DECIMAL(3, 0), comment='均线多头0/1')
    
    # ===== 情绪因子 =====
    turnover_change = db.Column(db.DECIMAL(10, 4), comment='换手率变化%')
    volume_ratio = db.Column(db.DECIMAL(10, 4), comment='量比')
    
    # ===== 规模因子 =====
    market_cap = db.Column(db.DECIMAL(20, 4), comment='总市值(亿元)')
    circulating_cap = db.Column(db.DECIMAL(20, 4), comment='流通市值(亿元)')
    
    # 数据时间
    trade_date = db.Column(db.Date, nullable=False, comment='交易日期')
    fetch_time = db.Column(db.DateTime, nullable=False, default=get_shanghai_now, comment='数据获取时间')
    
    # 索引
    __table_args__ = (
        db.Index('idx_screening_code', 'stock_code'),
        db.Index('idx_screening_date', 'trade_date'),
        db.Index('idx_screening_pe', 'pe'),
        db.Index('idx_screening_pb', 'pb'),
        db.Index('idx_screening_change', 'change_percent'),
    )

    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'latest_price': float(self.latest_price) if self.latest_price else None,
            'open': float(self.open_price) if self.open_price else None,
            'high': float(self.high) if self.high else None,
            'low': float(self.low) if self.low else None,
            'pre_close': float(self.pre_close) if self.pre_close else None,
            'change_percent': float(self.change_percent) if self.change_percent else 0,
            'change_amount': float(self.change_amount) if self.change_amount else 0,
            'volume': float(self.volume) if self.volume else 0,
            'turnover': float(self.turnover) if self.turnover else 0,
            'turnover_rate': float(self.turnover_rate) if self.turnover_rate else 0,
            'pe': float(self.pe) if self.pe else None,
            'pb': float(self.pb) if self.pb else None,
            'ps': float(self.ps) if self.ps else None,
            'change_5d': float(self.change_5d) if self.change_5d else None,
            'change_10d': float(self.change_10d) if self.change_10d else None,
            'change_20d': float(self.change_20d) if self.change_20d else None,
            'change_60d': float(self.change_60d) if self.change_60d else None,
            'roe': float(self.roe) if self.roe else None,
            'gross_margin': float(self.gross_margin) if self.gross_margin else None,
            'net_profit_margin': float(self.net_profit_margin) if self.net_profit_margin else None,
            'revenue_growth': float(self.revenue_growth) if self.revenue_growth else None,
            'profit_growth': float(self.profit_growth) if self.profit_growth else None,
            'market_cap': float(self.market_cap) if self.market_cap else None,
            'circulating_cap': float(self.circulating_cap) if self.circulating_cap else None,
            'trade_date': self.trade_date.isoformat() if self.trade_date else None,
            'fetch_time': self.fetch_time.isoformat() if self.fetch_time else None,
        }
