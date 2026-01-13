# services/fund_holdings_service.py

from models.fund_holding import FundHolding  # 假设模型在此
from .fund_holdings_fetcher import fetch_fund_holdings
from models import db
import logging

logger = logging.getLogger(__name__)

def fetch_and_save_fund_holdings(fund_code: str, year: str):
    """
    业务层：查 DB → 决定是否抓 → 存 DB
    """
    if not fund_code or not (year.isdigit() and len(year) == 4):
        return {"success": False, "message": "参数错误"}

    # 可选：检查该基金该年是否已有任意季度数据（避免全量重复抓）
    existing_any = FundHolding.query.filter(
        FundHolding.fund_code == fund_code,
        FundHolding.quarter.like(f"{year}Q%")
    ).first()
    if existing_any:
        return {"success": True, "message": "该年数据已存在", "data": []}

    # 调用统一抓取器
    result = fetch_fund_holdings(fund_code, year)
    if not result["success"]:
        return result

    saved_count = 0
    for rec in result["data"]:
        # 补充 fund_code
        rec['fund_code'] = fund_code

        # 防重：同一基金+股票+季度
        exists = FundHolding.query.filter_by(
            fund_code=fund_code,
            stock_code=rec['stock_code'],
            quarter=rec['quarter']
        ).first()

        if not exists:
            holding = FundHolding(**rec)
            db.session.add(holding)
            saved_count += 1

    try:
        db.session.commit()
        logger.info(f"✅ 基金 {fund_code} 年份 {year} 保存 {saved_count} 条持仓")
        return {"success": True, "message": f"保存 {saved_count} 条", "data": result["data"]}
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ 保存失败: {e}")
        return {"success": False, "message": str(e), "data": []}