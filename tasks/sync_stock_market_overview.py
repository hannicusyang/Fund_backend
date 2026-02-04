# tasks/sync_stock_market_overview.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import akshare as ak
import pandas as pd
from datetime import datetime, date, timedelta
from config.logging_config import logger
from models import db
from models.stock_market_models_overview import (
    StockSSESummary, StockSZSESummary, StockSZSEAreaSummary,
    StockSZSESectorSummary, StockSSEDealDaily
)
from models.trading_day import TradingDay


from datetime import datetime, date
from models.trading_day import TradingDay

def get_effective_trading_date_for_sync():
    """
    根据当前时间和 trading_day 表，确定应同步的交易日：
    - 如果当前时间 >= 16:30 且今天是交易日 → 返回今天
    - 否则 → 返回上一个交易日（<= 昨天）
    """
    now = datetime.now()
    today = now.date()
    current_time = now.time()

    # 检查今天是否是交易日
    is_today_trading = db.session.query(
        db.exists().where(TradingDay.trade_date == today)
    ).scalar()

    cutoff_time = datetime.strptime("16:30", "%H:%M").time()

    if is_today_trading and current_time >= cutoff_time:
        # 已过16:30，且今天是交易日 → 可用今天
        logger.info(f"Current time {now.strftime('%Y-%m-%d %H:%M')} >= 16:30 and today is trading day → use today.")
        return today
    else:
        # 否则，使用上一个交易日（严格 < 今天）
        prev_trade_day = db.session.query(db.func.max(TradingDay.trade_date)) \
            .filter(TradingDay.trade_date < today) \
            .scalar()
        if prev_trade_day:
            reason = "before 16:30" if is_today_trading else "non-trading day"
            logger.info(f"Using previous trading day {prev_trade_day} because: {reason}.")
            return prev_trade_day
        else:
            # 极端情况：无历史交易日，回退到昨天（不推荐，仅保底）
            fallback = today - timedelta(days=1)
            logger.warning(f"No previous trading day found, falling back to {fallback}.")
            return fallback


def get_latest_available_month():
    """
    从当前月开始往前推，找到 AKShare 能返回有效数据的第一个月份。
    最多回退 12 个月，避免无限循环。
    """
    today = date.today()
    for i in range(12):  # 最多回退12个月
        first_of_current = (today.replace(day=1) - timedelta(days=i * 30))
        # 精确计算上 i 个月
        year = first_of_current.year
        month = first_of_current.month
        period_str = f"{year}{month:02d}"

        logger.info(f"Trying SZSE monthly data for period: {period_str}")
        try:
            df = ak.stock_szse_area_summary(date=period_str)
            if df is not None and not df.empty:
                logger.info(f"Found valid data for period: {period_str}")
                return period_str
        except Exception as e:
            logger.debug(f"Failed to fetch area summary for {period_str}: {e}")
            continue
    logger.error("Could not find any valid monthly data in last 12 months.")
    return None

def sync_sse_summary():
    """同步 SSE Summary，自动获取最新日，并从'报告时间'提取日期"""
    logger.info("Starting SSE Summary synchronization...")
    try:
        from app import app
        with app.app_context():
            df = ak.stock_sse_summary()
            if df is None or df.empty:
                logger.error("AKShare returned empty data for SSE Summary.")
                return

            # 关键修复：'项目' 是列，不是 index
            if '项目' not in df.columns:
                logger.error("Column '项目' not found in SSE DataFrame.")
                return

            # 提取报告时间（取主板列的第一个非NaN值）
            report_time_col = '主板'
            if report_time_col not in df.columns:
                logger.error("Column '主板' not found.")
                return

            report_time_series = df[df['项目'] == '报告时间'][report_time_col]
            if report_time_series.empty:
                logger.error("'报告时间' row not found.")
                return

            report_time_str = str(int(report_time_series.iloc[0]))
            try:
                trade_date = datetime.strptime(report_time_str, "%Y%m%d").date()
            except ValueError as e:
                logger.error(f"Failed to parse report time '{report_time_str}': {e}")
                return

            # 检查是否已存在
            existing = StockSSESummary.query.filter_by(trade_date=trade_date).first()
            if existing:
                logger.info(f"SSE Summary for {trade_date} already exists, skipping.")
                return

            # 设置 index 为 '项目'
            df_indexed = df.set_index('项目')

            field_map = {
                '流通股本': 'circulating_capital',
                '总市值': 'total_mv',
                '平均市盈率': 'avg_pe',
                '上市公司': 'companies',
                '上市股票': 'stocks',
                '流通市值': 'circulating_mv',
                '总股本': 'total_capital',
            }

            record_data = {'trade_date': trade_date}
            for row_label, attr_suffix in field_map.items():
                if row_label not in df_indexed.index:
                    logger.warning(f"Row '{row_label}' not found in SSE DataFrame.")
                    continue
                for board_type, col_name in [('main', '主板'), ('star', '科创板')]:
                    if col_name not in df_indexed.columns:
                        continue
                    value = df_indexed.at[row_label, col_name]
                    if pd.notna(value):
                        record_data[f"{board_type}_{attr_suffix}"] = float(value)

            if len(record_data) <= 1:
                logger.error("No valid data extracted from SSE Summary.")
                return

            record = StockSSESummary(**record_data)
            db.session.add(record)
            db.session.commit()
            logger.info(f"Successfully synchronized SSE Summary for {trade_date}.")

    except Exception as e:
        logger.exception(f"Failed to synchronize SSE Summary: {e}")
        db.session.rollback()


