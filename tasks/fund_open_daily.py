# tasks/fund_open_daily.py

import akshare as ak
import pandas as pd
import sys
import math
from datetime import datetime
from config.logging_config import logger
from models import db
from sqlalchemy import text


def fund_open_synchronization():
    SYMBOL = "全部"

    from app import app
    with app.app_context():
        try:
            logger.info(f"开始获取 {SYMBOL} 开放式基金排行榜...")
            df = ak.fund_open_fund_rank_em(symbol=SYMBOL)
        except Exception as e:
            logger.error(f"❌ akshare 请求失败: {e}")
            return False

        if df is None or df.empty or len(df) < 100:
            logger.error("❌ 数据为空或过少，拒绝更新排行表！")
            return False

        # === 1. 列重命名（18列，含日期）===
        column_mapping = {
            '序号': 'rank',
            '基金代码': 'fund_code',
            '基金简称': 'fund_name',
            '日期': 'date',  # ← 关键：保留日期
            '单位净值': 'net_value',
            '累计净值': 'accumulated_net_value',
            '日增长率': 'daily_growth_rate',
            '近1周': 'weekly_growth_rate',
            '近1月': 'monthly_1_growth_rate',
            '近3月': 'monthly_3_growth_rate',
            '近6月': 'monthly_6_growth_rate',
            '近1年': 'yearly_1_growth_rate',
            '近2年': 'yearly_2_growth_rate',
            '近3年': 'yearly_3_growth_rate',
            '今年来': 'ytd_growth_rate',
            '成立来': 'since_inception_growth_rate',
            '自定义': 'custom_growth_rate',
            '手续费': 'fee_rate'
        }
        df = df.rename(columns=column_mapping)[list(column_mapping.values())]

        # === 2. 处理百分比字段（不含 date 和 code/name）===
        pct_cols = [
            'daily_growth_rate', 'weekly_growth_rate', 'monthly_1_growth_rate',
            'monthly_3_growth_rate', 'monthly_6_growth_rate', 'yearly_1_growth_rate',
            'yearly_2_growth_rate', 'yearly_3_growth_rate', 'ytd_growth_rate',
            'since_inception_growth_rate', 'custom_growth_rate', 'fee_rate'
        ]
        for col in pct_cols:
            if col in df.columns:
                df[col] = (
                    df[col].astype(str)
                    .str.replace('%', '', regex=False)
                    .str.strip()
                    .replace(['', '---', 'nan', 'None', '-', '--', 'null'], pd.NA)
                )

        # === 3. 数值转换 ===
        numeric_cols = [
            'rank', 'net_value', 'accumulated_net_value',
            'daily_growth_rate', 'weekly_growth_rate', 'monthly_1_growth_rate',
            'monthly_3_growth_rate', 'monthly_6_growth_rate', 'yearly_1_growth_rate',
            'yearly_2_growth_rate', 'yearly_3_growth_rate', 'ytd_growth_rate',
            'since_inception_growth_rate', 'custom_growth_rate', 'fee_rate'
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # === 4. 字符串字段（含 date）===
        df['fund_code'] = df['fund_code'].astype(str).str.strip()
        df['fund_name'] = df['fund_name'].astype(str).str.strip()
        df['date'] = df['date'].astype(str).str.strip()  # 如 '01-13'

        # === 5. 固定字段 ===
        df['is_checked'] = False
        df['update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # === 6. 转字典 + 彻底清除 nan ===
        records = df.to_dict(orient='records')

        def replace_nan_with_none(obj):
            if isinstance(obj, dict):
                return {k: replace_nan_with_none(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_nan_with_none(item) for item in obj]
            elif isinstance(obj, float) and math.isnan(obj):
                return None
            else:
                return obj

        records = [replace_nan_with_none(r) for r in records]

        # === 7. 批量写入（SQL 需包含 date 字段）===
        try:
            db.session.execute(text("DELETE FROM fund_open_rank_all"))
            db.session.execute(
                text("""
                     INSERT INTO fund_open_rank_all (`rank`, `fund_code`, `fund_name`, `date`,
                                                     `net_value`, `accumulated_net_value`,
                                                     `daily_growth_rate`, `weekly_growth_rate`,
                                                     `monthly_1_growth_rate`, `monthly_3_growth_rate`,
                                                     `monthly_6_growth_rate`, `yearly_1_growth_rate`,
                                                     `yearly_2_growth_rate`, `yearly_3_growth_rate`,
                                                     `ytd_growth_rate`, `since_inception_growth_rate`,
                                                     `custom_growth_rate`, `fee_rate`,
                                                     `is_checked`, `update_time`)
                     VALUES (:rank, :fund_code, :fund_name, :date,
                             :net_value, :accumulated_net_value,
                             :daily_growth_rate, :weekly_growth_rate,
                             :monthly_1_growth_rate, :monthly_3_growth_rate,
                             :monthly_6_growth_rate, :yearly_1_growth_rate,
                             :yearly_2_growth_rate, :yearly_3_growth_rate,
                             :ytd_growth_rate, :since_inception_growth_rate,
                             :custom_growth_rate, :fee_rate,
                             :is_checked, :update_time)
                     """),
                records
            )
            db.session.commit()
            logger.info(f"✅ 成功更新基金排行榜，共 {len(records)} 条记录（含日期字段）")
            return True

        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ 批量写入失败: {e}")
            return False


if __name__ == "__main__":
    success = fund_open_synchronization()
    sys.exit(0 if success else 1)