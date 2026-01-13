import akshare as ak
import pandas as pd
from sqlalchemy import create_engine, text
import time
import random
import logging
from config.mysql_config import *
from config.logging_config import logger


HISTORY_TABLE = "fund_nav_history"
BASIC_TABLE = "fund_basic_info"



# 全局数据库引擎（可复用）
engine = create_engine(DB_URL, echo=False, pool_pre_ping=True)


def ensure_history_table_exists():
    """确保历史净值表存在"""
    create_sql = f"""
        CREATE TABLE IF NOT EXISTS fund_nav_history (
            fund_code VARCHAR(20) NOT NULL COMMENT '基金代码',
            fund_name VARCHAR(255) NOT NULL COMMENT '基金简称',
            nav_date DATE NOT NULL COMMENT '净值日期',
            net_value DECIMAL(18,6) COMMENT '单位净值',
            daily_growth_rate DECIMAL(10,4) COMMENT '日增长率 (%)',
            update_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据更新时间',
            PRIMARY KEY (fund_code(20), nav_date),
            INDEX idx_fund_code (fund_code(20)),
            INDEX idx_nav_date (nav_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    with engine.connect() as conn:
        conn.execute(text(create_sql))
        conn.commit()


def _get_fund_name(fund_code: str) -> str:
    """从 fund_basic_info 表获取基金名称，若无则返回代码本身"""
    try:
        query = text(f"SELECT fund_name FROM {BASIC_TABLE} WHERE fund_code = :code")
        with engine.connect() as conn:
            result = conn.execute(query, {"code": fund_code}).fetchone()
            return result[0] if result else fund_code
    except Exception as e:
        logger.warning(f"查询基金名称失败 {fund_code}: {e}")
        return fund_code


def _fetch_with_akshare(fund_code: str, max_retries: int = 2):
    """使用 akshare 抓取，带重试"""
    for attempt in range(max_retries + 1):
        try:
            df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
            if df is None or df.empty:
                raise ValueError("akshare 返回空数据")

            # 列重命名
            df = df.rename(columns={
                '净值日期': 'nav_date',
                '单位净值': 'net_value',
                '日增长率': 'daily_growth_rate'
            })

            # 数据清洗
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
            if not df.empty:
                return df

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
    使用 akshare 按需抓取并保存单只基金的历史净值

    Args:
        fund_code (str): 基金代码，如 "000013"
        force_update (bool): 是否强制重新抓取（即使已有数据）

    Returns:
        dict: 包含 success, message, fund_code, fund_name, record_count, exists 等字段
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

    # 检查是否已存在（除非强制更新）
    if not force_update:
        check_sql = text(f"SELECT 1 FROM {HISTORY_TABLE} WHERE fund_code = :code LIMIT 1")
        with engine.connect() as conn:
            exists = conn.execute(check_sql, {"code": fund_code}).fetchone()
            if exists:
                fund_name = _get_fund_name(fund_code)
                return {
                    "success": True,
                    "message": "数据已存在，跳过抓取",
                    "fund_code": fund_code,
                    "fund_name": fund_name,
                    "record_count": 0,
                    "exists": True
                }

    # 使用 akshare 抓取
    df = _fetch_with_akshare(fund_code, max_retries=2)
    if df is None or df.empty:
        fund_name = _get_fund_name(fund_code)
        return {
            "success": False,
            "message": "akshare 未能获取有效历史数据（可能被限流或接口变更）",
            "fund_code": fund_code,
            "fund_name": fund_name,
            "record_count": 0,
            "exists": False
        }

    # 获取基金名称
    fund_name = _get_fund_name(fund_code)

    # 添加元字段
    df['fund_code'] = fund_code
    df['fund_name'] = fund_name
    df['update_time'] = pd.Timestamp.now()

    # 写入数据库
    try:
        df.to_sql(
            name=HISTORY_TABLE,
            con=engine,
            if_exists='append',
            index=False,
            method='multi',
            chunksize=500
        )
        record_count = len(df)
        logger.info(f"✅ 基金 {fund_code} ({fund_name}) 成功保存 {record_count} 条历史数据")
        return {
            "success": True,
            "message": f"成功保存 {record_count} 条记录",
            "fund_code": fund_code,
            "fund_name": fund_name,
            "record_count": record_count,
            "exists": False
        }
    except Exception as e:
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


if __name__ == '__main__':
    fetch_and_save_fund_history(fund_code="000006", force_update=True)