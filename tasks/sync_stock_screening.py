# tasks/sync_stock_screening.py
# 股票多因子筛选数据同步任务
# 使用 stock_zh_a_spot_em() 获取实时数据
# 使用 stock_zh_a_hist() 计算历史涨跌幅

import akshare as ak
import pandas as pd
from datetime import datetime, date, timedelta
from decimal import Decimal
import time
import argparse
from config.logging_config import logger
from models import db
from models.stock_screening import StockScreeningData
from models.trading_day import TradingDay


def is_trading_day():
    today = date.today()
    try:
        return db.session.query(db.exists().where(TradingDay.trade_date == today)).scalar()
    except:
        return True


def safe_decimal(value, default=None):
    if pd.isna(value):
        return default
    try:
        return Decimal(str(float(value)))
    except:
        return default


def get_all_a_stocks():
    """获取全部A股数据"""
    logger.info("📡 获取A股实时行情...")
    df = ak.stock_zh_a_spot_em()
    logger.info(f"✅ 获取 {len(df)} 条数据")
    return df


def calculate_momentum_changes(stock_code):
    """计算动量因子：5日、10日、20日涨跌幅"""
    try:
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=120)).strftime('%Y%m%d')
        
        df = ak.stock_zh_a_hist(
            symbol=stock_code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"
        )
        
        if df is None or df.empty or len(df) < 20:
            return None, None, None
        
        df = df.sort_values('日期')
        latest_price = df['收盘'].iloc[-1]
        
        change_5d = None
        change_10d = None
        change_20d = None
        
        if len(df) >= 6:
            price_5d_ago = df['收盘'].iloc[-6]
            if price_5d_ago and price_5d_ago > 0:
                change_5d = ((latest_price - price_5d_ago) / price_5d_ago) * 100
        
        if len(df) >= 11:
            price_10d_ago = df['收盘'].iloc[-11]
            if price_10d_ago and price_10d_ago > 0:
                change_10d = ((latest_price - price_10d_ago) / price_10d_ago) * 100
        
        if len(df) >= 21:
            price_20d_ago = df['收盘'].iloc[-21]
            if price_20d_ago and price_20d_ago > 0:
                change_20d = ((latest_price - price_20d_ago) / price_20d_ago) * 100
        
        return change_5d, change_10d, change_20d
        
    except Exception as e:
        logger.debug(f"计算涨跌幅失败 {stock_code}: {e}")
        return None, None, None


def sync_stock_screening_data(force=False, include_momentum=True):
    """同步多因子选股数据
    
    Args:
        force: 强制同步
        include_momentum: 是否计算动量因子
    """
    today = date.today()
    
    if not force and not is_trading_day():
        logger.info("非交易日，跳过")
        return {"success": False, "message": "非交易日"}
    
    logger.info(f"开始同步多因子数据... 日期: {today}")
    start_time = time.time()
    
    try:
        # 1. 获取实时行情数据
        df = get_all_a_stocks()
        if df is None or df.empty:
            return {"success": False, "message": "无法获取实时行情数据"}
        
        df.columns = [c.strip() for c in df.columns]
        
        pe_count = df['市盈率-动态'].notna().sum() if '市盈率-动态' in df.columns else 0
        pb_count = df['市净率'].notna().sum() if '市净率' in df.columns else 0
        
        logger.info(f"PE数据: {pe_count} 条, PB数据: {pb_count} 条")
        
        # 2. 计算动量因子（全部股票）
        momentum_data = {}
        if include_momentum:
            logger.info("📊 计算动量因子...")
            stock_codes = df['代码'].astype(str).str.zfill(6).tolist()  # 全部股票
            for i, code in enumerate(stock_codes):
                if (i + 1) % 100 == 0:
                    logger.info(f"  进度: {i+1}/{len(stock_codes)}")
                try:
                    c5, c10, c20 = calculate_momentum_changes(code)
                    momentum_data[code] = {'change_5d': c5, 'change_10d': c10, 'change_20d': c20}
                    time.sleep(0.1)
                except Exception as e:
                    logger.debug(f"  {code} 计算失败: {e}")
            logger.info(f"  动量因子计算完成: {len(momentum_data)} 只")
        
        # 3. 处理数据
        stock_data = []
        for _, row in df.iterrows():
            code = str(row.get('代码', '')).strip()
            if not code:
                continue
            
            # 市值转换 (元 -> 亿元)
            total_mv = safe_decimal(row.get('总市值'))
            circ_mv = safe_decimal(row.get('流通市值'))
            if total_mv and total_mv > 0:
                total_mv = total_mv / 10000000000
            if circ_mv and circ_mv > 0:
                circ_mv = circ_mv / 10000000000
            
            # 动量因子
            momentum = momentum_data.get(code, {})
            
            record = {
                'stock_code': code,
                'stock_name': str(row.get('名称', '')).strip(),
                'latest_price': safe_decimal(row.get('最新价')),
                'open_price': safe_decimal(row.get('今开')),
                'high': safe_decimal(row.get('最高')),
                'low': safe_decimal(row.get('最低')),
                'pre_close': safe_decimal(row.get('昨收')),
                'change_percent': safe_decimal(row.get('涨跌幅')),
                'change_amount': safe_decimal(row.get('涨跌额')),
                'volume': safe_decimal(row.get('成交量')),
                'turnover': safe_decimal(row.get('成交额')),
                'turnover_rate': safe_decimal(row.get('换手率')),
                # 估值因子
                'pe': safe_decimal(row.get('市盈率-动态')),
                'pb': safe_decimal(row.get('市净率')),
                'ps': None,
                # 动量因子
                'change_5d': momentum.get('change_5d'),
                'change_10d': momentum.get('change_10d'),
                'change_20d': momentum.get('change_20d'),
                'change_60d': safe_decimal(row.get('60日涨跌幅')),
                # 质量因子（已移除）
                'roe': None,
                'gross_margin': None,
                'net_profit_margin': None,
                'revenue_growth': None,
                'profit_growth': None,
                # 规模因子
                'market_cap': total_mv,
                'circulating_cap': circ_mv,
                # 数据时间
                'trade_date': today,
                'fetch_time': datetime.utcnow(),
            }
            stock_data.append(record)
        
        # 4. 保存
        deleted = StockScreeningData.query.filter_by(trade_date=today).delete()
        logger.info(f"删除旧数据: {deleted} 条")
        
        db.session.bulk_insert_mappings(StockScreeningData, stock_data)
        db.session.commit()
        
        elapsed = time.time() - start_time
        logger.info(f"✅ 插入 {len(stock_data)} 条，耗时 {elapsed:.1f}秒")
        
        return {
            "success": True,
            "total": len(stock_data),
            "with_pe": pe_count,
            "with_pb": pb_count,
            "with_momentum": len(momentum_data),
            "elapsed": f"{elapsed:.1f}秒"
        }
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": str(e)}


def main():
    parser = argparse.ArgumentParser(description='多因子选股数据同步')
    parser.add_argument('--force', '-f', action='store_true', help='强制跳过交易日')
    parser.add_argument('--no-momentum', action='store_true', help='不计算动量因子')
    args = parser.parse_args()
    
    from app import app
    with app.app_context():
        print("=" * 50)
        print("多因子选股数据同步")
        print("=" * 50)
        result = sync_stock_screening_data(force=args.force, include_momentum=not args.no_momentum)
        print(f"\n结果: {result}")


if __name__ == '__main__':
    main()
