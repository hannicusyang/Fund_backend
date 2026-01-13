# fund_holdings_fetcher.py
import akshare as ak
import pandas as pd
import logging
import time
import random
from config.logging_config import logger  # 复用你的日志配置


def fetch_fund_holdings(fund_code: str, year: str) -> dict:
    """
    获取指定基金在某一年的持仓数据（来自天天基金网）

    Args:
        fund_code (str): 基金代码，如 "000001"
        year (str): 年份，如 "2024"

    Returns:
        dict: 包含 success, message, data 等字段的结构化结果
              data 是列表，每个元素为一条持仓记录（字典）
    """
    fund_code = str(fund_code).strip()
    year = str(year).strip()

    if not fund_code or not year.isdigit() or len(year) != 4:
        return {
            "success": False,
            "message": "参数错误：fund_code 不能为空，year 必须是四位年份",
            "data": []
        }

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            logger.info(f"正在抓取基金 {fund_code} {year} 年持仓数据...")
            df = ak.fund_portfolio_hold_em(symbol=fund_code, date=year)

            if df is None or df.empty:
                raise ValueError("akshare 返回空数据")

            # 列重命名（与历史净值脚本风格一致）
            df = df.rename(columns={
                '序号': 'rank',
                '股票代码': 'stock_code',
                '股票名称': 'stock_name',
                '占净值比例': 'proportion_of_nav',  # 单位: %
                '持股数': 'shares_held',            # 单位: 万股
                '持仓市值': 'market_value',         # 单位: 万元
                '季度': 'quarter'
            })

            # 数据清洗
            df['rank'] = pd.to_numeric(df['rank'], errors='coerce')
            df['proportion_of_nav'] = pd.to_numeric(df['proportion_of_nav'], errors='coerce')
            df['shares_held'] = pd.to_numeric(df['shares_held'], errors='coerce')
            df['market_value'] = pd.to_numeric(df['market_value'], errors='coerce')

            # 转为字典列表（适合 JSON 序列化）
            holdings = df.to_dict(orient='records')

            logger.info(f"✅ 基金 {fund_code} {year} 年共获取 {len(holdings)} 条持仓记录")
            return {
                "success": True,
                "message": f"成功获取 {len(holdings)} 条持仓数据",
                "data": holdings
            }

        except Exception as e:
            error_msg = str(e).split('\n')[0][:150]
            if attempt < max_retries:
                wait_sec = random.uniform(1.0, 2.0)
                logger.warning(
                    f"基金 {fund_code} 第 {attempt + 1} 次抓取失败（{error_msg}），"
                    f"{wait_sec:.1f} 秒后重试..."
                )
                time.sleep(wait_sec)
            else:
                logger.error(f"基金 {fund_code} {year} 年持仓抓取最终失败: {error_msg}")
                return {
                    "success": False,
                    "message": f"抓取失败: {error_msg}",
                    "data": []
                }

    return {
        "success": False,
        "message": "未知错误",
        "data": []
    }


# services/fund_holdings_fetcher.py
def parse_quarter_from_text(text: str):
    try:
        year = text[:4]
        q = text[5]
        quarter = f"{year}Q{q}"
        report_map = {"1": f"{year}-03-31", "2": f"{year}-06-30", "3": f"{year}-09-30", "4": f"{year}-12-31"}
        return quarter, report_map.get(q)
    except:
        return "UNKNOWN", None