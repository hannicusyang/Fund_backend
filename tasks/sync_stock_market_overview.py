# tasks/sync_stock_market_overview.py

import sys
import os

# 确保能找到 app 和 models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import akshare as ak
import pandas as pd
from datetime import datetime, date, timedelta
from config.logging_config import logger
from models import db
from models.stock_market_overview import (
    StockSSESummary, StockSZSESummary, StockSZSEAreaSummary,
    StockSZSESectorSummary, StockSSEDealDaily
)
from models.trading_day import TradingDay  # 假设您有此模型用于日历检查


def get_latest_trading_day_or_yesterday():
    """
    获取数据库中最新的非未来交易日。如果不存在，则使用昨天的日期。
    """
    today = date.today()
    # 查询小于或等于今天的最大交易日
    latest_valid_trade_day = db.session.query(db.func.max(TradingDay.trade_date)) \
        .filter(TradingDay.trade_date <= today) \
        .scalar()

    if latest_valid_trade_day:
        logger.info(f"Found latest valid (non-future) trading day in DB: {latest_valid_trade_day}")
        return latest_valid_trade_day
    else:
        # 如果数据库中没有找到有效交易日，则回退到昨天
        logger.warning("No valid (non-future) trading days found in database, using yesterday's date.")
        return date.today() - timedelta(days=1)


def sync_sse_summary():
    """
    同步上海证券交易所股票数据总貌 (stock_sse_summary)。
    """
    logger.info("Starting SSE Summary synchronization...")
    try:
        from app import app
        with app.app_context():
            # 根据数据库最新记录或昨天确定目标日期
            target_date = get_latest_trading_day_or_yesterday()
            logger.info(f"Determined target date for SSE Summary: {target_date}")

            # 检查目标日期的数据是否已存在
            existing = StockSSESummary.query.filter_by(trade_date=target_date).first()
            if existing:
                logger.info(f"SSE Summary for {target_date} already exists, skipping.")
                return

            logger.info(f"Fetching SSE Summary for {target_date}...")
            df = ak.stock_sse_summary()
            if df is None or df.empty:
                logger.error("AKShare returned empty data for SSE Summary.")
                return

            logger.debug(f"Fetched SSE data:\n{df}")

            # 定义 DataFrame 索引 (行) 和列的中文标签
            # 行索引: 项目
            index_labels = ['流通股本', '总市值', '平均市盈率', '上市公司', '上市股票', '流通市值', '总股本']
            # 列: 股票, 科创板, 主板
            column_labels = ['股票', '科创板', '主板']

            # 映射: 行索引 -> 模型字段后缀
            field_map = {
                '流通股本': 'circulating_capital',
                '总市值': 'total_mv',
                '平均市盈率': 'avg_pe',
                '上市公司': 'companies',  # 注意: 这通常指上市公司总数
                '上市股票': 'stocks',  # 注意: 这通常指上市股票总数
                '流通市值': 'circulating_mv',
                '总股本': 'total_capital',
            }

            # 映射: 列名 -> 模型字段前缀
            prefix_map = {
                '股票': 'stock',
                '科创板': 'star',
                '主板': 'main'
            }

            record_data = {'trade_date': target_date}
            for index_label in index_labels:
                if index_label not in df.index:
                    logger.warning(f"Index '{index_label}' not found in the fetched DataFrame for SSE Summary.")
                    continue
                for column_label in column_labels:
                    if column_label not in df.columns:
                        logger.warning(f"Column '{column_label}' not found in the fetched DataFrame for SSE Summary.")
                        continue
                    try:
                        value = df.at[index_label, column_label]
                        if pd.isna(value):
                            logger.debug(f"Value for '{index_label}' in '{column_label}' is NaN, skipping.")
                            continue

                        # 获取模型属性后缀
                        attr_suffix = field_map.get(index_label)
                        if attr_suffix:
                            # 获取模型属性前缀
                            prefix = prefix_map.get(column_label)
                            if prefix:
                                full_attr = f"{prefix}_{attr_suffix}"
                                if hasattr(StockSSESummary, full_attr):
                                    record_data[full_attr] = float(value)  # 确保为数值类型
                                else:
                                    logger.warning(f"Model attribute '{full_attr}' does not exist on StockSSESummary.")
                            else:
                                logger.warning(f"Unknown column label '{column_label}' encountered.")
                        else:
                            logger.warning(f"Unknown index label '{index_label}' encountered.")
                    except (KeyError, IndexError, TypeError) as e:
                        logger.warning(
                            f"Could not access value for '{index_label}' in '{column_label}' for SSE Summary. Error: {e}")
                        continue  # 访问失败则跳过该单元格

            logger.debug(f"Prepared record data: {record_data}")

            # 检查是否成功提取了有效数据再插入
            if len(record_data) <= 1:  # 只有 'trade_date'
                logger.error("No valid data could be extracted from the SSE Summary DataFrame.")
                return

            record = StockSSESummary(**record_data)
            db.session.add(record)
            db.session.commit()
            logger.info(f"Successfully synchronized SSE Summary for {target_date}.")

    except Exception as e:
        # 确保在应用上下文中执行回滚
        from app import app
        with app.app_context():
            db.session.rollback()
        logger.error(f"Failed to synchronize SSE Summary: {e}")


