# tasks/sync_index_history.py
"""
指数历史行情数据同步任务
支持多数据源：新浪、腾讯、东方财富、东财通用接口
自动切换数据源，优先使用数据最全的接口
同步策略：每次运行全量更新（不限制日期范围），自动覆盖旧数据
"""
import akshare as ak
# 导入tushare
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.tushare_api import get_pro

import pandas as pd
# 导入tushare
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.tushare_api import get_pro

from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
import time
# 导入tushare
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.tushare_api import get_pro

import requests
# 导入tushare
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.tushare_api import get_pro


from config.logging_config import logger
from models import db
from models.index_history import IndexHistory, BENCHMARK_INDICES, get_index_symbol

# 数据源优先级：优先使用不限制日期的接口，hist作为备选
DATA_SOURCE_PRIORITY = ['em', 'sina', 'tx', 'hist']

# 请求间隔（秒）
REQUEST_DELAY = 0.5


def safe_float(value) -> Optional[float]:
    """安全转换为float"""
    if value is None or value == '' or pd.isna(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def safe_int(value) -> Optional[int]:
    """安全转换为int"""
    if value is None or value == '' or pd.isna(value):
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def calculate_change_pct(current_close: float, prev_close: float) -> Optional[float]:
    """计算涨跌幅"""
    if current_close is None or prev_close is None or prev_close == 0:
        return None
    try:
        return round((current_close - prev_close) / prev_close * 100, 4)
    except:
        return None


def fetch_from_em_interface(symbol: str) -> Tuple[Optional[pd.DataFrame], str]:
    """
    从东方财富接口获取指数历史数据（不限制日期，获取全部）
    接口: stock_zh_index_daily_em
    返回: date, open, close, high, low, volume, amount
    """
    try:
        logger.debug(f"[em] 获取 {symbol} 历史数据...")
        df = ak.stock_zh_index_daily_em(symbol=symbol)
        if df is not None and not df.empty:
            logger.debug(f"[em] {symbol} 获取成功，共 {len(df)} 条")
            return df, 'em'
        return None, 'em'
    except Exception as e:
        logger.debug(f"[em] {symbol} 获取失败: {str(e)[:50]}")
        return None, 'em'


def fetch_from_sina_interface(symbol: str) -> Tuple[Optional[pd.DataFrame], str]:
    """
    从新浪接口获取指数历史数据（不限制日期，获取全部）
    接口: stock_zh_index_daily
    返回: date, open, high, low, close, volume
    """
    try:
        logger.debug(f"[sina] 获取 {symbol} 历史数据...")
        df = ak.stock_zh_index_daily(symbol=symbol)
        if df is not None and not df.empty:
            logger.debug(f"[sina] {symbol} 获取成功，共 {len(df)} 条")
            return df, 'sina'
        return None, 'sina'
    except Exception as e:
        logger.debug(f"[sina] {symbol} 获取失败: {str(e)[:50]}")
        return None, 'sina'


def fetch_from_tx_interface(symbol: str) -> Tuple[Optional[pd.DataFrame], str]:
    """
    从腾讯接口获取指数历史数据（不限制日期，获取全部）
    接口: stock_zh_index_daily_tx
    返回: date, open, close, high, low, amount（单位：手）
    """
    try:
        logger.debug(f"[tx] 获取 {symbol} 历史数据...")
        df = ak.stock_zh_index_daily_tx(symbol=symbol)
        if df is not None and not df.empty:
            logger.debug(f"[tx] {symbol} 获取成功，共 {len(df)} 条")
            return df, 'tx'
        return None, 'tx'
    except Exception as e:
        logger.debug(f"[tx] {symbol} 获取失败: {str(e)[:50]}")
        return None, 'tx'


def fetch_from_hist_interface(symbol: str) -> Tuple[Optional[pd.DataFrame], str]:
    """
    从东方财富通用接口获取指数历史数据（备选）
    接口: index_zh_a_hist （需要日期参数，默认获取1970-2050）
    """
    try:
        logger.debug(f"[hist] 获取 {symbol} 历史数据...")
        df = ak.index_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date="19700101",
            end_date="20500101"
        )
        if df is not None and not df.empty:
            logger.debug(f"[hist] {symbol} 获取成功，共 {len(df)} 条")
            return df, 'hist'
        return None, 'hist'
    except Exception as e:
        logger.debug(f"[hist] {symbol} 获取失败: {str(e)[:50]}")
        return None, 'hist'


