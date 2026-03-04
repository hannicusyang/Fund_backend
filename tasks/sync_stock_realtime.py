"""
股票实时行情数据同步任务
数据源: tushare (第三方代理) > akshare > 其他
"""
import akshare as ak
import pandas as pd
from datetime import datetime, date, time
from config.logging_config import logger
from models import db
from models.stock_estimation import StockEstimation
from models.trading_day import TradingDay

# 导入tushare工具
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.tushare_api import get_pro, get_stock_list, get_daily_basic_full, get_daily, get_daily_batch, get_trade_cal


def is_trading_time():
    """判断当前是否为A股交易时间（查数据库 + 时间段检查）"""
    now = datetime.now()
    today = now.date()
    current_time = now.time()
    
    # 检查交易时段: 9:30-11:30, 13:00-15:00
    is_trading_hours = (
        (time(9, 30) <= current_time <= time(11, 30)) or
        (time(13, 0) <= current_time <= time(15, 0))
    )
    
    if not is_trading_hours:
        return False
    
    # 查数据库判断是否为交易日
    try:
        is_trading_day = db.session.query(
            db.exists().where(TradingDay.trade_date == today)
        ).scalar()
        return bool(is_trading_day)
    except Exception as e:
        logger.error(f"❌ 查询交易日失败: {e}")
        return False


def fetch_stock_tushare():
    """通过tushare获取实时行情 - 使用完整版接口获取全量数据"""
    try:
        logger.info("📡 正在获取股票实时行情(tushare)...")
        
        # 获取最近7天的交易日历
        from datetime import timedelta
        df_cal = get_trade_cal(
            start_date=(date.today() - timedelta(days=7)).strftime('%Y%m%d'),
            end_date=date.today().strftime('%Y%m%d')
        )
        
        if df_cal is not None and not df_cal.empty:
            df_cal = df_cal[df_cal['is_open'] == 1]
            if not df_cal.empty:
                # 查找最近有数据的交易日
                for trade_date in df_cal['cal_date'].tolist():
                    # 使用完整版接口获取全量数据
                    daily_data = get_daily_basic_full(trade_date, limit=6000)
                    if daily_data is not None and not daily_data.empty:
                        logger.info(f"✅ tushare获取成功，共 {len(daily_data)} 条 (日期: {trade_date})")
                        return daily_data, 'tushare'
                    else:
                        logger.info(f"⚠️ 日期 {trade_date} 无数据，继续...")
        
        return None, 'tushare'
        
    except Exception as e:
        logger.warning(f"tushare接口失败: {e}")
        import traceback
        traceback.print_exc()
        return None, 'tushare'


def fetch_stock_akshare():
    """通过akshare获取实时行情"""
    import requests
    
    # 尝试东方财富接口
    try:
        logger.info("📡 正在获取股票实时行情(东方财富)...")
        df = ak.stock_zh_a_spot_em()
        if df is not None and not df.empty:
            logger.info(f"✅ 东方财富接口获取成功，共 {len(df)} 条")
            return df, 'eastmoney'
    except Exception as e:
        logger.warning(f"东方财富接口失败: {e}")
    
    # 尝试新浪接口
    try:
        logger.info("📡 正在获取股票实时行情(新浪)...")
        df = ak.stock_zh_a_spot()
        if df is not None and not df.empty:
            logger.info(f"✅ 新浪接口获取成功，共 {len(df)} 条")
            return df, 'sina'
    except Exception as e:
        logger.warning(f"新浪接口失败: {e}")
    
    return None, 'akshare'


