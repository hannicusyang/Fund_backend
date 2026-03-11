# services/__init__.py
# AI分析服务模块

from .ai_analysis_service import get_ai_service, analyze_news_with_ai
from .fund_analysis import (
    get_fund_analysis_service, 
    analyze_fund_with_ai, 
    compare_funds_with_ai
)
from .stock_analysis import get_stock_analysis_service, analyze_stock_with_ai
from .portfolio_analysis import (
    get_portfolio_analysis_service,
    analyze_portfolio_with_ai,
    generate_rebalance_advice
)
from .backtest_analysis import (
    get_backtest_analysis_service,
    analyze_backtest_with_ai,
    optimize_strategy_params,
    compare_strategies_with_ai
)

__all__ = [
    # AI分析服务
    'get_ai_service',
    'analyze_news_with_ai',
    # 基金分析
    'get_fund_analysis_service',
    'analyze_fund_with_ai',
    'compare_funds_with_ai',
    # 股票分析
    'get_stock_analysis_service',
    'analyze_stock_with_ai',
    # 组合分析
    'get_portfolio_analysis_service',
    'analyze_portfolio_with_ai',
    'generate_rebalance_advice',
    # 回测分析
    'get_backtest_analysis_service',
    'analyze_backtest_with_ai',
    'optimize_strategy_params',
    'compare_strategies_with_ai',
]