def fetch_index_history(index_code: str,
                        preferred_source: Optional[str] = None) -> Tuple[Optional[pd.DataFrame], str]:
    """
    获取指数历史数据（不限制日期范围），支持多数据源自动切换
    """
    symbol = get_index_symbol(index_code)
    logger.info(f"获取 {index_code}({BENCHMARK_INDICES.get(index_code, '未知')}) 全部历史数据")

    if preferred_source and preferred_source in DATA_SOURCE_PRIORITY:
        source_order = [preferred_source] + [s for s in DATA_SOURCE_PRIORITY if s != preferred_source]
    else:
        source_order = DATA_SOURCE_PRIORITY

    errors = []

    for source in source_order:
        try:
            if source == 'em':
                df, src = fetch_from_em_interface(symbol)
            elif source == 'sina':
                df, src = fetch_from_sina_interface(symbol)
            elif source == 'tx':
                df, src = fetch_from_tx_interface(symbol)
            elif source == 'hist':
                hist_symbol = symbol.replace('sh', '').replace('sz', '')
                df, src = fetch_from_hist_interface(hist_symbol)
            else:
                continue

            if df is not None and not df.empty:
                return df, src

        except Exception as e:
            error_msg = f"[{source}]{str(e)[:30]}"
            errors.append(error_msg)
            continue

    logger.error(f"❌ {index_code} 所有数据源失败: {'; '.join(errors)}")
    return None, ''


def convert_hist_to_db_format(df: pd.DataFrame, index_code: str, index_name: str) -> List[Dict]:
    """转换东财通用接口数据为数据库格式"""
    records = []
    prev_close = None

    for _, row in df.iterrows():
        try:
            close_val = safe_float(row.get('收盘'))
            change_pct = safe_float(row.get('涨跌幅'))
            if change_pct is None and prev_close is not None and close_val is not None:
                change_pct = calculate_change_pct(close_val, prev_close)

            record = {
                'index_code': index_code,
                'index_name': index_name,
                'trade_date': pd.to_datetime(row.get('日期')).date(),
                'open': safe_float(row.get('开盘')),
                'close': close_val,
                'high': safe_float(row.get('最高')),
                'low': safe_float(row.get('最低')),
                'volume': safe_int(row.get('成交量')),
                'amount': safe_float(row.get('成交额')),
                'change_pct': change_pct,
                'change_amount': safe_float(row.get('涨跌额')),
                'amplitude': safe_float(row.get('振幅')),
                'turnover_rate': safe_float(row.get('换手率')),
                'source': 'hist'
            }
            if record['volume'] is not None:
                record['volume'] = record['volume'] * 100
            records.append(record)
            prev_close = close_val
        except Exception as e:
            logger.warning(f"处理 hist 数据行失败: {e}")
            continue
    return records


def convert_em_to_db_format(df: pd.DataFrame, index_code: str, index_name: str) -> List[Dict]:
    """转换东方财富接口数据为数据库格式"""
    records = []
    prev_close = None

    for _, row in df.iterrows():
        try:
            close_val = safe_float(row.get('close'))
            change_pct = None
            if prev_close is not None and close_val is not None:
                change_pct = calculate_change_pct(close_val, prev_close)

            record = {
                'index_code': index_code,
                'index_name': index_name,
                'trade_date': pd.to_datetime(row.get('date')).date(),
                'open': safe_float(row.get('open')),
                'close': close_val,
                'high': safe_float(row.get('high')),
                'low': safe_float(row.get('low')),
                'volume': safe_int(row.get('volume')),
                'amount': safe_float(row.get('amount')),
                'change_pct': change_pct,
                'change_amount': None,
                'amplitude': None,
                'turnover_rate': None,
                'source': 'em'
            }
            records.append(record)
            prev_close = close_val
        except Exception as e:
            logger.warning(f"处理 em 数据行失败: {e}")
            continue
    return records


def convert_sina_to_db_format(df: pd.DataFrame, index_code: str, index_name: str) -> List[Dict]:
    """转换新浪接口数据为数据库格式"""
    records = []
    prev_close = None

    for _, row in df.iterrows():
        try:
            close_val = safe_float(row.get('close'))
            change_pct = None
            if prev_close is not None and close_val is not None:
                change_pct = calculate_change_pct(close_val, prev_close)

            record = {
                'index_code': index_code,
                'index_name': index_name,
                'trade_date': pd.to_datetime(row.get('date')).date(),
                'open': safe_float(row.get('open')),
                'close': close_val,
                'high': safe_float(row.get('high')),
                'low': safe_float(row.get('low')),
                'volume': safe_int(row.get('volume')),
                'amount': None,
                'change_pct': change_pct,
                'change_amount': None,
                'amplitude': None,
                'turnover_rate': None,
                'source': 'sina'
            }
            records.append(record)
            prev_close = close_val
        except Exception as e:
            logger.warning(f"处理 sina 数据行失败: {e}")
            continue
    return records