def sync_szse_summary():
    """
    同步深圳证券交易所证券类别统计 (stock_szse_summary)。
    """
    logger.info("Starting SZSE Summary synchronization...")
    try:
        from app import app
        with app.app_context():
            target_date = get_latest_trading_day_or_yesterday()
            logger.info(f"Determined target date for SZSE Summary: {target_date}")

            # 检查目标日期的数据是否已存在
            existing_count = StockSZSESummary.query.filter_by(trade_date=target_date).count()
            if existing_count > 0:
                logger.info(f"SZSE Summary for {target_date} already exists, skipping.")
                return

            date_str = target_date.strftime("%Y%m%d")
            logger.info(f"Fetching SZSE Summary for {date_str}...")
            try:
                df = ak.stock_szse_summary(date=date_str)
            except ValueError as ve:  # 捕获 "Invalid date format" 或 "Date is in the future" 等错误
                logger.error(f"AKShare error fetching SZSE Summary for {date_str}: {ve}")
                return

            if df is None or df.empty:
                logger.error("AKShare returned empty data for SZSE Summary.")
                return

            logger.debug(f"Fetched SZSE data:\n{df}")

            # 清空旧数据（以防重新运行）
            StockSZSESummary.query.filter_by(trade_date=target_date).delete()
            records = []
            for _, row in df.iterrows():
                # --- 创建记录前处理 NaN 值 ---
                # 将 NaN 值替换为 None (Python 的 null)
                quantity_val = row['数量'] if not pd.isna(row['数量']) else None
                turnover_amount_val = row['成交金额'] if not pd.isna(row['成交金额']) else None
                total_mv_val = row['总市值'] if not pd.isna(row['总市值']) else None
                circulating_mv_val = row['流通市值'] if not pd.isna(row['流通市值']) else None

                record = StockSZSESummary(
                    trade_date=target_date,
                    security_type=row['证券类别'],
                    # 例如: '股票', '主板A股', '创业板A股', '基金', '债券', '债券现券', 'ETF', 'LOF', '封闭式基金', '分级基金', 'ABS', '期权'
                    quantity=quantity_val,
                    turnover_amount=turnover_amount_val,
                    total_mv=total_mv_val,
                    circulating_mv=circulating_mv_val,
                )
                records.append(record)

            db.session.bulk_save_objects(records)
            db.session.commit()
            logger.info(f"Successfully synchronized SZSE Summary for {target_date}, {len(records)} records.")

    except Exception as e:
        from app import app
        with app.app_context():
            db.session.rollback()
        logger.error(f"Failed to synchronize SZSE Summary: {e}")