def fetch_stock_tencent():
    """通过腾讯接口获取实时行情"""
    import requests
    
    try:
        logger.info("📡 正在获取股票实时行情(腾讯)...")
        
        # 获取全部A股股票代码列表
        stock_codes = []
        
        # 尝试获取上证股票 (600000-603999)
        for i in range(600000, 604000):
            stock_codes.append(f'sh{i}')
        # 尝试获取深证股票 (000001-003000)
        for i in range(1, 3001):
            stock_codes.append(f'sz{i:06d}')
        
        # 批量获取（每次100个）
        all_data = []
        batch_size = 100
        
        for i in range(0, min(len(stock_codes), 500), batch_size):
            batch = stock_codes[i:i+batch_size]
            codes_str = ','.join(batch)
            url = f'https://qt.gtimg.cn/q={codes_str}'
            
            try:
                r = requests.get(url, timeout=30)
                if r.text and r.text != '\n':
                    for line in r.text.split('\n'):
                        if line.strip():
                            # 解析腾讯数据格式
                            # v_sh600519="1~贵州茅台~600519~1440.11~1455.02~1450.00~...
                            parts = line.split('=')
                            if len(parts) >= 2:
                                data = parts[1].replace('"', '').split('~')
                                if len(data) > 31:
                                    code = data[2]  # 股票代码
                                    name = data[1]  # 股票名称
                                    # 修正字段索引
                                    latest_price = float(data[5]) if data[5] else 0  # 当前价(索引5)
                                    pre_close = float(data[4]) if data[4] else 0  # 前收盘价(索引4)
                                    change_amount = float(data[30]) if len(data) > 30 and data[30] else 0  # 涨跌额
                                    change_percent = float(data[31]) if len(data) > 31 and data[31] else 0  # 涨跌幅
                                    volume = float(data[6]) if data[6] else 0  # 成交量(索引6)
                                    turnover = float(data[7]) if data[7] else 0  # 成交额(索引7)
                                    
                                    if latest_price > 0:  # 只保留有价格的
                                        all_data.append({
                                            'code': code,
                                            'name': name,
                                            'latest_price': latest_price,
                                            'pre_close': pre_close,
                                            'change_amount': change_amount,
                                            'change_percent': change_percent,
                                            'volume': volume,
                                            'turnover': turnover,
                                        })
            except Exception as e:
                logger.warning(f"腾讯批量获取失败: {e}")
                continue
        
        if all_data:
            df = pd.DataFrame(all_data)
            logger.info(f"✅ 腾讯接口获取成功，共 {len(df)} 条")
            return df, 'tencent'
            
    except Exception as e:
        logger.warning(f"腾讯接口失败: {e}")
    
    return None, 'tencent'


def fetch_stock_realtime():
    """获取A股实时行情数据（多数据源）"""
    
    # 优先尝试tushare
    df, source = fetch_stock_tushare()
    if df is not None and not df.empty:
        return df, source
    
    # 其次尝试akshare
    df, source = fetch_stock_akshare()
    if df is not None and not df.empty:
        return df, source
    
    # 最后尝试腾讯接口
    df, source = fetch_stock_tencent()
    if df is not None and not df.empty:
        return df, source
    
    raise Exception("所有接口失败")


