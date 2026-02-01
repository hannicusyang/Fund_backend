# models/stock_market_overview.py
from datetime import date
from . import db

class StockSSESummary(db.Model):
    __tablename__ = 'stock_sse_summary'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    trade_date = db.Column(db.Date, unique=True, nullable=False, index=True) # 用交易日期作为唯一标识

    # SSE Summary 的数据字段 (根据实际数据类型调整)
    # 股票
    stock_circulating_capital = db.Column(db.Float) # 流通股本
    stock_total_mv = db.Column(db.Float) # 总市值
    stock_avg_pe = db.Column(db.Float) # 平均市盈率
    stock_companies = db.Column(db.Integer) # 上市公司
    stock_stocks = db.Column(db.Integer) # 上市股票
    stock_circulating_mv = db.Column(db.Float) # 流通市值
    stock_total_capital = db.Column(db.Float) # 总股本

    # 科创板
    star_circulating_capital = db.Column(db.Float)
    star_total_mv = db.Column(db.Float)
    star_avg_pe = db.Column(db.Float)
    star_companies = db.Column(db.Integer)
    star_stocks = db.Column(db.Integer)
    star_circulating_mv = db.Column(db.Float)
    star_total_capital = db.Column(db.Float)

    # 主板
    main_circulating_capital = db.Column(db.Float)
    main_total_mv = db.Column(db.Float)
    main_avg_pe = db.Column(db.Float)
    main_companies = db.Column(db.Integer)
    main_stocks = db.Column(db.Integer)
    main_circulating_mv = db.Column(db.Float)
    main_total_capital = db.Column(db.Float)

    update_time = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    def to_dict(self):
        return {
            "trade_date": self.trade_date.isoformat() if self.trade_date else None,
            "stock": {
                "circulating_capital": self.stock_circulating_capital,
                "total_mv": self.stock_total_mv,
                "avg_pe": self.stock_avg_pe,
                "companies": self.stock_companies,
                "stocks": self.stock_stocks,
                "circulating_mv": self.stock_circulating_mv,
                "total_capital": self.stock_total_capital,
            },
            "star_board": {
                "circulating_capital": self.star_circulating_capital,
                "total_mv": self.star_total_mv,
                "avg_pe": self.star_avg_pe,
                "companies": self.star_companies,
                "stocks": self.star_stocks,
                "circulating_mv": self.star_circulating_mv,
                "total_capital": self.star_total_capital,
            },
            "main_board": {
                "circulating_capital": self.main_circulating_capital,
                "total_mv": self.main_total_mv,
                "avg_pe": self.main_avg_pe,
                "companies": self.main_companies,
                "stocks": self.main_stocks,
                "circulating_mv": self.main_circulating_mv,
                "total_capital": self.main_total_capital,
            },
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }

class StockSZSESummary(db.Model):
    __tablename__ = 'stock_szse_summary'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    trade_date = db.Column(db.Date, nullable=False, index=True) # 日期作为索引
    security_type = db.Column(db.String(50), nullable=False) # 证券类别，作为复合主键的一部分

    quantity = db.Column(db.Integer) # 数量
    turnover_amount = db.Column(db.Float) # 成交金额
    total_mv = db.Column(db.Float) # 总市值
    circulating_mv = db.Column(db.Float) # 流通市值

    update_time = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    __table_args__ = (db.UniqueConstraint('trade_date', 'security_type', name='_trade_date_security_type_uc'),)

    def to_dict(self):
        return {
            "trade_date": self.trade_date.isoformat() if self.trade_date else None,
            "security_type": self.security_type,
            "quantity": self.quantity,
            "turnover_amount": self.turnover_amount,
            "total_mv": self.total_mv,
            "circulating_mv": self.circulating_mv,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }

