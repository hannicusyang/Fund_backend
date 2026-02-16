# models/__init__.py
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# 导出模型（方便外部使用）
from .fund_holding import FundHolding
from .fund_estimation import FundEstimation  # ← 新增
from .fund_list import FundList
from .fund_nav_history import FundNavHistory
from .fund_open_rank import FundOpenRankAll
from .stock_watchlist import StockWatchlist  # ← 新增股票自选
from .stock_estimation import StockEstimation  # ← 新增股票实时行情
from .stock_screening import StockScreeningData  # ← 新增多因子筛选数据
from .index_history import IndexHistory, BENCHMARK_INDICES  # ← 新增基准指数
from .fund_portfolio import FundPortfolio, FundPortfolioItem  # ← 新增组合模型
