# services/fund_holdings_service.py
import akshare as ak
import pandas as pd
from datetime import datetime
from models.fund_holding import FundHolding
from services.fund_holdings_fetcher import parse_quarter_from_text

def get_holdings_from_db(fund_code: str, year: str):
    quarters = [f"{year}Q1", f"{year}Q2", f"{year}Q3", f"{year}Q4"]
    holdings = FundHolding.query.filter(
        FundHolding.fund_code == fund_code,
        FundHolding.quarter.in_(quarters)
    ).all()
    return [h.to_dict() for h in holdings]

def fetch_and_save_fund_holdings(fund_code: str, year: str):
    fund_code = fund_code.strip()
    year = year.strip()
    if not fund_code or not year.isdigit() or len(year) != 4:
        return {"success": False, "message": "参数错误"}

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            df = ak.fund_portfolio_hold_em(symbol=fund_code, date=year)
            if df.empty:
                raise ValueError("空数据")

            records = []
            for _, row in df.iterrows():
                quarter, report_date = parse_quarter_from_text(row['季度'])
                record = {
                    'fund_code': fund_code,
                    'stock_code': row['股票代码'],
                    'stock_name': row['股票名称'],
                    'proportion_of_nav': float(row['占净值比例']) if pd.notna(row['占净值比例']) else None,
                    'shares_held': float(row['持股数']) if pd.notna(row['持股数']) else None,
                    'market_value': float(row['持仓市值']) if pd.notna(row['持仓市值']) else None,
                    'quarter': quarter,
                    'report_date': report_date
                }
                records.append(record)

            saved = 0
            for rec in records:
                existing = FundHolding.query.filter_by(
                    fund_code=rec['fund_code'],
                    stock_code=rec['stock_code'],
                    quarter=rec['quarter']
                ).first()
                if not existing:
                    db.session.add(FundHolding(**rec))
                    saved += 1
            db.session.commit()
            return {"success": True, "message": f"保存 {saved} 条", "data": records}

        except Exception as e:
            db.session.rollback()
            if attempt < max_retries:
                time.sleep(random.uniform(1, 2))
            else:
                return {"success": False, "message": str(e), "data": []}
    return {"success": False, "message": "未知错误", "data": []}