def sync_szse_area_summary():
    """
    同步深圳证券交易所地区交易排序 (stock_szse_area_summary) (月度数据)。
    """
    logger.info("Starting SZSE Area Summary synchronization...")
    try:
        from app import app
        with app.app_context():
            # 使用上个月作为默认周期
            today = date.today()
            first_of_current_month = today.replace(day=1)
            last_of_prev_month = first_of_current_month - timedelta(days=1)
            period_str = last_of_prev_month.strftime("%Y%m")  # 例如 "202512"
            logger.info(f"Determined target period for SZSE Area Summary: {period_str}")

            # 检查该周期的数据是否已存在
            existing_count = StockSZSEAreaSummary.query.filter_by(report_period=period_str).count()
            if existing_count > 0:
                logger.info(f"SZSE Area Summary for {period_str} already exists, skipping.")
                return

            logger.info(f"Fetching SZSE Area Summary for {period_str}...")
            try:
                df = ak.stock_szse_area_summary(date=period_str)
            except Exception as e:  # 捕获潜在错误，包括长度不匹配或无效日期
                logger.error(f"AKShare error fetching SZSE Area Summary for {period_str}: {e}")
                return

            if df is None or df.empty:
                logger.error("AKShare returned empty data for SZSE Area Summary.")
                return

            logger.debug(f"Fetched SZSE Area data:\n{df}")

            # 清空该周期的旧数据
            StockSZSEAreaSummary.query.filter_by(report_period=period_str).delete()
            records = []
            for _, row in df.iterrows():
                # --- 创建记录前处理 NaN 值 ---
                record_kwargs = {
                    'report_period': period_str,
                    'area': row['地区'],  # 例如: '上海', '深圳', '浙江', ...
                    'serial_number': row['序号'],  # 替换 NaN 为 None
                    'total_turnover': row['总交易额'] if not pd.isna(row['总交易额']) else None,  # 单位: 元
                    'market_share': row['占市场'] if not pd.isna(row['占市场']) else None,  # 单位: %
                    'stock_turnover': row['股票交易额'] if not pd.isna(row['股票交易额']) else None,  # 单位: 元
                    'fund_turnover': row['基金交易额'] if not pd.isna(row['基金交易额']) else None,  # 单位: 元
                    'bond_turnover': row['债券交易额'] if not pd.isna(row['债券交易额']) else None,  # 单位: 元
                    # 2025年新增字段，使用 .get() 安全获取，防止旧版本 akshare 没有这些列
                    'preferred_stock_turnover': row.get('优先股交易额'),
                    'option_turnover': row.get('期权交易额'),
                }
                # 对新获取的可选列也进行 NaN 检查
                for key in ['preferred_stock_turnover', 'option_turnover']:
                    if key in record_kwargs and pd.isna(record_kwargs[key]):
                        record_kwargs[key] = None

                record = StockSZSEAreaSummary(**record_kwargs)
                records.append(record)

            if records:  # 仅在有记录要保存时才继续
                db.session.bulk_save_objects(records)
                db.session.commit()
                logger.info(f"Successfully synchronized SZSE Area Summary for {period_str}, {len(records)} records.")
            else:
                logger.warning(f"No valid records generated for SZSE Area Summary {period_str}.")

    except Exception as e:
        from app import app
        with app.app_context():
            db.session.rollback()
        logger.error(f"Failed to synchronize SZSE Area Summary: {e}")


def sync_szse_sector_summary():
    """
    同步深圳证券交易所股票行业成交数据 (stock_szse_sector_summary) (月度数据)。
    """
    logger.info("Starting SZSE Sector Summary synchronization...")
    try:
        from app import app
        with app.app_context():
            # 使用上个月作为默认周期
            today = date.today()
            first_of_current_month = today.replace(day=1)
            last_of_prev_month = first_of_current_month - timedelta(days=1)
            period_str = last_of_prev_month.strftime("%Y%m")  # 例如 "202512"
            logger.info(f"Determined target period for SZSE Sector Summary: {period_str}")

            # 检查该周期和 '当年' 符号的数据是否已存在
            existing_count = StockSZSESectorSummary.query.filter_by(report_period=period_str, symbol='当年').count()
            if existing_count > 0:
                logger.info(f"SZSE Sector Summary for {period_str} ('当年') already exists, skipping.")
                return

            logger.info(f"Fetching SZSE Sector Summary for {period_str}, symbol '当年'...")
            try:
                df = ak.stock_szse_sector_summary(symbol="当年", date=period_str)
            except ValueError as ve:  # 可能由无效日期字符串格式或未来日期引起
                logger.error(f"AKShare ValueError fetching SZSE Sector Summary for {period_str} ('当年'): {ve}")
                return
            except Exception as e:
                logger.error(f"AKShare general error fetching SZSE Sector Summary for {period_str} ('当年'): {e}")
                return

            if df is None or df.empty:
                logger.error("AKShare returned empty data for SZSE Sector Summary.")
                return

            logger.debug(f"Fetched SZSE Sector data:\n{df}")

            # 清空该周期和符号的旧数据
            StockSZSESectorSummary.query.filter_by(report_period=period_str, symbol='当年').delete()
            records = []
            for _, row in df.iterrows():
                # --- 创建记录前处理 NaN 值 ---
                record = StockSZSESectorSummary(
                    report_period=period_str,
                    symbol='当年',  # '当月' 或 '当年'
                    sector_chinese=row['项目名称'],  # 例如: '合计', '农林牧渔', '制造业', ...
                    sector_english=row['项目名称-英文'],  # 例如: 'Total', 'Agriculture', 'Manufacturing', ...
                    trading_days=row['交易天数'],  # 替换 NaN 为 None
                    turnover_amount_cny=row['成交金额-人民币元'] if not pd.isna(row['成交金额-人民币元']) else None,
                    # 单位: 元
                    turnover_amount_pct=row['成交金额-占总计'] if not pd.isna(row['成交金额-占总计']) else None,
                    # 单位: %
                    volume_shares=row['成交股数-股数'] if not pd.isna(row['成交股数-股数']) else None,  # 单位: 股
                    volume_shares_pct=row['成交股数-占总计'] if not pd.isna(row['成交股数-占总计']) else None,  # 单位: %
                    deal_count=row['成交笔数-笔'] if not pd.isna(row['成交笔数-笔']) else None,  # 单位: 笔
                    deal_count_pct=row['成交笔数-占总计'] if not pd.isna(row['成交笔数-占总计']) else None,  # 单位: %
                )
                records.append(record)

            if records:  # 仅在有记录要保存时才继续
                db.session.bulk_save_objects(records)
                db.session.commit()
                logger.info(
                    f"Successfully synchronized SZSE Sector Summary for {period_str} ('当年'), {len(records)} records.")
            else:
                logger.warning(f"No valid records generated for SZSE Sector Summary {period_str} ('当年').")

    except Exception as e:
        from app import app
        with app.app_context():
            db.session.rollback()
        logger.error(f"Failed to synchronize SZSE Sector Summary: {e}")


