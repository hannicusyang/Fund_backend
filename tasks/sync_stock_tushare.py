# tasks/sync_stock_tushare.py
# 使用第三方Tushare代理接口同步股票数据
# 绕过积分限制

import tushare as ts
import pandas as pd
from datetime import datetime, date, timedelta
from decimal import Decimal
import time
from config.logging_config import logger
from models import db
from models.stock_screening import StockScreeningData
from models.trading_day import TradingDay


# Tushare 第三方代理配置
TUSHARE_TOKEN = '4502105893002009438'
TUSHARE_PROXY = 'http://5k1a.xiximiao.com/dataapi'


def get_pro():
    """获取tushare pro接口"""
    pro = ts.pro_api('dummy')
    pro._DataApi__token = TUSHARE_TOKEN
    pro._DataApi__http_url = TUSHARE_PROXY
    return pro


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


def get_stock_list(pro):
    """获取A股股票列表"""
    logger.info("📡 获取A股股票列表...")
    df = pro.stock_basic(limit=6000, offset=0)
    # 只保留沪深A股
    df = df[df['ts_code'].str.endswith(('.SH', '.SZ'))]
    logger.info(f"✅ 获取 {len(df)} 只A股")
    return df


def get_realtime_data(pro, stock_codes):
    """批量获取实时行情数据（分批）"""
    all_data = []
    batch_size = 100
    
    for i in range(0, len(stock_codes), batch_size):
        batch = stock_codes[i:i+batch_size]
        logger.info(f"  获取实时行情 {i+1}-{min(i+batch_size, len(stock_codes))}/{len(stock_codes)}")
        
        try:
            # 一次性获取多只股票
            df = pro.realtime_quotes(batch[:50])
            if df is not None and not df.empty:
                all_data.append(df)
        except Exception as e:
            logger.warning(f"    批量获取失败: {e}")
            # 逐个获取
            for code in batch:
                try:
                    df = pro.realtime_quotes([code])
                    if df is not None and not df.empty:
                        all_data.append(df)
                except:
                    pass
        
        time.sleep(0.2)
    
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return pd.DataFrame()


def get_daily_basic(pro, trade_date):
    """获取每日指标数据"""
    try:
        # 分页获取
        all_data = []
        for offset in range(0, 5000, 1000):
            df = pro.daily_basic(trade_date=trade_date, limit=1000, offset=offset)
            if df is None or df.empty:
                break
            all_data.append(df)
            time.sleep(0.3)
        
        if all_data:
            return pd.concat(all_data, ignore_index=True)
    except Exception as e:
        logger.warning(f"获取daily_basic失败: {e}")
    return pd.DataFrame()


def sync_stock_tushare(force=False):
    """使用tushare代理同步股票数据"""
    today = date.today()
    
    if not force and not is_trading_day():
        logger.info("非交易日，跳过")
        return {"success": False, "message": "非交易日"}
    
    logger.info(f"开始同步股票数据... 日期: {today}")
    start_time = time.time()
    
    try:
        pro = get_pro()
        
        # 1. 获取股票列表
        stock_list = get_stock_list(pro)
        logger.info(f"总计 {len(stock_list)} 只股票")
        
        # 2. 获取实时行情（如果可用）
        # 由于realtime_quotes可能有限制，我们主要用daily_basic
        
        # 3. 获取每日指标数据
        logger.info("📊 获取每日指标数据...")
        
        # 先获取最新的交易日
        df_cal = pro.trade_cal(exchange='', start_date='20250201', end_date=today.strftime('%Y%m%d'))
        if df_cal is not None and not df_cal.empty:
            df_cal = df_cal[df_cal['is_open'] == 1]
            if not df_cal.empty:
                latest_trade_date = df_cal['cal_date'].max()
                logger.info(f"最新交易日: {latest_trade_date}")
                
                daily_data = get_daily_basic(pro, latest_trade_date)
                if not daily_data.empty:
                    logger.info(f"✅ 获取 {len(daily_data)} 条每日指标")
        
        # 4. 处理数据
        stock_data = []
        
        # 如果有daily_basic数据，创建映射
        data_map = {}
        if not daily_data.empty:
            for _, row in daily_data.iterrows():
                ts_code = row['ts_code']
                code = ts_code.split('.')[0]
                data_map[code] = row
        
        # 处理每只股票
        for _, row in stock_list.iterrows():
            ts_code = row['ts_code']
            code = ts_code.split('.')[0]
            
            # 从daily_basic获取数据
            basic_data = data_map.get(code, {})
            
            # 市值转换
            total_mv = safe_decimal(basic_data.get('total_mv'))
            circ_mv = safe_decimal(basic_data.get('circ_mv'))
            if total_mv and total_mv > 0:
                total_mv = total_mv / 100000000  # 元转亿元
            if circ_mv and circ_mv > 0:
                circ_mv = circ_mv / 100000000
            
            record = {
                'stock_code': code,
                'stock_name': row['name'],
                'latest_price': safe_decimal(basic_data.get('close')),
                'open_price': None,  # daily_basic没有
                'high': None,
                'low': None,
                'pre_close': safe_decimal(basic_data.get('pre_close')),
                'change_percent': safe_decimal(basic_data.get('pct_chg')),
                'change_amount': safe_decimal(basic_data.get('change')),
                'volume': safe_decimal(basic_data.get('vol')),
                'turnover': safe_decimal(basic_data.get('amount')),
                'turnover_rate': safe_decimal(basic_data.get('turnover_rate')),
                # 估值因子
                'pe': safe_decimal(basic_data.get('pe')),
                'pb': safe_decimal(basic_data.get('pb')),
                'ps': safe_decimal(basic_data.get('ps')),
                # 动量因子（暂无）
                'change_5d': None,
                'change_10d': None,
                'change_20d': None,
                'change_60d': None,
                # 质量因子
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
        
        # 5. 保存到数据库
        deleted = StockScreeningData.query.filter_by(trade_date=today).delete()
        logger.info(f"删除旧数据: {deleted} 条")
        
        db.session.bulk_insert_mappings(StockScreeningData, stock_data)
        db.session.commit()
        
        elapsed = time.time() - start_time
        logger.info(f"✅ 插入 {len(stock_data)} 条，耗时 {elapsed:.1f}秒")
        
        return {
            "success": True,
            "total": len(stock_data),
            "elapsed": f"{elapsed:.1f}秒"
        }
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": str(e)}


def main():
    from app import app
    with app.app_context():
        print("=" * 50)
        print("Tushare代理股票数据同步")
        print("=" * 50)
        result = sync_stock_tushare(force=True)
        print(f"\n结果: {result}")


if __name__ == '__main__':
    main()