def sync_szse_summary():
    """同步 SZSE Summary，使用最新过去交易日"""
    logger.info("Starting SZSE Summary synchronization...")
    try:
        from app import app
        with app.app_context():
            target_date = get_effective_trading_date_for_sync()  # ← 使用新函数
            date_str = target_date.strftime("%Y%m%d")

            # 检查是否已存在
            if StockSZSESummary.query.filter_by(trade_date=target_date).count() > 0:
                logger.info(f"SZSE Summary for {target_date} already exists, skipping.")
                return

            logger.info(f"Fetching SZSE Summary for {date_str}...")
            try:
                df = ak.stock_szse_summary(date=date_str)
            except Exception as e:
                logger.error(f"AKShare error for SZSE Summary on {date_str}: {e}")
                return

            if df is None or df.empty:
                logger.error("AKShare returned empty data for SZSE Summary.")
                return

            # 清空当日旧数据
            StockSZSESummary.query.filter_by(trade_date=target_date).delete()

            records = []
            for _, row in df.iterrows():
                def safe_float(val):
                    return float(val) if pd.notna(val) else None

                record = StockSZSESummary(
                    trade_date=target_date,
                    security_type=row['证券类别'],
                    quantity=int(row['数量']) if pd.notna(row['数量']) else None,
                    turnover_amount=safe_float(row['成交金额']),
                    total_mv=safe_float(row['总市值']),
                    circulating_mv=safe_float(row['流通市值']),
                )
                records.append(record)

            db.session.bulk_save_objects(records)
            db.session.commit()
            logger.info(f"Synced SZSE Summary for {target_date}, {len(records)} records.")

    except Exception as e:
        logger.exception(f"Failed to sync SZSE Summary: {e}")
        db.session.rollback()


def sync_szse_area_summary(period_str):
    """同步 SZSE Area Summary，使用指定报告期"""
    logger.info(f"Starting SZSE Area Summary synchronization for {period_str}...")
    try:
        from app import app
        with app.app_context():
            if not period_str:
                logger.error("No period provided for SZSE Area Summary.")
                return

            if StockSZSEAreaSummary.query.filter_by(report_period=period_str).count() > 0:
                logger.info(f"SZSE Area Summary for {period_str} exists, skipping.")
                return

            logger.info(f"Fetching SZSE Area Summary for {period_str}...")
            try:
                df = ak.stock_szse_area_summary(date=period_str)
            except Exception as e:
                logger.error(f"AKShare error for SZSE Area on {period_str}: {e}")
                return

            if df is None or df.empty:
                logger.error("AKShare returned empty data for SZSE Area Summary.")
                return

            StockSZSEAreaSummary.query.filter_by(report_period=period_str).delete()
            records = []
            for _, row in df.iterrows():
                def safe_float(val):
                    return float(val) if pd.notna(val) else None

                record = StockSZSEAreaSummary(
                    report_period=period_str,
                    area=row['地区'],
                    serial_number=int(row['序号']) if pd.notna(row['序号']) else None,
                    total_turnover=safe_float(row['总交易额']),
                    market_share=safe_float(row['占市场']),
                    stock_turnover=safe_float(row.get('股票交易额')),
                    fund_turnover=safe_float(row.get('基金交易额')),
                    bond_turnover=safe_float(row.get('债券交易额')),
                    preferred_stock_turnover=safe_float(row.get('优先股交易额')),
                    option_turnover=safe_float(row.get('期权交易额')),
                )
                records.append(record)

            if records:
                db.session.bulk_save_objects(records)
                db.session.commit()
                logger.info(f"Synced SZSE Area Summary for {period_str}, {len(records)} records.")
            else:
                logger.warning("No records generated for SZSE Area Summary.")

    except Exception as e:
        logger.exception(f"Failed to sync SZSE Area Summary: {e}")
        db.session.rollback()


