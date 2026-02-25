#!/usr/bin/env python3
"""
股票波动率计算任务
预先计算所有股票的年化波动率并存入数据库
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models.stock_screening import StockScreeningData
import baostock as bs
from datetime import datetime, timedelta
import math
from sqlalchemy import text

def calculate_stock_volatility(stock_code, days=60):
    """计算单只股票的年化波动率"""
    try:
        # 转换代码格式
        if stock_code.startswith('6'):
            bs_code = f"sh.{stock_code}"
        elif stock_code.startswith(('0', '3')):
            bs_code = f"sz.{stock_code}"
        else:
            return None
        
        # 计算日期范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 30)
        
        lg = bs.login()
        if lg.error_code != '0':
            return None
        
        rs = bs.query_history_k_data_plus(
            bs_code,
            'date,close,pctChg',
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            frequency='d',
            adjustflag='2'  # 前复权
        )
        
        if rs is None or rs.error_code != '0':
            bs.logout()
            return None
        
        daily_returns = []
        while (rs.error_code == '0') & rs.next():
            row = rs.get_row_data()
            if len(row) >= 3 and row[2]:
                try:
                    daily_returns.append(float(row[2]))
                except:
                    pass
        
        bs.logout()
        
        if len(daily_returns) < 20:
            return None
        
        # 计算日收益率的标准差
        mean_return = sum(daily_returns) / len(daily_returns)
        variance = sum((x - mean_return) ** 2 for x in daily_returns) / len(daily_returns)
        daily_volatility = math.sqrt(variance)
        
        # 年化波动率
        annual_volatility = daily_volatility * math.sqrt(252)
        
        return round(annual_volatility, 2)
        
    except Exception as e:
        print(f"计算 {stock_code} 波动率失败: {e}")
        return None


def sync_all_volatility():
    """同步所有股票的波动率"""
    print("开始计算股票波动率...")
    
    # 获取所有有数据的股票
    stocks = db.session.query(StockScreeningData.stock_code).distinct().all()
    total = len(stocks)
    success = 0
    failed = 0
    
    for i, (stock_code,) in enumerate(stocks):
        if (i + 1) % 50 == 0:
            print(f"进度: {i+1}/{total}")
        
        volatility = calculate_stock_volatility(stock_code)
        
        if volatility:
            # 更新数据库
            db.session.execute(
                text("""
                    UPDATE stock_screening_data 
                    SET volatility = :vol 
                    WHERE stock_code = :code
                """),
                {"vol": volatility, "code": stock_code}
            )
            success += 1
        else:
            failed += 1
    
    db.session.commit()
    print(f"波动率计算完成: 成功 {success}, 失败 {failed}")


if __name__ == '__main__':
    with app.app_context():
        sync_all_volatility()
