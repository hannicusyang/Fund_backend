# tasks/sync_stock_financial.py
# 股票财务因子同步 - ROE、毛利率、净利率、营收增长、利润增长
# 数据源: tushare (第三方代理) > akshare

import akshare as ak
import pandas as pd
from datetime import datetime, date
from decimal import Decimal
import time
import sys
import os
import re

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db
from models.stock_screening import StockScreeningData

# 导入tushare
from utils.tushare_api import get_pro, get_fina_indicator


def parse_percent(value):
    """解析百分比字符串为数值"""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    # 处理 "17.65%" 格式
    if isinstance(value, str):
        if '%' in value:
            try:
                return Decimal(value.replace('%', ''))
            except:
                return None
        # 处理 "4.82亿" 格式
        if '亿' in value:
            try:
                return Decimal(float(value.replace('亿', '')) * 100000000)
            except:
                return None
        # 处理 "False" 等
        if value.lower() == 'false' or value == '':
            return None
        try:
            return Decimal(value)
        except:
            return None
    return None


def safe_decimal(value, default=None):
    """安全转换Decimal"""
    if pd.isna(value) or value is None:
        return default
    try:
        return Decimal(str(float(value)))
    except:
        return default


def get_financial_indicators(stock_code):
    """获取单只股票的财务指标"""
    try:
        # 财务摘要
        df = ak.stock_financial_abstract_ths(symbol=stock_code, indicator='按报告期')
        
        if df is None or df.empty:
            return None
        
        # 取最新报告期数据（不是False的）
        df = df.sort_values('报告期', ascending=False)
        
        latest = None
        for _, row in df.iterrows():
            # 找一个有效的记录（净资产收益率不是False）
            roe = row.get('净资产收益率')
            if roe and str(roe).lower() != 'false':
                latest = row
                break
        
        if latest is None:
            latest = df.iloc[0]
        
        return {
            'roe': parse_percent(latest.get('净资产收益率')),
            'gross_margin': parse_percent(latest.get('销售净利率')),  # 用销售净利率代替毛利率
            'net_profit_margin': parse_percent(latest.get('销售净利率')),
            'revenue_growth': parse_percent(latest.get('营业总收入同比增长率')),
            'profit_growth': parse_percent(latest.get('净利润同比增长率')),
        }
    except Exception as e:
        print(f"Error getting financial for {stock_code}: {e}")
        return None


def sync_financial_data(limit=100):
    """同步财务因子数据
    
    Args:
        limit: 同步前N只股票（按市值排序）
    """
    with app.app_context():
        today = date.today()
        
        # 获取今日已有数据的股票（按市值排序，取前N只）
        stocks = StockScreeningData.query.filter_by(
            trade_date=today
        ).order_by(
            StockScreeningData.market_cap.desc()
        ).limit(limit).all()
        
        print(f"📊 开始同步财务因子... 股票数: {len(stocks)}")
        
        success_count = 0
        fail_count = 0
        
        for i, stock in enumerate(stocks):
            if (i + 1) % 10 == 0:
                print(f"  进度: {i+1}/{len(stocks)}")
            
            financial = get_financial_indicators(stock.stock_code)
            
            if financial:
                stock.roe = financial['roe']
                stock.gross_margin = financial['gross_margin']
                stock.net_profit_margin = financial['net_profit_margin']
                stock.revenue_growth = financial['revenue_growth']
                stock.profit_growth = financial['profit_growth']
                success_count += 1
                print(f"  {stock.stock_code} {stock.stock_name}: ROE={financial['roe']}")
            else:
                fail_count += 1
            
            # 避免请求过快
            time.sleep(0.3)
        
        db.session.commit()
        print(f"✅ 财务因子同步完成: 成功 {success_count}, 失败 {fail_count}")
        
        return {
            'success': True,
            'total': len(stocks),
            'updated': success_count,
            'failed': fail_count
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description='股票财务因子同步')
    parser.add_argument('--limit', '-l', type=int, default=100, help='同步股票数量')
    args = parser.parse_args()
    
    print("=" * 50)
    print("股票财务因子同步")
    print("=" * 50)
    
    result = sync_financial_data(limit=args.limit)
    print(f"\n结果: {result}")


if __name__ == '__main__':
    main()
