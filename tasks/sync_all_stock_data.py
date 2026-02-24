# tasks/sync_all_stock_data.py
# 股票全量数据同步脚本
# 同步内容：
# 1. 实时行情（PE、PB、市值、涨跌幅等）
# 2. 财务因子（ROE、毛利率、净利率、营收增长、利润增长）
# 3. 动量因子（5日、10日、20日涨跌幅）
# 数据源：akshare + baostock
# 建议运行时间：凌晨1点（A股收盘后）

import akshare as ak
import baostock as bs
import pandas as pd
from datetime import datetime, date, timedelta
from decimal import Decimal
import time
import sys
import os
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db
from models.stock_screening import StockScreeningData


def parse_percent(value):
    """解析百分比字符串"""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        if '%' in value:
            try:
                return Decimal(value.replace('%', ''))
            except:
                return None
        if value.lower() == 'false' or value == '':
            return None
        try:
            return Decimal(value)
        except:
            return None
    return None


def sync_realtime_data():
    """同步实时行情数据"""
    logger.info("=" * 50)
    logger.info("Step 1: 同步实时行情 (akshare)")
    logger.info("=" * 50)
    
    try:
        df = ak.stock_zh_a_spot_em()
        logger.info(f"获取到 {len(df)} 条实时数据")
        
        today = date.today()
        
        # 清除旧数据
        deleted = StockScreeningData.query.filter_by(trade_date=today).delete()
        logger.info(f"清除旧数据: {deleted} 条")
        
        records = []
        for i, row in df.iterrows():
            try:
                # 市值转换
                total_mv = row.get('总市值')
                circ_mv = row.get('流通市值')
                if pd.notna(total_mv) and total_mv > 0:
                    total_mv = total_mv / 100000000
                else:
                    total_mv = None
                if pd.notna(circ_mv) and circ_mv > 0:
                    circ_mv = circ_mv / 100000000
                else:
                    circ_mv = None
                
                record = StockScreeningData(
                    trade_date=today,
                    stock_code=str(row.get('代码', '')),
                    stock_name=str(row.get('名称', '')),
                    latest_price=Decimal(str(row.get('最新价', 0))) if pd.notna(row.get('最新价')) else None,
                    open_price=Decimal(str(row.get('今开', 0))) if pd.notna(row.get('今开')) else None,
                    high=Decimal(str(row.get('最高', 0))) if pd.notna(row.get('最高')) else None,
                    low=Decimal(str(row.get('最低', 0))) if pd.notna(row.get('最低')) else None,
                    pre_close=Decimal(str(row.get('昨收', 0))) if pd.notna(row.get('昨收')) else None,
                    change_percent=Decimal(str(row.get('涨跌幅', 0))) if pd.notna(row.get('涨跌幅')) else None,
                    change_amount=Decimal(str(row.get('涨跌额', 0))) if pd.notna(row.get('涨跌额')) else None,
                    volume=Decimal(str(row.get('成交量', 0))) if pd.notna(row.get('成交量')) else None,
                    turnover=Decimal(str(row.get('成交额', 0))) if pd.notna(row.get('成交额')) else None,
                    turnover_rate=Decimal(str(row.get('换手率', 0))) if pd.notna(row.get('换手率')) else None,
                    pe=Decimal(str(row.get('市盈率-动态', 0))) if pd.notna(row.get('市盈率-动态')) and row.get('市盈率-动态') > 0 else None,
                    pb=Decimal(str(row.get('市净率', 0))) if pd.notna(row.get('市净率')) and row.get('市净率') > 0 else None,
                    market_cap=total_mv,
                    circulating_cap=circ_mv,
                    fetch_time=datetime.now(),
                )
                records.append(record)
            except Exception as e:
                continue
        
        db.session.bulk_save_objects(records)
        db.session.commit()
        logger.info(f"实时行情同步完成: {len(records)} 条")
        return {'success': True, 'count': len(records)}
        
    except Exception as e:
        logger.error(f"实时行情同步失败: {e}")
        return {'success': False, 'message': str(e)}


def get_financial_for_stock(stock_code):
    """获取单只股票财务因子"""
    try:
        df = ak.stock_financial_abstract_ths(symbol=stock_code, indicator='按报告期')
        if df is None or df.empty:
            return None
        
        df = df.sort_values('报告期', ascending=False)
        
        latest = None
        for _, row in df.iterrows():
            roe = row.get('净资产收益率')
            if roe and str(roe).lower() != 'false':
                latest = row
                break
        
        if latest is None:
            latest = df.iloc[0]
        
        return {
            'roe': parse_percent(latest.get('净资产收益率')),
            'gross_margin': parse_percent(latest.get('销售净利率')),
            'net_profit_margin': parse_percent(latest.get('销售净利率')),
            'revenue_growth': parse_percent(latest.get('营业总收入同比增长率')),
            'profit_growth': parse_percent(latest.get('净利润同比增长率')),
        }
    except Exception as e:
        return None