def sync_szse_sector_summary(period_str):
    """同步 SZSE Sector Summary，使用指定报告期"""
    logger.info(f"Starting SZSE Sector Summary synchronization for {period_str} ('当年')...")
    try:
        from app import app
        with app.app_context():
            if not period_str:
                logger.error("No period provided for SZSE Sector Summary.")
                return

            if StockSZSESectorSummary.query.filter_by(report_period=period_str, symbol='当年').count() > 0:
                logger.info(f"SZSE Sector Summary for {period_str} ('当年') exists, skipping.")
                return

            logger.info(f"Fetching SZSE Sector Summary for {period_str}, symbol '当年'...")
            try:
                df = ak.stock_szse_sector_summary(symbol="当年", date=period_str)
            except Exception as e:
                logger.error(f"AKShare error for SZSE Sector on {period_str}: {e}")
                return

            if df is None or df.empty:
                logger.error("AKShare returned empty data for SZSE Sector Summary.")
                return

            StockSZSESectorSummary.query.filter_by(report_period=period_str, symbol='当年').delete()
            records = []
            for _, row in df.iterrows():
                def safe_int(val):
                    return int(val) if pd.notna(val) else None
                def safe_float(val):
                    return float(val) if pd.notna(val) else None

                record = StockSZSESectorSummary(
                    report_period=period_str,
                    symbol='当年',
                    sector_chinese=row['项目名称'],
                    sector_english=row['项目名称-英文'],
                    trading_days=safe_int(row['交易天数']),
                    turnover_amount_cny=safe_int(row['成交金额-人民币元']),
                    turnover_amount_pct=safe_float(row['成交金额-占总计']),
                    volume_shares=safe_int(row['成交股数-股数']),
                    volume_shares_pct=safe_float(row['成交股数-占总计']),
                    deal_count=safe_int(row['成交笔数-笔']),
                    deal_count_pct=safe_float(row['成交笔数-占总计']),
                )
                records.append(record)

            if records:
                db.session.bulk_save_objects(records)
                db.session.commit()
                logger.info(f"Synced SZSE Sector Summary for {period_str} ('当年'), {len(records)} records.")
            else:
                logger.warning("No records generated for SZSE Sector Summary.")

    except Exception as e:
        logger.exception(f"Failed to sync SZSE Sector Summary: {e}")
        db.session.rollback()

def sync_szse_sector_month_summary(period_str):
    """同步 SZSE Sector Summary，使用指定报告期"""
    logger.info(f"Starting SZSE Sector Summary synchronization for {period_str} ('当月')...")
    try:
        from app import app
        with app.app_context():
            if not period_str:
                logger.error("No period provided for SZSE Sector Summary.")
                return

            if StockSZSESectorSummary.query.filter_by(report_period=period_str, symbol='当月').count() > 0:
                logger.info(f"SZSE Sector Summary for {period_str} ('当月') exists, skipping.")
                return

            logger.info(f"Fetching SZSE Sector Summary for {period_str}, symbol '当月'...")
            try:
                df = ak.stock_szse_sector_summary(symbol="当月", date=period_str)
            except Exception as e:
                logger.error(f"AKShare error for SZSE Sector on {period_str}: {e}")
                return

            if df is None or df.empty:
                logger.error("AKShare returned empty data for SZSE Sector Summary.")
                return

            StockSZSESectorSummary.query.filter_by(report_period=period_str, symbol='当月').delete()
            records = []
            for _, row in df.iterrows():
                def safe_int(val):
                    return int(val) if pd.notna(val) else None
                def safe_float(val):
                    return float(val) if pd.notna(val) else None

                record = StockSZSESectorSummary(
                    report_period=period_str,
                    symbol='当月',
                    sector_chinese=row['项目名称'],
                    sector_english=row['项目名称-英文'],
                    trading_days=safe_int(row['交易天数']),
                    turnover_amount_cny=safe_int(row['成交金额-人民币元']),
                    turnover_amount_pct=safe_float(row['成交金额-占总计']),
                    volume_shares=safe_int(row['成交股数-股数']),
                    volume_shares_pct=safe_float(row['成交股数-占总计']),
                    deal_count=safe_int(row['成交笔数-笔']),
                    deal_count_pct=safe_float(row['成交笔数-占总计']),
                )
                records.append(record)

            if records:
                db.session.bulk_save_objects(records)
                db.session.commit()
                logger.info(f"Synced SZSE Sector Summary for {period_str} ('当月'), {len(records)} records.")
            else:
                logger.warning("No records generated for SZSE Sector Summary.")

    except Exception as e:
        logger.exception(f"Failed to sync SZSE Sector Summary: {e}")
        db.session.rollback()