class StockSZSEAreaSummary(db.Model):
    __tablename__ = 'stock_szse_area_summary'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    report_period = db.Column(db.String(10), nullable=False, index=True) # 报告期，如 '202412'
    area = db.Column(db.String(100), nullable=False)

    serial_number = db.Column(db.Integer) # 序号
    total_turnover = db.Column(db.Float) # 总交易额
    market_share = db.Column(db.Float) # 占市场 (%)
    stock_turnover = db.Column(db.Float) # 股票交易额
    fund_turnover = db.Column(db.Float) # 基金交易额
    bond_turnover = db.Column(db.Float) # 债券交易额
    preferred_stock_turnover = db.Column(db.Float) # 优先股交易额 (2025年新增)
    option_turnover = db.Column(db.Float) # 期权交易额 (2025年新增)

    update_time = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    __table_args__ = (db.UniqueConstraint('report_period', 'area', name='_report_period_area_uc'),)

    def to_dict(self):
        return {
            "report_period": self.report_period,
            "area": self.area,
            "serial_number": self.serial_number,
            "total_turnover": self.total_turnover,
            "market_share": self.market_share,
            "stock_turnover": self.stock_turnover,
            "fund_turnover": self.fund_turnover,
            "bond_turnover": self.bond_turnover,
            "preferred_stock_turnover": self.preferred_stock_turnover,
            "option_turnover": self.option_turnover,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }

class StockSZSESectorSummary(db.Model):
    __tablename__ = 'stock_szse_sector_summary'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    report_period = db.Column(db.String(10), nullable=False, index=True) # 报告期，如 '202412'
    symbol = db.Column(db.String(20), nullable=False) # '当月' 或 '当年'
    sector_chinese = db.Column(db.String(100), nullable=False) # 项目名称
    sector_english = db.Column(db.String(100)) # 项目名称-英文

    trading_days = db.Column(db.Integer) # 交易天数
    turnover_amount_cny = db.Column(db.BigInteger) # 成交金额-人民币元
    turnover_amount_pct = db.Column(db.Float) # 成交金额-占总计 (%)
    volume_shares = db.Column(db.BigInteger) # 成交股数-股数
    volume_shares_pct = db.Column(db.Float) # 成交股数-占总计 (%)
    deal_count = db.Column(db.BigInteger) # 成交笔数-笔
    deal_count_pct = db.Column(db.Float) # 成交笔数-占总计 (%)

    update_time = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    __table_args__ = (db.UniqueConstraint('report_period', 'symbol', 'sector_chinese', name='_report_period_symbol_sector_uc'),)

    def to_dict(self):
        return {
            "report_period": self.report_period,
            "symbol": self.symbol,
            "sector_chinese": self.sector_chinese,
            "sector_english": self.sector_english,
            "trading_days": self.trading_days,
            "turnover_amount_cny": self.turnover_amount_cny,
            "turnover_amount_pct": self.turnover_amount_pct,
            "volume_shares": self.volume_shares,
            "volume_shares_pct": self.volume_shares_pct,
            "deal_count": self.deal_count,
            "deal_count_pct": self.deal_count_pct,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }

