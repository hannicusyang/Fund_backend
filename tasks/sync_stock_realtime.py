"""
股票实时行情数据同步任务
定时从akshare获取A股实时行情并写入数据库
"""
import akshare as ak
import pandas as pd
from datetime import datetime, date, time
from config.logging_config import logger
from models import db
from models.stock_estimation import StockEstimation
from models.trading_day import TradingDay


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
        return False  # 安全起见返回 False


def fetch_stock_realtime():
    """获取A股实时行情数据"""
    import requests
    
    errors = []
    
    # 尝试新浪接口
    try:
        logger.info("📡 正在获取股票实时行情(新浪)...")
        df = ak.stock_zh_a_spot()
        logger.info(f"✅ 新浪接口获取成功，共 {len(df)} 条")
        return df, 'sina'
    except requests.exceptions.ConnectionError as e:
        errors.append(f"新浪连接失败")
        logger.warning(f"新浪接口连接失败")
    except Exception as e:
        error_msg = str(e)[:50]  # 截取前50字符
        errors.append(f"新浪:{error_msg}")
        logger.warning(f"新浪接口失败: {error_msg}")
    
    # 尝试东方财富接口
    try:
        logger.info("📡 正在获取股票实时行情(东方财富)...")
        df = ak.stock_zh_a_spot_em()
        logger.info(f"✅ 东方财富接口获取成功，共 {len(df)} 条")
        return df, 'eastmoney'
    except requests.exceptions.ConnectionError as e:
        errors.append(f"东财连接失败")
        logger.warning(f"东方财富接口连接失败")
    except Exception as e:
        error_msg = str(e)[:50]
        errors.append(f"东财:{error_msg}")
        logger.warning(f"东方财富接口失败: {error_msg}")
    
    # 都失败了，抛出简洁的错误
    raise Exception(f"所有接口失败: {'; '.join(errors)}")


def convert_to_db_format(df, source, trade_date):
    """将DataFrame转换为数据库记录格式"""
    records = []
    
    for _, row in df.iterrows():
        try:
            if source == 'sina':
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
                    'amplitude': None,  # 新浪没有
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
            # 只记录简洁错误，不打印完整堆栈
            error_msg = str(e)[:100]
            logger.error(f"💥 同步失败: {error_msg}")
            # 只在DEBUG级别记录详细堆栈
            logger.debug(f"详细错误: {traceback.format_exc()}")


# 兼容性导出
fetch_and_save_stock_realtime = sync_stock_realtime