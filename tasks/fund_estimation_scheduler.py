# tasks/fund_estimation_scheduler.py
import pandas as pd
# 导入tushare
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.tushare_api import get_pro

import re
# 导入tushare
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.tushare_api import get_pro

import akshare as ak
# 导入tushare
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.tushare_api import get_pro

from datetime import datetime, date
from config.logging_config import logger
from models import db
from models.fund_estimation import FundEstimation
from models.fund_watchlist import FundWatchlist
from models.trading_day import TradingDay
from models.my_fund_holding import MyFundHolding
import math  # ← 新增：用于判断 NaN
# 导入tushare
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.tushare_api import get_pro

from datetime import datetime, time, timedelta
import pandas_market_calendars as mcal
# 导入tushare
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.tushare_api import get_pro

import json  # ✅ 新增：用于 JSON 序列化
# 导入tushare
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.tushare_api import get_pro

import time as time_module
# 导入tushare
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.tushare_api import get_pro


_redis_client = None

def get_redis_client():
    """惰性获取 Redis 客户端"""
    global _redis_client
    if _redis_client is None:
        try:
            from models.redis_client import get_redis_client as _get_redis_client
            _redis_client = _get_redis_client()
        except Exception as e:
            logger.warning(f"Redis client not available: {e}")
            _redis_client = None
    return _redis_client

def sync_trading_days():
    """从 AKShare 同步交易日历到数据库（幂等操作）"""
    try:
        # 检查是否已有数据
        if db.session.query(TradingDay).first() is not None:
            logger.debug("📅 交易日历已存在，跳过同步")
            return

        logger.info("🔄 正在从 AKShare 同步交易日历...")
        df = ak.tool_trade_date_hist_sina()
        dates_to_insert = [
            TradingDay(trade_date=pd.to_datetime(row['trade_date']).date())
            for _, row in df.iterrows()
        ]
        db.session.bulk_save_objects(dates_to_insert)
        db.session.commit()
        logger.info(f"✅ 成功同步 {len(dates_to_insert)} 个交易日到数据库")
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ 同步交易日历失败: {e}")

def is_a_stock_trading_time():
    """判断当前是否为 A 股交易时间（查数据库 + 时间段检查）"""
    now = datetime.now()
    today = now.date()
    current_time = now.time()

    # 检查交易时段
    if not (time(9, 30) <= current_time <= time(15, 0)):
        return False

    # 查数据库
    try:
        exists = db.session.query(
            db.exists().where(TradingDay.trade_date == today)
        ).scalar()
        return bool(exists)
    except Exception as e:
        logger.error(f"❌ 查询交易日失败: {e}")
        return False  # 安全起见返回 False


def calculate_and_save_portfolio_realtime_summary():
    """
    计算当天实时投资组合汇总数据并保存到 Redis（仅保留当天数据）
    在每次抓取基金估值后调用
    """
    redis_client = get_redis_client()
    if not redis_client:
        logger.debug("Redis client not available, skipping portfolio summary calculation")
        return

    try:
        # 获取用户当前有效持仓（shares > 0）
        holdings = MyFundHolding.query.filter(
            MyFundHolding.user_id == 'default',
            MyFundHolding.shares > 0
        ).all()

        if not holdings:
            logger.debug("No active holdings found, skipping portfolio summary")
            return

        total_asset = 0.0
        total_cost = 0.0
        calculation_time = datetime.now()
        estimation_time_str = calculation_time.isoformat()

        # 为每个持仓获取最新估值并计算
        for holding in holdings:
            fund_code = holding.fund_code
            estimation_data = get_fund_estimation_from_redis_for_calculation(fund_code)

            current_nav = estimation_data['estimated_nav'] if estimation_data else None

            if current_nav is not None and holding.shares > 0:
                shares_f = float(holding.shares)
                cost_price_f = float(holding.cost_price) if holding.cost_price else 0.0

                current_value = current_nav * shares_f
                holding_cost = cost_price_f * shares_f

                total_asset += current_value
                total_cost += holding_cost

        # 计算收益和收益率
        if total_cost <= 0:
            total_profit = 0.0
            total_profit_rate = 0.0
        else:
            total_profit = total_asset - total_cost
            total_profit_rate = (total_profit / total_cost) * 100

        # 准备要保存的数据
        portfolio_summary = {
            "estimated_total_asset": round(total_asset, 2),
            "estimated_total_profit": round(total_profit, 2),
            "estimated_total_profit_rate": round(total_profit_rate, 2),
            "update_time": estimation_time_str,
            "calculation_time": estimation_time_str
        }

        # ✅ 只保存当天的数据到 Redis
        save_portfolio_summary_today(portfolio_summary, calculation_time)

        logger.info(f"✅ 当天实时投资组合汇总已保存 | 总资产: ¥{total_asset:.2f}")

    except Exception as e:
        logger.error(f"❌ 计算并保存当天实时投资组合汇总失败: {e}")


