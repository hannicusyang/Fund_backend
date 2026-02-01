# utils/stock_trading_calendar.py
from datetime import date, timedelta
import logging
from models.trading_day import TradingDay
from flask import current_app
import akshare as ak

from config import *


class TradingCalendarService:
    """权威交易日历服务 - 单一数据源"""

    _instance = None
    _trading_days = set()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TradingCalendarService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """多源降级初始化策略"""
        try:
            # 1. 优先从数据库加载
            if self._load_from_db():
                logger.info(f"✅ 从数据库加载 {len(self._trading_days)} 个交易日")
                return

            # 2. 尝试AKShare（仅开发环境）
            if current_app.debug and self._load_from_akshare():
                logger.info(f"✅ 从AKShare加载 {len(self._trading_days)} 个交易日")
                return

            # 3. 硬编码兜底 - 2026春节场景
            self._load_hardcoded_2026_spring_festival()
            logger.warning("⚠️ 使用硬编码交易日历，请立即修复数据源")

        except Exception as e:
            logger.error(f"交易日历初始化失败: {e}")
            self._load_hardcoded_2026_spring_festival()

    def _load_from_db(self):
        """从数据库加载交易日历"""
        try:
            trading_days = TradingDay.query.all()
            if trading_days:
                self._trading_days = {td.trade_date for td in trading_days}
                return True
        except Exception as e:
            logger.error(f"数据库加载交易日历失败: {e}")
        return False

    def _load_from_akshare(self):
        """从AKShare加载交易日历"""
        try:
            # 获取最近2年交易日
            end_date = date.today().strftime('%Y%m%d')
            start_date = (date.today() - timedelta(days=730)).strftime('%Y%m%d')
            df = ak.tool_trade_date_hist_sina()

            if not df.empty:
                # 过滤指定日期范围
                df['trade_date'] = pd.to_datetime(df['trade_date']).dt.date
                filtered_dates = df[
                    (df['trade_date'] >= pd.to_datetime(start_date).date()) &
                    (df['trade_date'] <= pd.to_datetime(end_date).date())
                    ]['trade_date'].tolist()

                self._trading_days = set(filtered_dates)
                return len(self._trading_days) > 0
        except Exception as e:
            logger.error(f"AKShare加载交易日历失败: {e}")
        return False

    def _load_hardcoded_2026_spring_festival(self):
        """2026年春节前交易日硬编码"""
        # 基于知识库：2026年1月30日为春节前最后一个交易日
        jan_2026_trading_days = [
            date(2026, 1, 2), date(2026, 1, 3), date(2026, 1, 6),
            date(2026, 1, 7), date(2026, 1, 8), date(2026, 1, 9),
            date(2026, 1, 10), date(2026, 1, 13), date(2026, 1, 14),
            date(2026, 1, 15), date(2026, 1, 16), date(2026, 1, 17),
            date(2026, 1, 20), date(2026, 1, 21), date(2026, 1, 22),
            date(2026, 1, 23), date(2026, 1, 24), date(2026, 1, 27),
            date(2026, 1, 28), date(2026, 1, 29), date(2026, 1, 30)
        ]
        self._trading_days = set(jan_2026_trading_days)

    def get_last_trading_day(self, before_date=None):
        """获取指定日期之前的最近交易日"""
        if before_date is None:
            before_date = date.today()

        # 向前查找最近交易日（最多30天）
        for i in range(30):
            check_date = before_date - timedelta(days=i)
            if check_date in self._trading_days:
                return check_date.strftime('%Y%m%d')

        # 终极兜底
        logger.critical(f"无法确定最近交易日，使用硬编码: 20260130")
        return "20260130"

    def is_trading_day(self, check_date):
        """检查是否为交易日"""
        if isinstance(check_date, str):
            try:
                check_date = date.fromisoformat(check_date.replace('/', '-').replace('\\', '-'))
            except ValueError:
                return False
        return check_date in self._trading_days