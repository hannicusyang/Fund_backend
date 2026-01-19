# tasks/sync_fund_holdings_quarterly.py
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
import time
from models.fund_watchlist import FundWatchlist  # ← 新增导入
from services.fund_holdings_service import fetch_and_save_fund_holdings
from config import logger


def sync_watchlist_fund_holdings_quarterly():
    """
    同步【观察清单】中所有基金的季度持仓数据。
    此函数必须在 Flask app context 中运行！
    """
    current_year = datetime.now().year
    years_to_fetch = [str(current_year), str(current_year - 1)]

    # ← 关键修改：从 fund_watchlist 表获取基金代码（去重）
    watchlist_funds = (
        FundWatchlist.query
        .with_entities(FundWatchlist.fund_code)
        .distinct()  # 避免重复基金（虽然有唯一约束，但保险起见）
        .all()
    )

    fund_codes = [f.fund_code for f in watchlist_funds]
    total = len(fund_codes)

    if total == 0:
        logger.info("⚠️ 观察清单为空，跳过持仓同步。")
        return

    logger.info(f"开始同步 {total} 只【自选清单】基金的持仓数据...")

    for i, fund_code in enumerate(fund_codes, 1):
        logger.info(f"[{i}/{total}] 处理基金: {fund_code}")
        for year in years_to_fetch:
            fetch_and_save_fund_holdings(fund_code, year)
        time.sleep(0.8)  # 避免请求过快

    logger.info("✅ 【自选清单】基金持仓数据同步完成！")


if __name__ == "__main__":
    # 独立运行时手动创建上下文
    from app import app
    with app.app_context():
        sync_watchlist_fund_holdings_quarterly()