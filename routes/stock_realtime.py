from flask import Blueprint, jsonify, request
import akshare as ak
import pandas as pd
from datetime import datetime, date, timedelta
from functools import wraps
from models import db
from models.stock_estimation import StockEstimation

stock_realtime_bp = Blueprint('stock_realtime', __name__)

# 外部API缓存
_api_cache = {
    'data': None,
    'last_update': None,
    'source': None
}
API_CACHE_DURATION = timedelta(seconds=30)
MAX_RETRIES = 3
RETRY_DELAY = 1


def retry_on_failure(max_retries=MAX_RETRIES, delay=RETRY_DELAY):
    """重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    print(f"第 {attempt + 1} 次尝试失败: {e}")
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(delay * (attempt + 1))
            raise last_exception
        return wrapper
    return decorator


@retry_on_failure(max_retries=2, delay=1)
def fetch_from_sina():
    """从新浪获取实时行情"""
    print("[数据源] 尝试从新浪获取...")
    df = ak.stock_zh_a_spot()
    print(f"[数据源] 新浪获取成功，共 {len(df)} 条")
    return df, 'sina'


@retry_on_failure(max_retries=2, delay=1)
def fetch_from_em():
    """从东方财富获取实时行情"""
    print("[数据源] 尝试从东方财富获取...")
    df = ak.stock_zh_a_spot_em()
    print(f"[数据源] 东方财富获取成功，共 {len(df)} 条")
    return df, 'eastmoney'


def fetch_from_api():
    """从外部API获取股票数据"""
    errors = []
    
    try:
        return fetch_from_sina()
    except Exception as e:
        errors.append(f"新浪: {str(e)}")
        print(f"新浪接口失败: {e}")
    
    try:
        return fetch_from_em()
    except Exception as e:
        errors.append(f"东方财富: {str(e)}")
        print(f"东方财富接口失败: {e}")
    
    raise Exception(f"所有数据源都失败: {'; '.join(errors)}")


def get_data_from_db():
    """从数据库获取今日最新股票数据"""
    try:
        today = date.today()
        
        # 获取今日最新数据（按fetch_time倒序取最新的一批）
        # 先找到最新的fetch_time
        latest_record = StockEstimation.query.filter(
            StockEstimation.trade_date == today
        ).order_by(StockEstimation.fetch_time.desc()).first()
        
        if not latest_record:
            print(f"[数据库] 今日({today})无数据")
            return None
        
        # 获取同一批次的数据（5分钟内）
        latest_time = latest_record.fetch_time
        time_threshold = latest_time - timedelta(minutes=5)
        
        records = StockEstimation.query.filter(
            StockEstimation.trade_date == today,
            StockEstimation.fetch_time >= time_threshold
        ).all()
        
        if not records:
            return None
        
        print(f"[数据库] 获取到 {len(records)} 条数据，最新时间: {latest_time}")
        return db_records_to_api_format(records), 'database'
        
    except Exception as e:
        print(f"[数据库] 查询失败: {e}")
        return None


def db_records_to_api_format(records):
    """将数据库记录转换为API格式"""
    result = []
    for record in records:
        result.append({
            'index': 0,
            'code': record.stock_code,
            'name': record.stock_name,
            'latest_price': float(record.latest_price) if record.latest_price else 0,
            'change_percent': float(record.change_percent) if record.change_percent else 0,
            'change_amount': float(record.change_amount) if record.change_amount else 0,
            'volume': float(record.volume) if record.volume else 0,
            'turnover': float(record.turnover) if record.turnover else 0,
            'amplitude': float(record.amplitude) if record.amplitude else None,
            'high': float(record.high) if record.high else 0,
            'low': float(record.low) if record.low else 0,
            'open': float(record.open_price) if record.open_price else 0,
            'prev_close': float(record.prev_close) if record.prev_close else 0,
            'volume_ratio': float(record.volume_ratio) if record.volume_ratio else None,
            'turnover_rate': float(record.turnover_rate) if record.turnover_rate else None,
            'pe_dynamic': float(record.pe_dynamic) if record.pe_dynamic else None,
            'pb_ratio': float(record.pb_ratio) if record.pb_ratio else None,
            'total_market_cap': float(record.total_market_cap) if record.total_market_cap else 0,
            'circulating_market_cap': float(record.circulating_market_cap) if record.circulating_market_cap else 0,
            'change_speed': float(record.change_speed) if record.change_speed else None,
            'change_5min': float(record.change_5min) if record.change_5min else None,
            'change_60d': float(record.change_60d) if record.change_60d else None,
            'change_ytd': float(record.change_ytd) if record.change_ytd else None,
            'fetch_time': record.fetch_time.isoformat() if record.fetch_time else None
        })
    return result


def get_cached_api_data():
    """获取外部API的缓存数据"""
    now = datetime.now()
    if _api_cache['data'] is None or _api_cache['last_update'] is None or \
       (now - _api_cache['last_update']) > API_CACHE_DURATION:
        try:
            df, source = fetch_from_api()
            _api_cache['data'] = df
            _api_cache['last_update'] = now
            _api_cache['source'] = source
        except Exception as e:
            print(f"[外部API] 获取失败: {e}")
            if _api_cache['data'] is not None and _api_cache['last_update'] is not None:
                if (now - _api_cache['last_update']) < timedelta(minutes=5):
                    print(f"[降级] 使用API缓存数据")
                    return _api_cache['data'], _api_cache['source']
            raise
    return _api_cache['data'], _api_cache['source']


def df_to_api_format(df, source):
    """将DataFrame转换为API格式"""
    result = []
    
    for _, row in df.iterrows():
        try:
            if source == 'sina':
                # 新浪格式
                item = {
                    'index': 0,
                    'code': str(row.get('代码', '')).replace('sh', '').replace('sz', ''),
                    'name': str(row.get('名称', '')),
                    'latest_price': _parse_float(row.get('最新价')),
                    'change_amount': _parse_float(row.get('涨跌额')),
                    'change_percent': _parse_float(row.get('涨跌幅')),
                    'prev_close': _parse_float(row.get('昨收')),
                    'open': _parse_float(row.get('今开')),
                    'high': _parse_float(row.get('最高')),
                    'low': _parse_float(row.get('最低')),
                    'volume': _parse_float(row.get('成交量')),
                    'turnover': _parse_float(row.get('成交额')),
                    'turnover_rate': _parse_float(row.get('换手率')),
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
                }
            else:
                # 东方财富格式
                item = {
                    'index': int(row['序号']) if '序号' in row and pd.notna(row['序号']) else 0,
                    'code': str(row['代码']) if '代码' in row and pd.notna(row['代码']) else '',
                    'name': str(row['名称']) if '名称' in row and pd.notna(row['名称']) else '',
                    'latest_price': _parse_float(row.get('最新价')),
                    'change_percent': _parse_float(row.get('涨跌幅')),
                    'change_amount': _parse_float(row.get('涨跌额')),
                    'volume': _parse_float(row.get('成交量')),
                    'turnover': _parse_float(row.get('成交额')),
                    'amplitude': _parse_float(row.get('振幅')),
                    'high': _parse_float(row.get('最高')),
                    'low': _parse_float(row.get('最低')),
                    'open': _parse_float(row.get('今开')),
                    'prev_close': _parse_float(row.get('昨收')),
                    'volume_ratio': _parse_float(row.get('量比')),
                    'turnover_rate': _parse_float(row.get('换手率')),
                    'pe_dynamic': _parse_float(row.get('市盈率-动态')),
                    'pb_ratio': _parse_float(row.get('市净率')),
                    'total_market_cap': _parse_float(row.get('总市值')),
                    'circulating_market_cap': _parse_float(row.get('流通市值')),
                    'change_speed': _parse_float(row.get('涨速')),
                    'change_5min': _parse_float(row.get('5分钟涨跌')),
                    'change_60d': _parse_float(row.get('60日涨跌幅')),
                    'change_ytd': _parse_float(row.get('年初至今涨跌幅')),
                }
            result.append(item)
        except Exception as e:
            continue
    
    return result


def _parse_float(value):
    """安全解析浮点数"""
    if value is None or value == '':
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def get_stock_data():
    """
    获取股票数据的完整逻辑：
    1. 优先从数据库读取今日数据
    2. 数据库没有则请求外部API
    3. 外部API失败则返回错误
    """
    # 1. 先尝试从数据库获取
    db_result = get_data_from_db()
    if db_result:
        return db_result[0], db_result[1], 'db'  # data, source, cache_type
    
    # 2. 数据库没有，从外部API获取
    print("[数据源] 数据库无数据，尝试外部API...")
    try:
        df, source = get_cached_api_data()
        data = df_to_api_format(df, source)
        return data, source, 'api'
    except Exception as e:
        raise Exception(f"数据库无数据且外部API失败: {str(e)}")


@stock_realtime_bp.route('/realtime', methods=['GET'])
def get_realtime_list():
    """获取所有A股实时行情"""
    try:
        data, source, cache_type = get_stock_data()
        
        # 获取数据时间
        data_time = None
        if cache_type == 'db' and data:
            # 从第一条记录的fetch_time获取
            data_time = data[0].get('fetch_time')
        
        return jsonify({
            "success": True,
            "data": data,
            "message": "获取成功",
            "total": len(data),
            "source": source,
            "cache_type": cache_type,  # 'db' 或 'api'
            "data_time": data_time
        })
    except Exception as e:
        error_msg = str(e)
        print(f"获取实时行情失败: {error_msg}")
        return jsonify({
            "success": False,
            "data": [],
            "message": f"获取实时行情失败: {error_msg}",
            "source": None,
            "cache_type": None
        }), 500


@stock_realtime_bp.route('/search', methods=['GET'])
def search_stocks():
    """搜索股票"""
    keyword = request.args.get('keyword', '').strip()
    if not keyword:
        return jsonify({
            "success": True,
            "data": [],
            "message": "请输入搜索关键词"
        })
    
    try:
        data, source, cache_type = get_stock_data()
        
        if not data:
            return jsonify({
                "success": False,
                "data": [],
                "message": "暂无股票数据"
            }), 500
        
        # 按代码或名称搜索
        keyword_lower = keyword.lower()
        filtered = [
            item for item in data
            if keyword_lower in item['code'].lower() or 
               keyword_lower in item['name'].lower()
        ]
        
        return jsonify({
            "success": True,
            "data": filtered[:20],  # 最多20条
            "message": "搜索成功",
            "total": len(filtered),
            "source": source,
            "cache_type": cache_type
        })
    except Exception as e:
        error_msg = str(e)
        print(f"搜索失败: {error_msg}")
        return jsonify({
            "success": False,
            "data": [],
            "message": f"搜索失败: {error_msg}"
        }), 500


@stock_realtime_bp.route('/detail/<stock_code>', methods=['GET'])
def get_stock_detail(stock_code):
    """获取单只股票详情"""
    try:
        data, source, cache_type = get_stock_data()
        
        if not data:
            return jsonify({
                "success": False,
                "data": None,
                "message": "暂无股票数据"
            }), 500
        
        # 查找股票
        stock = None
        for item in data:
            if item['code'] == stock_code:
                stock = item
                break
        
        if not stock:
            return jsonify({
                "success": False,
                "data": None,
                "message": "股票不存在"
            }), 404
        
        return jsonify({
            "success": True,
            "data": stock,
            "message": "获取成功",
            "source": source,
            "cache_type": cache_type
        })
    except Exception as e:
        error_msg = str(e)
        print(f"获取详情失败: {error_msg}")
        return jsonify({
            "success": False,
            "data": None,
            "message": f"获取详情失败: {error_msg}"
        }), 500