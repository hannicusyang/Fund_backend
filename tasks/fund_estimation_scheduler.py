# tasks/fund_estimation_scheduler.py
import pandas as pd
import re
import akshare as ak
from datetime import datetime, date
from config.logging_config import logger
from models import db
from models.fund_estimation import FundEstimation
from models.trading_day import TradingDay
import math  # ← 新增：用于判断 NaN
from datetime import datetime, time, timedelta
import pandas_market_calendars as mcal


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
    try:
        objects = [FundEstimation(**rec) for rec in records]
        db.session.bulk_save_objects(objects)
        db.session.commit()
        logger.info(f"✅ 写入 {len(records)} 条数据 | 估算日: {t_date}")
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
            save_estimation_to_mysql(df)

    except Exception as e:
        logger.error(f"💥 抓取失败: {e}", exc_info=True)