# utils/trading_calendar.py
import akshare as ak
from datetime import date
import logging
import pandas as pd
logger = logging.getLogger(__name__)

# 全局缓存：交易日集合（set of date objects）
_TRADING_DAYS = None


def _load_trading_days():
    """从 AKShare 加载交易日历并缓存为 set"""
    global _TRADING_DAYS
    if _TRADING_DAYS is not None:
        return _TRADING_DAYS

    try:
        df = ak.tool_trade_date_hist_sina()
        # 转换为 date 对象集合，便于快速查找
        _TRADING_DAYS = set(pd.to_datetime(df['trade_date']).dt.date)
        logger.info(f"✅ 成功加载 {len(_TRADING_DAYS)} 个交易日（{min(_TRADING_DAYS)} ～ {max(_TRADING_DAYS)}）")
        return _TRADING_DAYS
    except Exception as e:
        logger.error(f"❌ 加载交易日历失败: {e}")
        _TRADING_DAYS = set()  # 防止反复重试
        raise


def is_a_stock_trading_day(input_date):
    """
    判断指定日期是否为 A 股交易日（基于 AKShare 新浪财经数据）

    Args:
        input_date (str or datetime.date): 日期，格式如 '2026-01-13' 或 date(2026, 1, 13)

    Returns:
        bool: True 表示是交易日，False 表示非交易日或日期超出已知范围
    """
    # 标准化为 date 对象
    if isinstance(input_date, str):
        input_date = date.fromisoformat(input_date)
    elif not isinstance(input_date, date):
        raise ValueError("input_date 必须是 str (YYYY-MM-DD) 或 datetime.date 类型")

    try:
        trading_days = _load_trading_days()
    except Exception:
        # 加载失败时保守返回 False
        return False

    return input_date in trading_days


def is_a_stock_trading_time():
    """
    判断当前是否为 A 股交易时间（交易日 + 9:30～15:00）
    """
    from datetime import datetime, time

    now = datetime.now()
    today = now.date()
    current_time = now.time()

    # 检查是否在交易时段
    if not (time(9, 30) <= current_time <= time(15, 0)):
        return False

    # 检查是否为交易日
    return is_a_stock_trading_day(today)