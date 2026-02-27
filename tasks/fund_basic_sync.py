# tasks/fund_basic_sync.py
from datetime import datetime, timezone

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

import logging
# 导入tushare
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.tushare_api import get_pro

from config.logging_config import logger
from models import db
from models.fund_list import FundList


def fetch_fund_data():
    """从东方财富网获取基金基本信息"""
    logger.info("正在从东方财富网获取基金基本信息...")
    try:
        df = ak.fund_name_em()
    except Exception as e:
        logger.error(f"获取基金数据失败: {e}")
        raise

    required_columns = ['基金代码', '拼音缩写', '基金简称', '基金类型', '拼音全称']
    if not all(col in df.columns for col in required_columns):
        raise ValueError("返回数据缺少必要字段")

    # 清洗数据
    df = df[required_columns].rename(columns={
        '基金代码': 'fund_code',
        '拼音缩写': 'pinyin_abbr',
        '基金简称': 'fund_name',
        '基金类型': 'fund_type',
        '拼音全称': 'pinyin_full'
    })
    df = df.dropna(subset=['fund_code']).reset_index(drop=True)
    logger.info(f"成功获取 {len(df)} 条基金数据。")
    return df


def sync_fund_basic_info():
    try:
        from app import app
        with app.app_context():
            df = fetch_fund_data()

            # 清空表
            db.session.execute(db.delete(FundList))
            db.session.commit()

            # 获取当前 UTC 时间（用于所有记录）
            current_time = datetime.now(timezone.utc)  # ← 关键：统一时间戳

            records = []
            for _, row in df.iterrows():
                record = FundList(
                    fund_code=row['fund_code'],
                    pinyin_abbr=row['pinyin_abbr'],
                    fund_name=row['fund_name'],
                    fund_type=row['fund_type'],
                    pinyin_full=row['pinyin_full'],
                    update_time=current_time  # ← 显式赋值！
                )
                records.append(record)

            db.session.bulk_save_objects(records)
            db.session.commit()
            logger.info(f"✅ 基金基础信息同步完成，共写入 {len(records)} 条记录。")
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ 基金基础信息同步失败: {e}", exc_info=True)
        raise