def save_portfolio_summary_today(summary_data, timestamp):
    """
    将当天的投资组合汇总数据保存到 Redis
    使用日期作为 key 的一部分，自动按天分组
    """
    redis_client = get_redis_client()
    if not redis_client:
        return

    try:
        # 使用日期作为 key，例如：portfolio_summary_2026-01-21
        date_str = timestamp.strftime("%Y-%m-%d")
        redis_key = f"portfolio_summary_{date_str}"
        member = json.dumps(summary_data, separators=(',', ':'))
        score = timestamp.timestamp()

        # 添加到当天的 sorted set
        redis_client.zadd(redis_key, {member: score})

        # 设置过期时间（7天，足够覆盖一周的数据）
        redis_client.expire(redis_key, 7 * 24 * 3600)

    except Exception as e:
        logger.error(f"保存当天投资组合汇总到 Redis 失败: {e}")

def save_portfolio_summary_to_redis_timeseries(summary_data, timestamp):
    """
    将投资组合汇总数据保存到 Redis 时间序列
    使用 sorted set，score 为时间戳，member 为 JSON 数据
    """
    redis_client = get_redis_client()
    if not redis_client:
        return

    try:
        redis_key = "portfolio_summary_ts"
        member = json.dumps(summary_data, separators=(',', ':'))
        score = timestamp.timestamp()  # 使用 Unix 时间戳作为 score

        # 添加到 sorted set
        redis_client.zadd(redis_key, {member: score})

        # 清理旧数据（保留最近7天的数据，假设每分钟一条，7*24*60=10080条）
        # 或者保留最近10000条记录
        current_count = redis_client.zcard(redis_key)
        if current_count > 10000:
            # 删除最旧的记录，保留最新的10000条
            redis_client.zremrangebyrank(redis_key, 0, current_count - 10000 - 1)

        # 设置过期时间（30天）
        redis_client.expire(redis_key, 30 * 24 * 3600)

    except Exception as e:
        logger.error(f"保存投资组合汇总到 Redis 时间序列失败: {e}")


