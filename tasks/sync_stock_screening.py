# tasks/sync_stock_screening.py
# 股票多因子筛选数据同步任务
# 数据源：tushare (第三方代理) + akshare (备选)

import akshare as ak
import pandas as pd
from datetime import datetime, date, timedelta
from decimal import Decimal
import time
import json
import os
from config.logging_config import logger
from models import db
from models.stock_screening import StockScreeningData
from models.trading_day import TradingDay
from utils.tushare_api import get_pro, get_stock_list, get_daily_basic, get_trade_cal


# 缓存文件路径
CACHE_DIR = '/home/clawdbot/.openclaw/workspace/Fund_backend/cache'
CACHE_FILE = os.path.join(CACHE_DIR, 'momentum_cache.json')


def ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def load_momentum_cache():
    ensure_cache_dir()
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}


def save_momentum_cache(cache):
    ensure_cache_dir()
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f)
    except Exception as e:
        logger.warning(f"保存缓存失败: {e}")


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


def get_all_a_stocks_akshare():
    """通过akshare获取全部A股数据"""
    try:
        logger.info("📡 [akshare] 获取A股实时行情...")
        df = ak.stock_zh_a_spot_em()
        if df is not None and not df.empty:
            logger.info(f"✅ [akshare] 获取 {len(df)} 条数据")
            return df
    except Exception as e:
        logger.warning(f"[akshare] 失败: {e}")
    return None


def get_all_a_stocks_tushare():
    """通过tushare获取全部A股数据"""
    try:
        logger.info("📡 [tushare] 获取A股股票列表...")
        stock_list = get_stock_list(limit=6000)
        
        if stock_list is None or stock_list.empty:
            return None
        
        # 获取每日指标 - 使用最新有数据的交易日
        df_cal = get_trade_cal(
            start_date=(date.today() - timedelta(days=30)).strftime('%Y%m%d'),
            end_date=date.today().strftime('%Y%m%d')
        )
        daily_data = pd.DataFrame()
        if df_cal is not None and not df_cal.empty:
            df_cal = df_cal[df_cal['is_open'] == 1]
            if not df_cal.empty:
                # 倒序查找最新的有数据的日期
                for latest_date in reversed(df_cal['cal_date'].tolist()):
                    logger.info(f"📡 [tushare] 尝试获取每日指标 ({latest_date})...")
                    temp_data = get_daily_basic(latest_date)
                    if not temp_data.empty:
                        daily_data = temp_data
                        logger.info(f"✅ [tushare] 获取 {len(daily_data)} 条每日指标 ({latest_date})")
                        break
        
        # 合并数据
        result = stock_list.copy()
        
        # 创建daily数据映射
        data_map = {}
        if not daily_data.empty:
            for _, row in daily_data.iterrows():
                ts_code = row['ts_code']
                code = ts_code.split('.')[0]
                data_map[code] = row
        
        # 添加数据列
        for col in ['close', 'pe', 'pb', 'ps', 'turnover_rate', 'vol', 'amount', 'pct_chg', 'total_mv', 'circ_mv']:
            result[col] = None
        
        for idx, row in result.iterrows():
            code = row['symbol']
            if code in data_map:
                d = data_map[code]
                result.at[idx, 'close'] = d.get('close')
                result.at[idx, 'pe'] = d.get('pe')
                result.at[idx, 'pb'] = d.get('pb')
                result.at[idx, 'ps'] = d.get('ps')
                result.at[idx, 'turnover_rate'] = d.get('turnover_rate')
                result.at[idx, 'vol'] = d.get('vol')
                result.at[idx, 'amount'] = d.get('amount')
                result.at[idx, 'pct_chg'] = d.get('pct_chg')
                result.at[idx, 'total_mv'] = d.get('total_mv')
                result.at[idx, 'circ_mv'] = d.get('circ_mv')
        
        # 重命名列以匹配后续处理
        result = result.rename(columns={
            'symbol': '代码',
            'name': '名称',
            'close': '最新价',
            'pct_chg': '涨跌幅',
            'turnover_rate': '换手率',
            'total_mv': '总市值',
            'circ_mv': '流通市值',
            'vol': '成交量',
            'amount': '成交额'
        })
        
        logger.info(f"✅ [tushare] 获取 {len(result)} 只股票")
        return result
        
    except Exception as e:
        logger.warning(f"[tushare] 失败: {e}")
    return None


def calculate_single_momentum(stock_code):
    """计算单只股票的动量因子"""
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
        
        change_5d = change_10d = change_20d = None
        
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