class StockSSEDealDaily(db.Model):
    __tablename__ = 'stock_sse_deal_daily'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    trade_date = db.Column(db.Date, unique=True, nullable=False, index=True) # 交易日期

    # 单日情况下的各项指标
    listed_count_stock = db.Column(db.Float) # 挂牌数-股票
    listed_count_main_a = db.Column(db.Float) # 挂牌数-主板A
    listed_count_main_b = db.Column(db.Float) # 挂牌数-主板B
    listed_count_star = db.Column(db.Float) # 挂牌数-科创板
    listed_count_repo = db.Column(db.Float) # 挂牌数-股票回购

    total_mv_stock = db.Column(db.Float) # 市价总值-股票
    total_mv_main_a = db.Column(db.Float) # 市价总值-主板A
    total_mv_main_b = db.Column(db.Float) # 市价总值-主板B
    total_mv_star = db.Column(db.Float) # 市价总值-科创板
    total_mv_repo = db.Column(db.Float) # 市价总值-股票回购

    circulating_mv_stock = db.Column(db.Float) # 流通市值-股票
    circulating_mv_main_a = db.Column(db.Float) # 流通市值-主板A
    circulating_mv_main_b = db.Column(db.Float) # 流通市值-主板B
    circulating_mv_star = db.Column(db.Float) # 流通市值-科创板
    circulating_mv_repo = db.Column(db.Float) # 流通市值-股票回购

    turnover_amount_stock = db.Column(db.Float) # 成交金额-股票
    turnover_amount_main_a = db.Column(db.Float) # 成交金额-主板A
    turnover_amount_main_b = db.Column(db.Float) # 成交金额-主板B
    turnover_amount_star = db.Column(db.Float) # 成交金额-科创板
    turnover_amount_repo = db.Column(db.Float) # 成交金额-股票回购

    volume_stock = db.Column(db.Float) # 成交量-股票
    volume_main_a = db.Column(db.Float) # 成交量-主板A
    volume_main_b = db.Column(db.Float) # 成交量-主板B
    volume_star = db.Column(db.Float) # 成交量-科创板
    volume_repo = db.Column(db.Float) # 成交量-股票回购

    avg_pe_stock = db.Column(db.Float) # 平均市盈率-股票
    avg_pe_main_a = db.Column(db.Float) # 平均市盈率-主板A
    avg_pe_main_b = db.Column(db.Float) # 平均市盈率-主板B
    avg_pe_star = db.Column(db.Float) # 平均市盈率-科创板
    avg_pe_repo = db.Column(db.Float) # 平均市盈率-股票回购

    turnover_rate_stock = db.Column(db.Float) # 换手率-股票
    turnover_rate_main_a = db.Column(db.Float) # 换手率-主板A
    turnover_rate_main_b = db.Column(db.Float) # 换手率-主板B
    turnover_rate_star = db.Column(db.Float) # 换手率-科创板
    turnover_rate_repo = db.Column(db.Float) # 换手率-股票回购

    circulating_turnover_rate_stock = db.Column(db.Float) # 流通换手率-股票
    circulating_turnover_rate_main_a = db.Column(db.Float) # 流通换手率-主板A
    circulating_turnover_rate_main_b = db.Column(db.Float) # 流通换手率-主板B
    circulating_turnover_rate_star = db.Column(db.Float) # 流通换手率-科创板
    circulating_turnover_rate_repo = db.Column(db.Float) # 流通换手率-股票回购

    update_time = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    def to_dict(self):
        return {
            "trade_date": self.trade_date.isoformat() if self.trade_date else None,
            "listed_count": {
                "stock": self.listed_count_stock,
                "main_board_a": self.listed_count_main_a,
                "main_board_b": self.listed_count_main_b,
                "star_board": self.listed_count_star,
                "repo": self.listed_count_repo,
            },
            "total_mv": {
                "stock": self.total_mv_stock,
                "main_board_a": self.total_mv_main_a,
                "main_board_b": self.total_mv_main_b,
                "star_board": self.total_mv_star,
                "repo": self.total_mv_repo,
            },
            "circulating_mv": {
                "stock": self.circulating_mv_stock,
                "main_board_a": self.circulating_mv_main_a,
                "main_board_b": self.circulating_mv_main_b,
                "star_board": self.circulating_mv_star,
                "repo": self.circulating_mv_repo,
            },
            "turnover_amount": {
                "stock": self.turnover_amount_stock,
                "main_board_a": self.turnover_amount_main_a,
                "main_board_b": self.turnover_amount_main_b,
                "star_board": self.turnover_amount_star,
                "repo": self.turnover_amount_repo,
            },
            "volume": {
                "stock": self.volume_stock,
                "main_board_a": self.volume_main_a,
                "main_board_b": self.volume_main_b,
                "star_board": self.volume_star,
                "repo": self.volume_repo,
            },
            "avg_pe": {
                "stock": self.avg_pe_stock,
                "main_board_a": self.avg_pe_main_a,
                "main_board_b": self.avg_pe_main_b,
                "star_board": self.avg_pe_star,
                "repo": self.avg_pe_repo,
            },
            "turnover_rate": {
                "stock": self.turnover_rate_stock,
                "main_board_a": self.turnover_rate_main_a,
                "main_board_b": self.turnover_rate_main_b,
                "star_board": self.turnover_rate_star,
                "repo": self.turnover_rate_repo,
            },
            "circulating_turnover_rate": {
                "stock": self.circulating_turnover_rate_stock,
                "main_board_a": self.circulating_turnover_rate_main_a,
                "main_board_b": self.circulating_turnover_rate_main_b,
                "star_board": self.circulating_turnover_rate_star,
                "repo": self.circulating_turnover_rate_repo,
            },
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }