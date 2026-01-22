# models/__init__.py
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# 导出模型（方便外部使用）
from .fund_holding import FundHolding
from .fund_estimation import FundEstimation  # ← 新增
from .fund_list import FundList
from .fund_nav_history import FundNavHistory
from .fund_open_rank import FundOpenRankAll