def sync_sse_deal_daily():
    """
    同步上海证券交易所每日股票情况 (stock_sse_deal_daily)。
    """
    logger.info("Starting SSE Deal Daily synchronization...")
    try:
        from app import app
        with app.app_context():
            target_date = get_latest_trading_day_or_yesterday()
            logger.info(f"Determined target date for SSE Deal Daily: {target_date}")

            # 检查目标日期的数据是否已存在
            existing = StockSSEDealDaily.query.filter_by(trade_date=target_date).first()
            if existing:
                logger.info(f"SSE Deal Daily for {target_date} already exists, skipping.")
                return

            date_str = target_date.strftime("%Y%m%d")
            logger.info(f"Fetching SSE Deal Daily for {date_str}...")
            try:
                df = ak.stock_sse_deal_daily(date=date_str)
            except ValueError as ve:  # 捕获 "Invalid date format" 或 "Date is in the future" 等错误
                logger.error(f"AKShare error fetching SSE Deal Daily for {date_str}: {ve}")
                return

            if df is None or df.empty:
                logger.error("AKShare returned empty data for SSE Deal Daily.")
                return

            logger.debug(f"Fetched SSE Deal Daily data:\n{df}")

            # DataFrame 结构可能变化。先检查是否有数据
            if len(df) == 0:
                logger.warning("Fetched SSE Deal Daily DataFrame is empty.")
                return

            # 假设第一行包含数据 (通常如此)
            # 行索引: '单日情况' (如 '挂牌数', '市价总值', ...)
            # 列: '股票', '主板A', '主板B', '科创板', '股票回购'
            record_data = {'trade_date': target_date}

            # 定义从 akshare 列名到模型字段前缀的映射
            col_to_prefix = {
                '股票': 'stock',
                '主板A': 'main_a',
                '主板B': 'main_b',
                '科创板': 'star',
                '股票回购': 'repo'
            }
            # 定义从行索引到模型字段后缀的映射
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

            # 遍历 DataFrame 的每一行 (指标) 和每一列 (证券类型)
            for idx, row in df.iterrows():
                # idx 应该是指标类型，如 '挂牌数', '市价总值' 等
                if idx in row_labels_to_suffix:
                    suffix = row_labels_to_suffix[idx]
                    for col_name, value in row.items():
                        if col_name in col_to_prefix:
                            prefix = col_to_prefix[col_name]
                            attr_name = f"{prefix}_{suffix}"
                            if hasattr(StockSSEDealDaily, attr_name):
                                # --- 这里也要处理 NaN 值 ---
                                if not pd.isna(value):
                                    record_data[attr_name] = value
                                else:
                                    logger.debug(f"Skipping NaN value for attribute '{attr_name}'.")
                            else:
                                logger.debug(
                                    f"(Alternative) Model attribute '{attr_name}' does not exist on StockSSEDealDaily.")

            logger.debug(f"Prepared record data for SSE Deal Daily: {record_data}")
            record = StockSSEDealDaily(**record_data)
            db.session.add(record)
            db.session.commit()
            logger.info(f"Successfully synchronized SSE Deal Daily for {target_date}.")

    except Exception as e:
        from app import app
        with app.app_context():
            db.session.rollback()
        logger.error(f"Failed to synchronize SSE Deal Daily: {e}")


def sync_all_stock_overview():
    """
    运行所有同步函数。
    """
    logger.info("Starting full stock market overview synchronization.")
    sync_sse_summary()
    sync_szse_summary()
    sync_szse_area_summary()
    sync_szse_sector_summary()
    sync_sse_deal_daily()
    logger.info("Completed stock market overview synchronization.")


if __name__ == "__main__":
    sync_all_stock_overview()