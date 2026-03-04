# utils/tushare_api.py
# Tushare API 统一封装 - 使用第三方代理绕过积分限制

import tushare as ts
import pandas as pd
import time
from config.logging_config import logger

# 第三方代理配置
TUSHARE_TOKEN = '4502105893002009438'
TUSHARE_PROXY = 'http://5k1a.xiximiao.com/dataapi'

# 缓存pro对象
_pro = None


def get_pro():
    """获取tushare pro接口（单例）"""
    global _pro
    if _pro is None:
        _pro = ts.pro_api('dummy')
        _pro._DataApi__token = TUSHARE_TOKEN
        _pro._DataApi__http_url = TUSHARE_PROXY
    return _pro


def get_stock_list(limit=6000):
    """获取A股股票列表"""
    pro = get_pro()
    df = pro.stock_basic(limit=limit, offset=0)
    # 只保留沪深A股
    df = df[df['ts_code'].str.endswith(('.SH', '.SZ'))]
    return df


def get_daily_basic_full(trade_date, limit=6000):
    """获取每日指标数据（包含涨跌幅和行情）- 完整版"""
    pro = get_pro()
    all_data = []
    
    # 获取每日指标数据
    for offset in range(0, limit, 1000):
        try:
            df = pro.daily_basic(trade_date=trade_date, limit=1000, offset=offset)
            if df is None or df.empty:
                break
            all_data.append(df)
            time.sleep(0.15)
        except Exception as e:
            logger.warning(f"获取daily_basic失败 (offset={offset}): {e}")
            break
    
    if not all_data:
        return pd.DataFrame()
    
    result = pd.concat(all_data, ignore_index=True)
    logger.info(f"daily_basic获取 {len(result)} 条")
    
    # 获取涨跌幅和行情数据（从daily接口）
    try:
        ts_codes = result['ts_code'].tolist()
        daily_data = []
        
        # 批量获取daily，每次50只
        for i in range(0, min(len(ts_codes), 5000), 50):
            batch = ts_codes[i:i+50]
            try:
                df_daily = pro.daily(ts_code=','.join(batch), start_date=trade_date, end_date=trade_date)
                if df_daily is not None and not df_daily.empty:
                    daily_data.append(df_daily)
                time.sleep(0.1)
            except:
                pass
        
        if daily_data:
            daily_df = pd.concat(daily_data, ignore_index=True)
            # 合并需要的字段（包含change涨跌额）
            merge_cols = ['ts_code', 'open', 'high', 'low', 'pre_close', 'vol', 'amount', 'pct_chg', 'change']
            exist_cols = [c for c in merge_cols if c in daily_df.columns]
            if exist_cols:
                result = result.merge(daily_df[exist_cols], on='ts_code', how='left')
                logger.info(f"合并daily数据后共 {len(result)} 条")
    except Exception as e:
        logger.warning(f"获取daily数据失败: {e}")
    
    return result


# 兼容旧版本
get_daily_basic = get_daily_basic_full


def get_daily(ts_code, start_date, end_date):
    """获取日K线数据"""
    pro = get_pro()
    try:
        return pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
    except Exception as e:
        logger.warning(f"获取daily失败 {ts_code}: {e}")
        return pd.DataFrame()


def get_daily_batch(ts_codes, start_date, end_date):
    """批量获取多只股票的日K线"""
    pro = get_pro()
    all_data = []
    
    # tushare限制每次最多100只
    batch_size = 100
    for i in range(0, len(ts_codes), batch_size):
        batch = ts_codes[i:i+batch_size]
        try:
            # 使用 daily 接口批量获取
            for code in batch:
                df = pro.daily(ts_code=code, start_date=start_date, end_date=end_date)
                if df is not None and not df.empty:
                    all_data.append(df)
                time.sleep(0.1)
        except Exception as e:
            logger.warning(f"批量获取K线失败: {e}")
    
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return pd.DataFrame()


def get_realtime_quotes(codes):
    """获取实时行情"""
    pro = get_pro()
    try:
        if isinstance(codes, list):
            codes = codes[:50]
        return pro.realtime_quotes(codes)
    except Exception as e:
        logger.warning(f"获取realtime_quotes失败: {e}")
        return pd.DataFrame()


