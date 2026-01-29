# services/fund_holdings_fetcher.py
import akshare as ak
import pandas as pd
from utils.date_utils import parse_quarter_from_text

from config import logger

def fetch_fund_holdings(fund_code: str, year: str) -> dict:
    """ 抓取某基金某年的所有季度持仓（经清洗和标准化） """
    try:
        df = ak.fund_portfolio_hold_em(symbol=fund_code, date=year)

        # 新增：处理空数据情况
        if df.empty:
            return {"success": True, "message": "无持仓数据", "data": []}

        # === 关键修复：动态处理列数 ===
        current_cols = len(df.columns)
        if current_cols == 7:
            # 标准7列：含“季度”
            df.columns = [
                'quarter_raw', 'stock_code', 'stock_name',
                'proportion_of_nav', 'shares_held', 'market_value', 'quarter'
            ]
            # 注意：这里第一个是“序号”，但您后续用 quarter_raw 没用到，可忽略
            # 实际“季度”在最后一列
        elif current_cols == 6:
            # 缺少“季度”列（如2025年最新数据）
            df.columns = [
                'quarter_raw', 'stock_code', 'stock_name',
                'proportion_of_nav', 'shares_held', 'market_value'
            ]
            # 手动添加 quarter 列（用年份代替，后续 parse_quarter_from_text 可能会修正）
            df['quarter'] = year
        else:
            logger.warning(f"未知列数 {current_cols}，跳过: {fund_code}@{year}")
            return {"success": True, "message": "列数异常，跳过", "data": []}

        # 清洗数值字段
        for col in ['proportion_of_nav', 'shares_held', 'market_value']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        holdings = []
        for _, row in df.iterrows():
            # 使用 row['quarter']（可能是 year 字符串，也可能是 "2024Q3"）
            quarter_std, report_date = parse_quarter_from_text(row['quarter'])
            if not quarter_std:
                # 如果解析失败，尝试用 year + Q4 作为 fallback（可选）
                quarter_std = f"{year}Q4"
                report_date = f"{year}-12-31"

            holding = {
                'stock_code': str(row['stock_code']).strip(),
                'stock_name': str(row['stock_name']).strip(),
                'proportion_of_nav': row['proportion_of_nav'],
                'shares_held': row['shares_held'],
                'market_value': row['market_value'],
                'quarter': row['quarter'],  # 标准化如 "2025Q4"
                'report_date': report_date,  # 如 "2025-12-31"
            }
            holdings.append(holding)

        return {"success": True, "message": "成功", "data": holdings}

    except Exception as e:
        logger.error(f"抓取失败 fund_code={fund_code}, year={year}: {e}")
        return {"success": False, "message": str(e), "data": []}