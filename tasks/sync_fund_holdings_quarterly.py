# tasks/sync_fund_holdings_quarterly.py

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
import time
from models.fund_basic import FundBasic
from services.fund_holdings_service import fetch_and_save_fund_holdings
from config import logger

def sync_all_fund_holdings_quarterly():
    """
    此函数必须在 Flask app context 中运行！
    """
    current_year = datetime.now().year
    years_to_fetch = [str(current_year), str(current_year - 1)]

    funds = FundBasic.query.with_entities(FundBasic.fund_code).all()
    total = len(funds)
    logger.info(f"开始同步 {total} 只基金的持仓数据...")

    for i, fund in enumerate(funds, 1):
        fund_code = fund.fund_code
        logger.info(f"[{i}/{total}] 处理基金: {fund_code}")
        for year in years_to_fetch:
            fetch_and_save_fund_holdings(fund_code, year)
            time.sleep(0.8)

    logger.info("✅ 持仓数据同步完成！")

if __name__ == "__main__":
    # 独立运行时手动创建上下文
    from app import app
    with app.app_context():
        sync_all_fund_holdings_quarterly()