def sync_sse_deal_daily():
    logger.info("Starting SSE Deal Daily synchronization...")
    try:
        from app import app
        with app.app_context():
            target_date = get_effective_trading_date_for_sync()
            date_str = target_date.strftime("%Y%m%d")

            if StockSSEDealDaily.query.filter_by(trade_date=target_date).first():
                logger.info(f"SSE Deal Daily for {target_date} exists, skipping.")
                return

            logger.info(f"Fetching SSE Deal Daily for {date_str}...")
            try:
                df = ak.stock_sse_deal_daily(date=date_str)
            except Exception as e:
                logger.error(f"AKShare error for SSE Deal Daily on {date_str}: {e}")
                return

            if df is None or df.empty:
                logger.warning(f"AKShare returned empty data for SSE Deal Daily on {date_str}.")
                return

            # 关键修复：正确设置 index
            if '单日情况' not in df.columns:
                logger.error("Column '单日情况' not found in SSE Deal Daily DataFrame.")
                return

            df = df.set_index('单日情况')
            logger.info(f"SSE Deal Daily index after set_index: {list(df.index)}")
            logger.info(f"Type of first index: {type(df.index[0])}, repr: {repr(df.index[0])}")

            col_to_prefix = {
                '股票': 'stock',
                '主板A': 'main_a',
                '主板B': 'main_b',
                '科创板': 'star',
                '股票回购': 'repo'
            }

            row_labels_to_suffix = {
                '挂牌数': 'listed_count',
                '市价总值': 'total_mv',
                '流通市值': 'circulating_mv',
                '成交金额': 'turnover_amount',
                '成交量': 'volume',
                '平均市盈率': 'avg_pe',
                '换手率': 'turnover_rate',
                '流通换手率': 'circulating_turnover_rate',
            }

            record_data = {'trade_date': target_date}
            for metric, suffix in row_labels_to_suffix.items():
                if metric not in df.index:
                    continue
                for col_name, prefix in col_to_prefix.items():
                    if col_name not in df.columns:
                        continue
                    value = df.at[metric, col_name]
                    if pd.notna(value):
                        attr_name = f"{suffix}_{prefix}"  # ← 关键修复：suffix 在前，prefix 在后
                        if hasattr(StockSSEDealDaily, attr_name):
                            record_data[attr_name] = float(value)
                        else:
                            logger.debug(f"Field {attr_name} not found in model.")

            if len(record_data) <= 1:
                logger.error("No valid data extracted from SSE Deal Daily.")
                return

            record = StockSSEDealDaily(**record_data)
            db.session.add(record)
            db.session.commit()
            logger.info(f"Successfully synchronized SSE Deal Daily for {target_date}.")

    except Exception as e:
        logger.exception(f"Failed to sync SSE Deal Daily: {e}")
        db.session.rollback()


def sync_all_stock_overview():
    logger.info("Starting full stock market overview synchronization.")
    sync_sse_summary()
    sync_szse_summary()

    # 统一获取月度周期
    monthly_period = get_latest_available_month()
    if monthly_period:
        sync_szse_area_summary(monthly_period)
        sync_szse_sector_summary(monthly_period)
        sync_szse_sector_month_summary(monthly_period)
    else:
        logger.warning("Skipping monthly SZSE summaries due to no available data.")

    sync_sse_deal_daily()
    logger.info("Completed stock market overview synchronization.")


if __name__ == "__main__":
    sync_all_stock_overview()