def convert_to_db_format(df, source, trade_date):
    """将DataFrame转换为数据库记录格式"""
    records = []
    
    # 如果是tushare，先获取股票列表用于查找名称
    stock_name_map = {}
    if source == 'tushare':
        try:
            stock_list = get_stock_list(limit=6000)
            if stock_list is not None and not stock_list.empty:
                stock_name_map = dict(zip(stock_list['ts_code'], stock_list['name']))
                print(f"已加载 {len(stock_name_map)} 只股票名称")
        except Exception as e:
            print(f"获取股票列表失败: {e}")
    
    for _, row in df.iterrows():
        try:
            if source == 'tushare':
                # tushare数据格式
                ts_code = row.get('ts_code', '')
                code = ts_code.split('.')[0] if '.' in ts_code else ts_code
                
                # 获取股票名称
                stock_name = stock_name_map.get(ts_code, '')
                
                record = {
                    'stock_code': code,
                    'stock_name': stock_name,
                    'latest_price': _to_decimal(row.get('close')),
                    'change_amount': _to_decimal(row.get('change')) if row.get('change') is not None else (_to_decimal(row.get('close')) - _to_decimal(row.get('pre_close'))),  # 涨跌额
                    'change_percent': _to_decimal(row.get('pct_chg')),
                    'prev_close': _to_decimal(row.get('pre_close')),
                    'open_price': _to_decimal(row.get('open')),  # 开盘价
                    'high': _to_decimal(row.get('high')),  # 最高价
                    'low': _to_decimal(row.get('low')),  # 最低价
                    'volume': _to_decimal(row.get('vol')),  # 成交量
                    'turnover': _to_decimal(row.get('amount')),  # 成交额
                    'turnover_rate': _to_decimal(row.get('turnover_rate')),
                    'amplitude': None,
                    'volume_ratio': _to_decimal(row.get('volume_ratio')),
                    'pe_dynamic': _to_decimal(row.get('pe')),
                    'pb_ratio': _to_decimal(row.get('pb')),
                    'total_market_cap': _to_decimal(row.get('total_mv')),
                    'circulating_market_cap': _to_decimal(row.get('circ_mv')),
                    'change_speed': None,
                    'change_5min': None,
                    'change_60d': None,
                    'change_ytd': None,
                    'trade_date': trade_date,
                    'fetch_time': datetime.now()
                }
            elif source == 'sina':
                # 新浪数据格式处理
                record = {
                    'stock_code': str(row.get('代码', '')).replace('sh', '').replace('sz', ''),
                    'stock_name': str(row.get('名称', '')),
                    'latest_price': _to_decimal(row.get('最新价')),
                    'change_amount': _to_decimal(row.get('涨跌额')),
                    'change_percent': _to_decimal(row.get('涨跌幅')),
                    'prev_close': _to_decimal(row.get('昨收')),
                    'open_price': _to_decimal(row.get('今开')),
                    'high': _to_decimal(row.get('最高')),
                    'low': _to_decimal(row.get('最低')),
                    'volume': _to_decimal(row.get('成交量')),
                    'turnover': _to_decimal(row.get('成交额')),
                    'turnover_rate': _to_decimal(row.get('换手率')),
                    'amplitude': None,
                    'volume_ratio': None,
                    'pe_dynamic': None,
                    'pb_ratio': None,
                    'total_market_cap': None,
                    'circulating_market_cap': None,
                    'change_speed': None,
                    'change_5min': None,
                    'change_60d': None,
                    'change_ytd': None,
                    'trade_date': trade_date,
                    'fetch_time': datetime.now()
                }
            elif source == 'tencent':
                # 腾讯数据格式处理
                record = {
                    'stock_code': str(row.get('code', '')),
                    'stock_name': str(row.get('name', '')),
                    'latest_price': _to_decimal(row.get('latest_price')),
                    'change_percent': _to_decimal(row.get('change_percent')),
                    'change_amount': _to_decimal(row.get('change_amount')),
                    'volume': _to_decimal(row.get('volume')),
                    'turnover': _to_decimal(row.get('turnover')),
                    'amplitude': None,
                    'high': None,
                    'low': None,
                    'open_price': None,
                    'prev_close': _to_decimal(row.get('pre_close')),
                    'volume_ratio': None,
                    'turnover_rate': None,
                    'pe_dynamic': None,
                    'pb_ratio': None,
                    'total_market_cap': None,
                    'circulating_market_cap': None,
                    'change_speed': None,
                    'change_5min': None,
                    'change_60d': None,
                    'change_ytd': None,
                    'trade_date': trade_date,
                    'fetch_time': datetime.now()
                }
            else:
                # 东方财富数据格式处理
                record = {
                    'stock_code': str(row.get('代码', '')),
                    'stock_name': str(row.get('名称', '')),
                    'latest_price': _to_decimal(row.get('最新价')),
                    'change_percent': _to_decimal(row.get('涨跌幅')),
                    'change_amount': _to_decimal(row.get('涨跌额')),
                    'volume': _to_decimal(row.get('成交量')),
                    'turnover': _to_decimal(row.get('成交额')),
                    'amplitude': _to_decimal(row.get('振幅')),
                    'high': _to_decimal(row.get('最高')),
                    'low': _to_decimal(row.get('最低')),
                    'open_price': _to_decimal(row.get('今开')),
                    'prev_close': _to_decimal(row.get('昨收')),
                    'volume_ratio': _to_decimal(row.get('量比')),
                    'turnover_rate': _to_decimal(row.get('换手率')),
                    'pe_dynamic': _to_decimal(row.get('市盈率-动态')),
                    'pb_ratio': _to_decimal(row.get('市净率')),
                    'total_market_cap': _to_decimal(row.get('总市值')),
                    'circulating_market_cap': _to_decimal(row.get('流通市值')),
                    'change_speed': _to_decimal(row.get('涨速')),
                    'change_5min': _to_decimal(row.get('5分钟涨跌')),
                    'change_60d': _to_decimal(row.get('60日涨跌幅')),
                    'change_ytd': _to_decimal(row.get('年初至今涨跌幅')),
                    'trade_date': trade_date,
                    'fetch_time': datetime.now()
                }
            records.append(record)
        except Exception as e:
            logger.warning(f"处理单条数据失败: {e}")
            continue
    
    return records


