# tasks/sync_stock_momentum.py
# 使用baostock同步股票动量因子（5日、10日、20日涨跌幅）

import baostock as bs
import pandas as pd
from datetime import datetime, date, timedelta
from decimal import Decimal
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db
from models.stock_screening import StockScreeningData


def get_momentum_for_stock(stock_code, trade_date):
    """获取单只股票的动量因子
    
    Args:
        stock_code: 股票代码 (如 600519)
        trade_date: 交易日期
    
    Returns:
        dict: {change_5d, change_10d, change_20d}
    """
    try:
        # 判断交易所
        if stock_code.startswith('6'):
            bs_code = f"sh.{stock_code}"
        elif stock_code.startswith(('0', '3')):
            bs_code = f"sz.{stock_code}"
        else:
            return None
        
        # 计算日期范围（需要60个交易日的数据）
        end_date = trade_date.strftime('%Y-%m-%d')
        start_date = (trade_date - timedelta(days=120)).strftime('%Y-%m-%d')
        
        rs = bs.query_history_k_data_plus(
            bs_code,
            'date,close',
            start_date=start_date,
            end_date=end_date,
            frequency='d'
        )
        
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        
        if not data_list:
            return None
        
        df = pd.DataFrame(data_list, columns=rs.fields)
        df = df[df['close'].notna() & (df['close'] != '')]
        
        if len(df) < 25:
            return None
        
        # 计算涨跌幅
        latest_close = float(df['close'].iloc[-1])
        
        change_5d = None
        if len(df) >= 6:
            price_5d = float(df['close'].iloc[-6])
            if price_5d > 0:
                change_5d = round((latest_close - price_5d) / price_5d * 100, 2)
        
        change_10d = None
        if len(df) >= 11:
            price_10d = float(df['close'].iloc[-11])
            if price_10d > 0:
                change_10d = round((latest_close - price_10d) / price_10d * 100, 2)
        
        change_20d = None
        if len(df) >= 21:
            price_20d = float(df['close'].iloc[-21])
            if price_20d > 0:
                change_20d = round((latest_close - price_20d) / price_20d * 100, 2)
        
        return {
            'change_5d': Decimal(str(change_5d)) if change_5d else None,
            'change_10d': Decimal(str(change_10d)) if change_10d else None,
            'change_20d': Decimal(str(change_20d)) if change_20d else None,
        }
        
    except Exception as e:
        print(f"Error {stock_code}: {e}")
        return None


def sync_momentum_data(limit=200):
    """同步动量因子数据
    
    Args:
        limit: 同步N只没有动量数据的股票
    """
    print("=" * 50)
    print("股票动量因子同步 (baostock)")
    print("=" * 50)
    
    # 登录baostock
    lg = bs.login()
    if lg.error_code != '0':
        print(f"登录失败: {lg.error_msg}")
        return {'success': False, 'message': lg.error_msg}
    print("登录成功!")
    
    with app.app_context():
        today = date.today()
        
        # 获取需要同步的股票（没有动量数据的，按市值排序）
        stocks = StockScreeningData.query.filter_by(
            trade_date=today
        ).filter(
            StockScreeningData.change_20d.is_(None)
        ).order_by(
            StockScreeningData.market_cap.desc()
        ).limit(limit).all()
        
        print(f"开始同步动量因子... 股票数: {len(stocks)}")
        
        success_count = 0
        fail_count = 0
        
        for i, stock in enumerate(stocks):
            if (i + 1) % 50 == 0:
                db.session.commit()
                print(f"  进度: {i+1}/{len(stocks)}, 已提交")
            
            # 不再跳过，每只股票都重新获取
            
            momentum = get_momentum_for_stock(stock.stock_code, today)
            
            if momentum:
                stock.change_5d = momentum['change_5d']
                stock.change_10d = momentum['change_10d']
                stock.change_20d = momentum['change_20d']
                success_count += 1
            else:
                fail_count += 1
            
            # 避免请求过快
            time.sleep(0.15)
        
        db.session.commit()
        print(f"✅ 动量因子同步完成: 成功 {success_count}, 失败 {fail_count}")
        
        # 登出
        bs.logout()
        
        return {
            'success': True,
            'total': len(stocks),
            'updated': success_count,
            'failed': fail_count
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description='股票动量因子同步')
    parser.add_argument('--limit', '-l', type=int, default=200, help='同步股票数量')
    args = parser.parse_args()
    
    result = sync_momentum_data(limit=args.limit)
    print(f"\n结果: {result}")


if __name__ == '__main__':
    main()