def sync_financial_data(limit=500):
    """同步财务因子"""
    logger.info("=" * 50)
    logger.info("Step 2: 同步财务因子 (akshare)")
    logger.info("=" * 50)
    
    with app.app_context():
        today = date.today()
        
        # 获取需要同步的股票（没有财务数据的）
        stocks = StockScreeningData.query.filter_by(trade_date=today).filter(
            StockScreeningData.roe.is_(None)
        ).order_by(StockScreeningData.market_cap.desc()).limit(limit).all()
        
        logger.info(f"需要同步财务因子: {len(stocks)} 只")
        
        success = 0
        for i, stock in enumerate(stocks):
            if (i + 1) % 50 == 0:
                logger.info(f"  进度: {i+1}/{len(stocks)}")
            
            financial = get_financial_for_stock(stock.stock_code)
            if financial:
                stock.roe = financial['roe']
                stock.gross_margin = financial['gross_margin']
                stock.net_profit_margin = financial['net_profit_margin']
                stock.revenue_growth = financial['revenue_growth']
                stock.profit_growth = financial['profit_growth']
                success += 1
            
            time.sleep(0.2)
        
        db.session.commit()
        logger.info(f"财务因子同步完成: {success} 只")
        return {'success': True, 'count': success}


def get_momentum_for_stock(stock_code, trade_date):
    """获取单只股票动量因子"""
    try:
        if stock_code.startswith('6'):
            bs_code = f"sh.{stock_code}"
        elif stock_code.startswith(('0', '3')):
            bs_code = f"sz.{stock_code}"
        else:
            return None
        
        end_date = trade_date.strftime('%Y-%m-%d')
        start_date = (trade_date - timedelta(days=120)).strftime('%Y-%m-%d')
        
        rs = bs.query_history_k_data_plus(
            bs_code, 'date,close',
            start_date=start_date, end_date=end_date, frequency='d'
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
        
        latest_close = float(df['close'].iloc[-1])
        
        change_5d = None
        if len(df) >= 6:
            price = float(df['close'].iloc[-6])
            if price > 0:
                change_5d = round((latest_close - price) / price * 100, 2)
        
        change_10d = None
        if len(df) >= 11:
            price = float(df['close'].iloc[-11])
            if price > 0:
                change_10d = round((latest_close - price) / price * 100, 2)
        
        change_20d = None
        if len(df) >= 21:
            price = float(df['close'].iloc[-21])
            if price > 0:
                change_20d = round((latest_close - price) / price * 100, 2)
        
        return {
            'change_5d': Decimal(str(change_5d)) if change_5d else None,
            'change_10d': Decimal(str(change_10d)) if change_10d else None,
            'change_20d': Decimal(str(change_20d)) if change_20d else None,
        }
    except:
        return None


def sync_momentum_data(limit=500):
    """同步动量因子"""
    logger.info("=" * 50)
    logger.info("Step 3: 同步动量因子 (baostock)")
    logger.info("=" * 50)
    
    # 登录baostock
    lg = bs.login()
    if lg.error_code != '0':
        logger.error(f"baostock登录失败: {lg.error_msg}")
        return {'success': False, 'message': lg.error_msg}
    
    with app.app_context():
        today = date.today()
        
        # 获取需要同步的股票（没有动量数据的）
        stocks = StockScreeningData.query.filter_by(trade_date=today).filter(
            StockScreeningData.change_20d.is_(None)
        ).order_by(StockScreeningData.market_cap.desc()).limit(limit).all()
        
        logger.info(f"需要同步动量因子: {len(stocks)} 只")
        
        success = 0
        for i, stock in enumerate(stocks):
            if (i + 1) % 100 == 0:
                db.session.commit()
                logger.info(f"  进度: {i+1}/{len(stocks)}")
            
            momentum = get_momentum_for_stock(stock.stock_code, today)
            if momentum:
                stock.change_5d = momentum['change_5d']
                stock.change_10d = momentum['change_10d']
                stock.change_20d = momentum['change_20d']
                success += 1
            
            time.sleep(0.15)
        
        db.session.commit()
        logger.info(f"动量因子同步完成: {success} 只")
    
    bs.logout()
    return {'success': True, 'count': success}


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("开始股票全量数据同步")
    logger.info("=" * 60)
    
    start_time = time.time()
    
    # Step 1: 实时行情
    result1 = sync_realtime_data()
    
    # Step 2: 财务因子
    result2 = sync_financial_data(limit=500)
    
    # Step 3: 动量因子
    result3 = sync_momentum_data(limit=500)
    
    elapsed = time.time() - start_time
    
    logger.info("=" * 60)
    logger.info(f"全量同步完成! 耗时: {elapsed/60:.1f} 分钟")
    logger.info(f"  实时行情: {result1}")
    logger.info(f"  财务因子: {result2}")
    logger.info(f"  动量因子: {result3}")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
