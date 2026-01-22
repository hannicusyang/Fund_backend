# tasks/fund_history_to_mysql.py （优化版）

import akshare as ak
import pandas as pd
import time
import random
from datetime import datetime, date, timedelta
from config.logging_config import logger
from models import db
from models.fund_nav_history import FundNavHistory
from models.fund_list import FundList
from models.fund_watchlist import FundWatchlist
import sys

# =============== 使用 exchange_calendars 判断交易日 ===============
try:
    import exchange_calendars as ec
    # 中国上海证券交易所日历（A股）
    XSHG_CAL = ec.get_calendar("XSHG")
except ImportError:
    logger.error("未安装 exchange-calendars，请运行: pip install exchange-calendars")
    XSHG_CAL = None


def _get_latest_trading_day():
    """获取最近一个 A 股交易日（<= 今天）"""
    if XSHG_CAL is None:
        # 回退到自然日（不推荐）
        return date.today()

    today = pd.Timestamp(date.today())
    # 获取最近的交易日（含今天）
    latest = XSHG_CAL.previous_close(today).date()
    # 如果今天是交易日，则 previous_close 是昨天，需检查今天是否开盘
    if XSHG_CAL.is_session(today):
        latest = today.date()
    return latest


def _is_fund_up_to_date(fund_code: str) -> bool:
    """判断基金是否已包含最近交易日的净值"""
    try:
        latest_trade_day = _get_latest_trading_day()
    except Exception as e:
        logger.warning(f"获取交易日失败，跳过智能判断: {e}")
        return False  # 安全起见，允许抓取

    exists = db.session.query(FundNavHistory.nav_date).filter(
        FundNavHistory.fund_code == fund_code,
        FundNavHistory.nav_date >= latest_trade_day
    ).first()
    return exists is not None


# ========== 以下函数保持不变 ==========
def _get_fund_name(fund_code: str) -> str:
    try:
        fund = db.session.get(FundList, fund_code)
        return fund.fund_name if fund else fund_code
    except Exception as e:
        logger.warning(f"查询基金名称失败 {fund_code}: {e}")
        return fund_code


def _fetch_with_akshare(fund_code: str, max_retries: int = 2):
    for attempt in range(max_retries + 1):
        try:
            df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
            if df is None or df.empty:
                raise ValueError("akshare 返回空数据")

            df = df.rename(columns={
                '净值日期': 'nav_date',
                '单位净值': 'net_value',
                '日增长率': 'daily_growth_rate'
            })

            df['nav_date'] = pd.to_datetime(df['nav_date'], errors='coerce').dt.date
            df['net_value'] = pd.to_numeric(df['net_value'], errors='coerce')
            df['daily_growth_rate'] = (
                df['daily_growth_rate']
                .astype(str)
                .str.replace('%', '', regex=False)
                .str.strip()
                .replace(['---', '', 'None', 'nan'], pd.NA)
                .astype(float, errors='ignore')
            )
            df = df.dropna(subset=['nav_date'])
            return df.sort_values('nav_date').reset_index(drop=True)
        except Exception as e:
            error_msg = str(e).split('\n')[0][:150]
            if attempt < max_retries:
                wait_sec = random.uniform(1.0, 2.0)
                logger.warning(f"基金 {fund_code} 第 {attempt + 1} 次失败（{error_msg}），{wait_sec:.1f} 秒后重试...")
                time.sleep(wait_sec)
            else:
                logger.error(f"基金 {fund_code} 最终失败: {error_msg}")
                return None
    return None