# 在文件适当位置添加
def get_fund_estimation_from_redis_for_calculation(fund_code):
    """专门为计算汇总数据优化的 Redis 读取函数"""
    redis_client = get_redis_client()
    if not redis_client:
        return None
    try:
        redis_key = f"fund_ts:{fund_code}"
        result = redis_client.zrevrange(redis_key, 0, 0, withscores=True)
        if not result:
            return None
        member, timestamp = result[0]
        data = json.loads(member)

        def parse_float_value(value):
            if value == '' or value is None:
                return None
            try:
                return float(value)
            except (ValueError, TypeError):
                return None

        estimation_date_str = data.get('estimation_date', '')
        net_value_date = None
        if estimation_date_str:
            try:
                net_value_date = datetime.strptime(estimation_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        return {
            'estimated_nav': parse_float_value(data.get('estimated_nav')),
            'daily_growth_rate': parse_float_value(data.get('estimated_growth_rate')),
            'net_value_date': net_value_date,
            'last_nav': parse_float_value(data.get('last_nav'))
        }
    except Exception as e:
        logger.warning(f"从 Redis 获取基金估值失败 {fund_code}: {e}")
        return None

def clear_old_estimation_data(batch_size=5000):
    """
    清理逻辑：只保留 fetch_time 日期 = 今天的记录
    （允许同一只基金同一天有多条，只要是在今天抓取的）
    """
    from datetime import date
    today = date.today()
    total_deleted = 0

    try:
        while True:
            ids = db.session.query(FundEstimation.id).filter(
                db.func.date(FundEstimation.fetch_time) != today
            ).limit(batch_size).all()

            if not ids:
                break

            id_list = [row.id for row in ids]
            deleted = FundEstimation.query.filter(FundEstimation.id.in_(id_list)).delete(synchronize_session=False)
            db.session.commit()
            total_deleted += deleted
            logger.debug(f"🧹 删除 {deleted} 条非今日抓取数据（累计 {total_deleted}）")

        if total_deleted > 0:
            logger.info(f"✅ 清理完成：共删除 {total_deleted} 条旧抓取数据")
        else:
            logger.debug("✅ 无旧抓取数据需要清理")

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ 清理失败: {e}")


def save_fund_estimation_to_redis(records, estimation_date):
    """
    将属于 watchlist 的基金估值数据存入 Redis
    """
    redis_client = get_redis_client()  # 惰性获取
    if not redis_client:
        logger.debug("Redis client not available, skipping Redis storage")
        return

    try:
        # 获取所有 watchlist 中的基金代码
        watchlist_funds = db.session.query(FundWatchlist.fund_code).all()
        watchlist_codes = {fund.fund_code for fund in watchlist_funds}

        stored_count = 0
        # 只存储在 watchlist 中的基金
        for record in records:
            fund_code = record.get('fund_code')
            if fund_code in watchlist_codes:

                # 准备要存储的数据
                redis_data = {
                    'fund_code': fund_code,
                    'fund_name': record.get('fund_name', ''),
                    'estimation_date': str(estimation_date) if estimation_date else '',
                    'last_nav_date': str(record.get('last_nav_date', '')) if record.get('last_nav_date') else '',
                    'estimated_nav': str(record.get('estimated_nav', '')) if record.get(
                        'estimated_nav') is not None else '',
                    'estimated_growth_rate': str(record.get('estimated_growth_rate', '')) if record.get(
                        'estimated_growth_rate') is not None else '',
                    'published_nav': str(record.get('published_nav', '')) if record.get(
                        'published_nav') is not None else '',
                    'published_growth_rate': str(record.get('published_growth_rate', '')) if record.get(
                        'published_growth_rate') is not None else '',
                    'estimation_bias': str(record.get('estimation_bias', '')) if record.get(
                        'estimation_bias') is not None else '',
                    'last_nav': str(record.get('last_nav', '')) if record.get('last_nav') is not None else '',
                    'fetch_time': str(record.get('fetch_time', '')) if record.get('fetch_time') else ''
                }
                import time
                timestamp = int(time.time())

                # 序列化为 JSON 字符串（保持数据内容不变）
                data_json = json.dumps(redis_data, separators=(',', ':'))

                # 使用新的 key 格式：fund_ts:{fund_code}
                redis_key = f"fund_ts:{fund_code}"

                # 存储到 Sorted Set
                redis_client.zadd(redis_key, {data_json: timestamp})

                # 设置过期时间为 7 天（时间序列需要更长保留时间）
                redis_client.expire(redis_key, 7 * 24 * 3600)

                stored_count += 1

        if stored_count > 0:
            logger.info(f"✅ 已将 {stored_count} 个 watchlist 基金估值数据存入 Redis")
        else:
            logger.debug("🔍 无 watchlist 基金需要存入 Redis")
    except Exception as e:
        logger.error(f"❌ 存储到 Redis 失败: {e}")

def save_estimation_to_mysql(df: pd.DataFrame):
    if df.empty:
        logger.info("无估值数据，跳过写入")
        return

    # === 列名解析逻辑（保持不变）===
    df.columns = df.columns.astype(str)
    date_columns = {}
    for col in df.columns:
        match = re.search(r'(\d{4}-\d{2}-\d{2})', col)
        if match:
            d = match.group(1)
            date_columns.setdefault(d, []).append(col)

    if not date_columns:
        logger.error("无法从列名中提取日期")
        return

    t_date = None
    t_minus_1_date = None
    for d, cols in date_columns.items():
        if any('估算数据' in c for c in cols):
            t_date = d
            break
    for d, cols in date_columns.items():
        if any('单位净值' in c and '公布数据' not in c for c in cols):
            t_minus_1_date = d
            break
    if t_minus_1_date is None and len(date_columns) > 1:
        sorted_dates = sorted(date_columns.keys())
        t_minus_1_date = sorted_dates[0]

    # === 构建记录列表 ===
    records = []
    for _, row in df.iterrows():
        new_record = {
            'fund_code': str(row['基金代码']),
            'fund_name': row['基金名称'],
            'estimation_date': datetime.strptime(t_date, "%Y-%m-%d").date() if t_date else None,
            'last_nav_date': datetime.strptime(t_minus_1_date, "%Y-%m-%d").date() if t_minus_1_date else None,
            'estimation_bias': None,
            'fetch_time': datetime.now()
        }

        if t_date:
            new_record['estimated_nav'] = pd.to_numeric(row.get(f'{t_date}-估算数据-估算值'), errors='coerce')
            new_record['estimated_growth_rate'] = pd.to_numeric(
                str(row.get(f'{t_date}-估算数据-估算增长率', '')).replace('%', ''), errors='coerce'
            )
            new_record['published_nav'] = pd.to_numeric(row.get(f'{t_date}-公布数据-单位净值'), errors='coerce')
            new_record['published_growth_rate'] = pd.to_numeric(
                str(row.get(f'{t_date}-公布数据-日增长率', '')).replace('%', ''), errors='coerce'
            )

        if t_minus_1_date:
            last_nav_col = f'{t_minus_1_date}-单位净值'
            if last_nav_col in df.columns:
                new_record['last_nav'] = pd.to_numeric(row[last_nav_col], errors='coerce')
            else:
                for col in df.columns:
                    if '单位净值' in col and '公布数据' not in col and col not in ['基金代码', '基金名称', '估算偏差']:
                        new_record['last_nav'] = pd.to_numeric(row[col], errors='coerce')
                        break

        if '估算偏差' in row and pd.notna(row['估算偏差']):
            new_record['estimation_bias'] = pd.to_numeric(
                str(row['估算偏差']).replace('%', ''), errors='coerce'
            )

        # ✅ 关键修复：将所有 NaN 值替换为 None
        for key, value in new_record.items():
            if isinstance(value, float) and math.isnan(value):
                new_record[key] = None

        records.append(new_record)

    # === 批量插入 ===
    batch_size = 2000
    total_records = len(records)

    try:
        for i in range(0, total_records, batch_size):
            batch = records[i:i + batch_size]
            objects = [FundEstimation(**rec) for rec in batch]
            db.session.bulk_save_objects(objects)
            db.session.commit()
            logger.debug(f"已写入批次 {i // batch_size + 1}/{(total_records - 1) // batch_size + 1}")

        logger.info(f"✅ 完成写入 {total_records} 条数据 | 估算日: {t_date}")

        # ✅ 新增：将 watchlist 基金数据存入 Redis
        if t_date:
            save_fund_estimation_to_redis(records, t_date)

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ 写入失败: {e}")


def fetch_and_save_fund_estimation(is_debug=False):
    """主抓取函数"""
    try:
        from app import app  # 确保能导入 app 实例
        with app.app_context():
            # ✅ 所有逻辑（包括判断是否交易时间）都放在这里！
            if not is_debug and not is_a_stock_trading_time():
                logger.debug("非 A 股交易时间，跳过抓取")
                return

            sync_trading_days()
            clear_old_estimation_data()
            logger.info("📡 开始抓取基金估值...")
            df = ak.fund_value_estimation_em(symbol="全部")

            # ✅ 先保存数据（包含 Redis 存储）
            save_estimation_to_mysql(df)

            # ✅ 然后计算汇总（现在 Redis 中已经有数据了）
            calculate_and_save_portfolio_realtime_summary()

    except Exception as e:
        logger.error(f"💥 抓取失败: {e}", exc_info=True)