def get_trade_cal(start_date, end_date):
    """获取交易日历"""
    pro = get_pro()
    try:
        return pro.trade_cal(exchange='', start_date=start_date, end_date=end_date)
    except Exception as e:
        logger.warning(f"获取trade_cal失败: {e}")
        return pd.DataFrame()


def get_kpl_concept_cons(trade_date):
    """获取概念股成分（5000积分）"""
    pro = get_pro()
    try:
        return pro.kpl_concept_cons(trade_date=trade_date)
    except Exception as e:
        logger.warning(f"获取kpl_concept_cons失败: {e}")
        return pd.DataFrame()


def get_fina_indicator(ts_code, limit=10):
    """获取财务指标（需要2000+积分）"""
    pro = get_pro()
    try:
        return pro.fina_indicator(ts_code=ts_code, limit=limit)
    except Exception as e:
        logger.warning(f"获取fina_indicator失败: {e}")
        return pd.DataFrame()


def get_index_daily(ts_code, start_date, end_date):
    """获取指数日K线"""
    pro = get_pro()
    try:
        return pro.index_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
    except Exception as e:
        logger.warning(f"获取index_daily失败: {e}")
        return pd.DataFrame()


def get_moneyflow_hsgt(trade_date):
    """获取沪深港通资金流向"""
    pro = get_pro()
    try:
        return pro.moneyflow_hsgt(trade_date=trade_date)
    except Exception as e:
        logger.warning(f"获取moneyflow_hsgt失败: {e}")
        return pd.DataFrame()


def get_margin(trade_date):
    """获取融资融券数据"""
    pro = get_pro()
    try:
        return pro.margin(trade_date=trade_date)
    except Exception as e:
        logger.warning(f"获取margin失败: {e}")
        return pd.DataFrame()


def get_stock_zh_index_spot():
    """获取A股指数行情（tushare）"""
    pro = get_pro()
    try:
        return pro.index_basic()
    except Exception as e:
        logger.warning(f"获取index_basic失败: {e}")
        return pd.DataFrame()


def get_top_inst(trade_date):
    """获取龙虎榜机构明细"""
    pro = get_pro()
    try:
        return pro.top_inst(trade_date=trade_date)
    except Exception as e:
        logger.warning(f"获取top_inst失败: {e}")
        return pd.DataFrame()


def get_moneyflow(trade_date):
    """获取资金流向数据"""
    pro = get_pro()
    try:
        return pro.moneyflow(trade_date=trade_date)
    except Exception as e:
        logger.warning(f"获取moneyflow失败: {e}")
        return pd.DataFrame()


def get_block_trade(start_date, end_date):
    """获取大宗交易数据"""
    pro = get_pro()
    try:
        return pro.block_trade(start_date=start_date, end_date=end_date)
    except Exception as e:
        logger.warning(f"获取block_trade失败: {e}")
        return pd.DataFrame()


def get_news():
    """获取财经新闻头条"""
    pro = get_pro()
    try:
        # Tushare pro 的 news 接口
        return pro.news(channel='all', start_date=None, end_date=None)
    except Exception as e:
        logger.warning(f"获取news失败: {e}")
        return pd.DataFrame()


def get_fund_news():
    """获取基金新闻"""
    pro = get_pro()
    try:
        return pro.news(channel='fund', start_date=None, end_date=None)
    except Exception as e:
        logger.warning(f"获取fund_news失败: {e}")
        return pd.DataFrame()


def get_stock_news():
    """获取股票新闻"""
    pro = get_pro()
    try:
        return pro.news(channel='stock', start_date=None, end_date=None)
    except Exception as e:
        logger.warning(f"获取stock_news失败: {e}")
        return pd.DataFrame()


def get_macro_news():
    """获取宏观新闻"""
    pro = get_pro()
    try:
        return pro.news(channel='macro', start_date=None, end_date=None)
    except Exception as e:
        logger.warning(f"获取macro_news失败: {e}")
        return pd.DataFrame()