def fetch_and_save_fund_history(fund_code: str, force_update: bool = False):
    """
    定时任务用：基于 exchange_calendars 的智能增量同步
    """
    fund_code = str(fund_code).strip()
    if not fund_code:
        return {
            "success": False,
            "message": "基金代码为空",
            "fund_code": fund_code,
            "fund_name": "",
            "record_count": 0,
            "exists": False
        }

    from app import app
    with app.app_context():
        # ====== 智能跳过：基于真实交易日历 ======
        if not force_update and _is_fund_up_to_date(fund_code):
            fund_name = _get_fund_name(fund_code)
            logger.info(f"基金 {fund_code} ({fund_name}) 数据已是最新（含最近交易日），跳过抓取")
            return {
                "success": True,
                "message": "数据已是最新（基于交易日历）",
                "fund_code": fund_code,
                "fund_name": fund_name,
                "record_count": 0,
                "exists": True
            }

        # ====== 抓取并插入新数据（逻辑不变）======
        df = _fetch_with_akshare(fund_code, max_retries=2)
        if df is None or df.empty:
            fund_name = _get_fund_name(fund_code)
            return {
                "success": False,
                "message": "akshare 未能获取有效历史数据",
                "fund_code": fund_code,
                "fund_name": fund_name,
                "record_count": 0,
                "exists": False
            }

        fund_name = _get_fund_name(fund_code)

        latest_in_db = db.session.query(
            db.func.max(FundNavHistory.nav_date)
        ).filter(FundNavHistory.fund_code == fund_code).scalar()

        if latest_in_db:
            df_new = df[df['nav_date'] > latest_in_db].copy()
        else:
            df_new = df.copy()

        if df_new.empty:
            return {
                "success": True,
                "message": "无新净值数据",
                "fund_code": fund_code,
                "fund_name": fund_name,
                "record_count": 0,
                "exists": True
            }

        records = []
        for _, row in df_new.iterrows():
            net_value = row['net_value'] if pd.notna(row['net_value']) else None
            daily_growth_rate = row['daily_growth_rate'] if pd.notna(row['daily_growth_rate']) else None
            record = FundNavHistory(
                fund_code=fund_code,
                fund_name=fund_name,
                nav_date=row['nav_date'],
                net_value=net_value,
                daily_growth_rate=daily_growth_rate,
                update_time=datetime.now()
            )
            records.append(record)

        try:
            db.session.bulk_save_objects(records)
            db.session.commit()
            record_count = len(records)
            logger.info(f"✅ 基金 {fund_code} ({fund_name}) 新增 {record_count} 条净值记录")
            return {
                "success": True,
                "message": f"成功新增 {record_count} 条记录",
                "fund_code": fund_code,
                "fund_name": fund_name,
                "record_count": record_count,
                "exists": False
            }
        except Exception as e:
            db.session.rollback()
            error_msg = str(e)[:200]
            logger.error(f"写入数据库失败 {fund_code}: {error_msg}")
            return {
                "success": False,
                "message": f"写入数据库失败: {error_msg}",
                "fund_code": fund_code,
                "fund_name": fund_name,
                "record_count": 0,
                "exists": False
            }


# ========== 新增：同步所有自选基金的历史净值 ==========
def sync_all_watched_funds(force_update: bool = False):
    """
    获取 fund_watchlist 表中所有基金，并同步其历史净值到 fund_nav_history
    :param force_update: 是否强制更新（忽略“已是最新”判断）
    """
    from app import app
    with app.app_context():
        try:
            # 查询所有自选基金代码（去重）
            watched_funds = db.session.query(FundWatchlist.fund_code).distinct().all()
            fund_codes = [f[0] for f in watched_funds]

            if not fund_codes:
                logger.info("观察清单为空，无需同步")
                return {"success": True, "message": "观察清单为空", "total": 0, "updated": 0}

            logger.info(f"开始同步 {len(fund_codes)} 只自选基金的历史净值...")
            updated_count = 0

            for i, fund_code in enumerate(fund_codes, 1):
                logger.info(f"[{i}/{len(fund_codes)}] 正在处理基金: {fund_code}")
                result = fetch_and_save_fund_history(fund_code, force_update=force_update)
                if result["success"] and result["record_count"] > 0:
                    updated_count += 1

            logger.info(f"✅ 自选基金历史净值同步完成！共 {len(fund_codes)} 只，新增数据 {updated_count} 只")
            return {
                "success": True,
                "message": "自选基金同步完成",
                "total": len(fund_codes),
                "updated": updated_count
            }

        except Exception as e:
            error_msg = str(e)[:200]
            logger.error(f"同步自选基金失败: {error_msg}")
            return {
                "success": False,
                "message": f"同步失败: {error_msg}",
                "total": 0,
                "updated": 0
            }


if __name__ == "__main__":
    success = sync_all_watched_funds()
    sys.exit(0 if success else 1)