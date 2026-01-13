# tasks/fund_estimation_scheduler.py
import pandas as pd
import re
import akshare as ak
from datetime import datetime, date
from config.logging_config import logger
from models import db
from models.fund_estimation import FundEstimation
import math  # ← 新增：用于判断 NaN


def is_a_stock_trading_time():
    """判断当前是否为 A 股交易时间（9:30-15:00 且为交易日）"""
    try:
        import exchange_calendars as tc
        calendar = tc.get_calendar("XSHG")
    except ImportError:
        logger.warning("未安装 exchange-calendars，跳过交易日检查")
        return True  # 默认允许抓取

    now = datetime.now()
    today = now.date()
    current_time = now.time()

    if not calendar.is_session(today):
        return False

    market_open = datetime.strptime("09:30", "%H:%M").time()
    market_close = datetime.strptime("15:00", "%H:%M").time()
    return market_open <= current_time <= market_close

def clear_old_estimation_data():
    """清空 fund_estimation 表中非今天的数据"""
    today = date.today()
    try:
        deleted_count = FundEstimation.query.filter(
            FundEstimation.estimation_date != today
        ).delete()
        db.session.commit()
        if deleted_count > 0:
            logger.info(f"🧹 已清理 {deleted_count} 条非今日的旧数据")
        else:
            logger.debug("✅ 无旧数据需要清理")
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ 清理旧数据失败: {e}")


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
    if not is_debug and not is_a_stock_trading_time():
        logger.debug("非交易时间，跳过")
        return

    try:
        # 进入 Flask 应用上下文（关键！）
        from app import app  # ← 关键：导入全局 app
        with app.app_context():
            clear_old_estimation_data()
            logger.info("📡 开始抓取基金估值...")
            df = ak.fund_value_estimation_em(symbol="全部")
            save_estimation_to_mysql(df)
    except Exception as e:
        logger.error(f"💥 抓取失败: {e}", exc_info=True)