def calculate_momentum_batch(stock_codes, existing_cache, batch_size=30, delay=0.2):
    """分批计算动量因子"""
    momentum_data = {}
    failed_codes = []
    total = len(stock_codes)
    
    # 使用缓存
    for code in stock_codes:
        if code in existing_cache:
            momentum_data[code] = existing_cache[code]
    
    to_calculate = [c for c in stock_codes if c not in momentum_data]
    logger.info(f"  缓存命中: {len(momentum_data)} 只, 需要计算: {len(to_calculate)} 只")
    
    if not to_calculate:
        return momentum_data, failed_codes
    
    for i in range(0, len(to_calculate), batch_size):
        batch = to_calculate[i:i+batch_size]
        batch_num = i // batch_size + 1
        batch_total = (len(to_calculate) + batch_size - 1) // batch_size
        
        logger.info(f"  计算批次 {batch_num}/{batch_total}")
        
        for code in batch:
            try:
                c5, c10, c20 = calculate_single_momentum(code)
                if c5 is not None or c10 is not None or c20 is not None:
                    momentum_data[code] = {'change_5d': c5, 'change_10d': c10, 'change_20d': c20}
                else:
                    failed_codes.append(code)
                time.sleep(delay)
            except Exception as e:
                failed_codes.append(code)
        
        if batch_num % 10 == 0:
            save_momentum_cache(momentum_data)
    
    return momentum_data, failed_codes


def sync_stock_screening_data(force=False, include_momentum=True, batch_size=30):
    """同步多因子选股数据
    
    策略：
    1. 优先使用 tushare 获取数据
    2. akshare 作为备选
    3. 动量因子使用缓存+增量
    """
    today = date.today()
    
    if not force and not is_trading_day():
        logger.info("非交易日，跳过")
        return {"success": False, "message": "非交易日"}
    
    logger.info(f"开始同步多因子数据... 日期: {today}")
    start_time = time.time()
    
    # ========== 步骤1: 获取实时行情数据 ==========
    df = get_all_a_stocks_tushare()
    
    if df is None or df.empty:
        logger.info("tushare失败，尝试akshare...")
        df = get_all_a_stocks_akshare()
    
    if df is None or df.empty:
        return {"success": False, "message": "无法获取实时行情数据"}
    
    df.columns = [c.strip() for c in df.columns]
    
    pe_count = df['pe'].notna().sum() if 'pe' in df.columns else 0
    pb_count = df['pb'].notna().sum() if 'pb' in df.columns else 0
    
    logger.info(f"PE数据: {pe_count} 条, PB数据: {pb_count} 条")
    logger.info(f"总计 {len(df)} 只股票")
    
    # ========== 步骤2: 动量因子 ==========
    momentum_data = {}
    if include_momentum:
        logger.info("📊 计算动量因子 (缓存+增量)...")
        existing_cache = load_momentum_cache()
        logger.info(f"  已加载缓存: {len(existing_cache)} 条")
        
        stock_codes = df['代码'].astype(str).str.zfill(6).tolist()
        momentum_data, failed = calculate_momentum_batch(
            stock_codes, existing_cache, batch_size=batch_size
        )
        save_momentum_cache(momentum_data)
        logger.info(f"  动量因子计算完成: {len(momentum_data)} 只")
    
    # ========== 步骤3: 处理数据 ==========
    stock_data = []
    
    for _, row in df.iterrows():
        code = str(row.get('代码', '')).strip()
        if not code:
            continue
        
        # 市值转换
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
            'pe': safe_decimal(row.get('pe')),
            'pb': safe_decimal(row.get('pb')),
            'ps': safe_decimal(row.get('ps')),
            # 动量因子
            'change_5d': momentum.get('change_5d'),
            'change_10d': momentum.get('change_10d'),
            'change_20d': momentum.get('change_20d'),
            'change_60d': safe_decimal(row.get('60日涨跌幅')),
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
            'fetch_time': datetime.now(),
        }
        stock_data.append(record)
    
    # ========== 步骤4: 保存到数据库 ==========
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


def main():
    import argparse
    parser = argparse.ArgumentParser(description='多因子选股数据同步')
    parser.add_argument('--force', '-f', action='store_true', help='强制跳过交易日')
    parser.add_argument('--no-momentum', action='store_true', help='不计算动量因子')
    parser.add_argument('--batch-size', '-b', type=int, default=30, help='每批计算数量')
    args = parser.parse_args()
    
    from app import app
    with app.app_context():
        print("=" * 50)
        print("多因子选股数据同步 (tushare + akshare)")
        print("=" * 50)
        result = sync_stock_screening_data(
            force=args.force, 
            include_momentum=not args.no_momentum,
            batch_size=args.batch_size
        )
        print(f"\n结果: {result}")


if __name__ == '__main__':
    main()