def _to_decimal(value):
    """安全转换为Decimal"""
    if value is None or value == '' or pd.isna(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def clear_old_stock_data(batch_size=5000):
    """清理非今日的数据"""
    today = date.today()
    total_deleted = 0
    
    try:
        while True:
            ids = db.session.query(StockEstimation.id).filter(
                StockEstimation.trade_date != today
            ).limit(batch_size).all()
            
            if not ids:
                break
            
            id_list = [row.id for row in ids]
            deleted = StockEstimation.query.filter(
                StockEstimation.id.in_(id_list)
            ).delete(synchronize_session=False)
            db.session.commit()
            total_deleted += deleted
            logger.debug(f"🧹 删除 {deleted} 条旧股票数据")
        
        if total_deleted > 0:
            logger.info(f"✅ 清理完成：共删除 {total_deleted} 条旧数据")
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ 清理旧数据失败: {e}")


def sync_stock_realtime():
    """主同步函数：获取股票实时行情并写入数据库"""
    from app import app
    import traceback
    
    # 检查是否为交易时间
    if not is_trading_time():
        logger.debug("⏸️ 非交易时间，跳过股票实时行情同步")
        return
    
    with app.app_context():
        try:
            # 清理旧数据
            clear_old_stock_data()
            
            # 获取实时数据
            df, source = fetch_stock_realtime()
            
            # 转换为数据库格式
            trade_date = date.today()
            records = convert_to_db_format(df, source, trade_date)
            
            if not records:
                logger.warning("没有数据需要写入")
                return
            
            # 批量写入数据库
            batch_size = 1000
            total = len(records)
            
            for i in range(0, total, batch_size):
                batch = records[i:i + batch_size]
                objects = [StockEstimation(**rec) for rec in batch]
                db.session.bulk_save_objects(objects)
                db.session.commit()
                logger.debug(f"已写入批次 {i // batch_size + 1}/{(total - 1) // batch_size + 1}")
            
            logger.info(f"✅ 成功写入 {total} 条股票实时数据 | 来源: {source} | 日期: {trade_date}")
            
        except Exception as e:
            db.session.rollback()
            error_msg = str(e)[:100]
            logger.error(f"💥 同步失败: {error_msg}")
            logger.debug(f"详细错误: {traceback.format_exc()}")


# 兼容性导出
fetch_and_save_stock_realtime = sync_stock_realtime