def convert_tx_to_db_format(df: pd.DataFrame, index_code: str, index_name: str) -> List[Dict]:
    """转换腾讯接口数据为数据库格式"""
    records = []
    prev_close = None

    for _, row in df.iterrows():
        try:
            close_val = safe_float(row.get('close'))
            change_pct = None
            if prev_close is not None and close_val is not None:
                change_pct = calculate_change_pct(close_val, prev_close)

            amount_hands = safe_float(row.get('amount'))
            amount_yuan = None
            if amount_hands is not None and close_val is not None:
                amount_yuan = amount_hands * 100 * close_val

            record = {
                'index_code': index_code,
                'index_name': index_name,
                'trade_date': pd.to_datetime(row.get('date')).date(),
                'open': safe_float(row.get('open')),
                'close': close_val,
                'high': safe_float(row.get('high')),
                'low': safe_float(row.get('low')),
                'volume': None,
                'amount': amount_yuan,
                'change_pct': change_pct,
                'change_amount': None,
                'amplitude': None,
                'turnover_rate': None,
                'source': 'tx'
            }
            records.append(record)
            prev_close = close_val
        except Exception as e:
            logger.warning(f"处理 tx 数据行失败: {e}")
            continue
    return records


def convert_to_db_format(df: pd.DataFrame, source: str, index_code: str, index_name: str) -> List[Dict]:
    """根据数据源类型转换为数据库格式"""
    if source == 'hist':
        return convert_hist_to_db_format(df, index_code, index_name)
    elif source == 'em':
        return convert_em_to_db_format(df, index_code, index_name)
    elif source == 'sina':
        return convert_sina_to_db_format(df, index_code, index_name)
    elif source == 'tx':
        return convert_tx_to_db_format(df, index_code, index_name)
    else:
        logger.error(f"未知数据源: {source}")
        return []


def save_records_to_db(records: List[Dict], index_code: str, batch_size: int = 500) -> Tuple[int, int]:
    """批量保存记录到数据库（全量更新模式：先删除旧数据，再插入新数据）"""
    if not records:
        return 0, 0

    try:
        deleted_count = IndexHistory.query.filter_by(index_code=index_code).delete()
        db.session.commit()
        logger.debug(f"已删除 {index_code} 的 {deleted_count} 条旧数据")

        objects_to_save = [IndexHistory(**record) for record in records]

        for i in range(0, len(objects_to_save), batch_size):
            batch = objects_to_save[i:i + batch_size]
            db.session.bulk_save_objects(batch)
            db.session.commit()

        return len(objects_to_save), deleted_count

    except Exception as e:
        db.session.rollback()
        logger.error(f"保存数据失败: {e}")
        return 0, 0


def sync_single_index(index_code: str, index_name: Optional[str] = None,
                      preferred_source: Optional[str] = None) -> bool:
    """同步单个指数的历史数据（全量更新，不限制日期）"""
    if index_name is None:
        index_name = BENCHMARK_INDICES.get(index_code, '未知指数')

    try:
        df, source = fetch_index_history(index_code, preferred_source)

        if df is None or df.empty:
            logger.warning(f"⚠️ {index_code} 未获取到数据")
            return False

        records = convert_to_db_format(df, source, index_code, index_name)

        if not records:
            logger.warning(f"⚠️ {index_code} 无有效记录可保存")
            return False

        inserted, deleted = save_records_to_db(records, index_code)

        logger.info(f"✅ {index_code} 全量更新完成: 新增 {inserted} 条, 删除 {deleted} 条旧数据 (来源: {source})")
        return True

    except Exception as e:
        logger.exception(f"❌ {index_code} 同步失败: {e}")
        return False


def sync_all_benchmark_indices(preferred_source: Optional[str] = None, delay: float = REQUEST_DELAY):
    """同步所有基准指数的历史数据（全量更新，不限制日期）"""
    indices = list(BENCHMARK_INDICES.items())
    total = len(indices)
    success_count = 0

    logger.info(f"开始全量同步 {total} 个基准指数的历史数据（不限制日期范围）...")

    for i, (code, name) in enumerate(indices, 1):
        logger.info(f"[{i}/{total}] 处理指数: {code} ({name})")

        if sync_single_index(code, name, preferred_source=preferred_source):
            success_count += 1

        if i < total:
            time.sleep(delay)

    logger.info(f"✅ 全部完成: {success_count}/{total} 个指数同步成功")


def daily_sync():
    """每日全量同步任务（不限制日期）"""
    logger.info("=" * 60)
    logger.info("开始每日全量同步 - 指数历史数据")
    logger.info("=" * 60)

    sync_all_benchmark_indices(preferred_source='em', delay=REQUEST_DELAY)

    logger.info("=" * 60)
    logger.info("每日全量同步完成")
    logger.info("=" * 60)


# 兼容性导出
fetch_and_save_index_history = sync_single_index
daily_incremental_sync = daily_sync

if __name__ == "__main__":
    from app import app

    with app.app_context():
        daily_sync()