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


def fetch_from_api():
    """从外部API获取股票数据 - 多数据源策略"""
    import requests
    errors = []
    
    # 数据源列表，按优先级排序
    data_sources = [
        # 主板A股
        ('东方财富全量', 'eastmoney', lambda: ak.stock_zh_a_spot_em()),
        ('上海A股', 'sh_a', lambda: ak.stock_sh_a_spot_em()),
        ('深圳A股', 'sz_a', lambda: ak.stock_sz_a_spot_em()),
        ('创业板', 'cy_a', lambda: ak.stock_cy_a_spot_em()),
        ('科创板', 'kc_a', lambda: ak.stock_kc_a_spot_em()),
        ('新股', 'new_a', lambda: ak.stock_new_a_spot_em()),
        ('腾讯', 'tencent', lambda: ak.stock_zh_a_spot_tx()),
        ('雪球', 'xueqiu', lambda: ak.stock_zh_a_spot_xq()),
        ('同花顺', 'ths', lambda: ak.stock_zh_a_spot_ths()),
        ('新浪1', 'sina', lambda: ak.stock_zh_a_spot()),
        ('新浪2', 'sina_s', lambda: ak.stock_zh_a_spot_sina()),
    ]
    
    for name, source_id, fetch_func in data_sources:
        try:
            print(f"[数据源] 尝试从{name}获取...")
            df = fetch_func()
            print(f"[数据源] {name}获取成功，共 {len(df)} 条")
            return df, source_id
        except requests.exceptions.ConnectionError:
            errors.append(f"{name}连接失败")
            print(f"[数据源] {name}连接失败")
        except Exception as e:
            error_msg = str(e)[:50]
            errors.append(f"{name}:{error_msg}")
            print(f"[数据源] {name}失败: {error_msg}")
    
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


def get_data_from_yesterday():
    """从数据库获取昨日股票数据作为后备"""
    try:
        from datetime import timedelta
        from models.stock_screening import StockScreeningData
        
        yesterday = date.today() - timedelta(days=1)
        
        # 找到最近的交易日数据
        latest_record = StockScreeningData.query.filter(
            StockScreeningData.trade_date <= yesterday
        ).order_by(StockScreeningData.trade_date.desc()).first()
        
        if not latest_record:
            print(f"[数据库] 昨日无数据")
            return None
        
        yesterday_date = latest_record.trade_date
        print(f"[数据库] 使用昨日({yesterday_date})数据")
        
        records = StockScreeningData.query.filter(
            StockScreeningData.trade_date == yesterday_date
        ).all()
        
        if not records:
            return None
        
        print(f"[数据库] 获取昨日 {len(records)} 条数据")
        
        # 转换为API格式
        result = []
        for r in records:
            result.append({
                'code': r.stock_code,
                'name': r.stock_name,
                'latest_price': r.latest_price,
                'change_percent': r.change_percent,
                'change_amount': r.change_amount,
                'open': r.open_price,
                'high': r.high,
                'low': r.low,
                'volume': r.volume,
                'turnover': r.turnover,
                'turnover_rate': r.turnover_rate,
                'pre_close': r.pre_close,
                'trade_date': r.trade_date,
                'fetch_time': str(r.fetch_time) if r.fetch_time else None
            })
        
        return result, 'screening_db'
        
    except Exception as e:
        print(f"[数据库] 查询昨日数据失败: {e}")
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
    """将DataFrame转换为API格式 - 支持多数据源"""
    result = []
    
    # 各数据源列名映射
    column_maps = {
        'sina': {
            'code': '代码', 'name': '名称', 'latest_price': '最新价',
            'change_amount': '涨跌额', 'change_percent': '涨跌幅',
            'prev_close': '昨收', 'open': '今开', 'high': '最高', 'low': '最低',
            'volume': '成交量', 'turnover': '成交额', 'turnover_rate': '换手率'
        },
        'sina_s': {
            'code': '代码', 'name': '名称', 'latest_price': '最新价',
            'change_amount': '涨跌额', 'change_percent': '涨跌幅',
            'prev_close': '昨收', 'open': '今开', 'high': '最高', 'low': '最低',
            'volume': '成交量', 'turnover': '成交额', 'turnover_rate': '换手率'
        },
        'eastmoney': {
            'code': '代码', 'name': '名称', 'latest_price': '最新价',
            'change_percent': '涨跌幅', 'change_amount': '涨跌额',
            'volume': '成交量', 'turnover': '成交额', 'amplitude': '振幅',
            'high': '最高', 'low': '最低', 'open': '今开', 'prev_close': '昨收',
            'volume_ratio': '量比', 'turnover_rate': '换手率',
            'pe_dynamic': '市盈率-动态', 'pb_ratio': '市净率',
            'total_market_cap': '总市值', 'circulating_market_cap': '流通市值',
            'change_speed': '涨速', 'change_5min': '5分钟涨跌',
            'change_60d': '60日涨跌幅', 'change_ytd': '年初至今涨跌幅'
        },
        'tencent': {
            'code': '代码', 'name': '名称', 'latest_price': '最新价',
            'change_amount': '涨跌额', 'change_percent': '涨跌幅',
            'prev_close': '昨收', 'open': '今开', 'high': '最高', 'low': '最低',
            'volume': '成交量', 'turnover': '成交额'
        },
        'xueqiu': {
            'code': '代码', 'name': '名称', 'latest_price': '最新价',
            'change_percent': '涨跌幅', 'change_amount': '涨跌额',
            'volume': '成交量', 'turnover': '成交额',
            'high': '最高', 'low': '最低', 'open': '今开', 'prev_close': '昨收',
            'turnover_rate': '换手率', 'pe_ttm': '市盈率(TTM)',
            'total_market_cap': '总市值', 'circulating_market_cap': '流通市值'
        },
        'ths': {
            'code': '代码', 'name': '名称', 'latest_price': '最新价',
            'change_percent': '涨跌幅', 'change_amount': '涨跌额',
            'volume': '成交量', 'turnover': '成交额',
            'high': '最高', 'low': '最低', 'open': '今开', 'prev_close': '昨收',
            'turnover_rate': '换手率', 'pe': '市盈率',
            'total_market_cap': '总市值', 'circulating_market_cap': '流通市值'
        }
    }
    
    col_map = column_maps.get(source, column_maps['eastmoney'])
    
    for _, row in df.iterrows():
        try:
            # 清理代码（去除sh/sz前缀）
            code = str(row.get(col_map['code'], ''))
            # 移除 sh/sz 前缀（新浪、雪球、同花顺等可能有）
            code = code.replace('sh', '').replace('sz', '').replace('SH', '').replace('SZ', '')
            
            item = {
                'index': 0,
                'code': code,
                'name': str(row.get(col_map['name'], '')),
                'latest_price': _parse_float(row.get(col_map.get('latest_price'))),
                'change_percent': _parse_float(row.get(col_map.get('change_percent'))),
                'change_amount': _parse_float(row.get(col_map.get('change_amount'))),
                'volume': _parse_float(row.get(col_map.get('volume'))),
                'turnover': _parse_float(row.get(col_map.get('turnover'))),
                'high': _parse_float(row.get(col_map.get('high'))),
                'low': _parse_float(row.get(col_map.get('low'))),
                'open': _parse_float(row.get(col_map.get('open'))),
                'prev_close': _parse_float(row.get(col_map.get('prev_close'))),
                'turnover_rate': _parse_float(row.get(col_map.get('turnover_rate'))),
                # 以下字段可能不存在，设为None
                'amplitude': _parse_float(row.get(col_map.get('amplitude'))) if 'amplitude' in col_map else None,
                'volume_ratio': _parse_float(row.get(col_map.get('volume_ratio'))) if 'volume_ratio' in col_map else None,
                'pe_dynamic': _parse_float(row.get(col_map.get('pe_dynamic'))) if 'pe_dynamic' in col_map else None,
                'pb_ratio': _parse_float(row.get(col_map.get('pb_ratio'))) if 'pb_ratio' in col_map else None,
                'total_market_cap': _parse_float(row.get(col_map.get('total_market_cap'))) if 'total_market_cap' in col_map else None,
                'circulating_market_cap': _parse_float(row.get(col_map.get('circulating_market_cap'))) if 'circulating_market_cap' in col_map else None,
                'change_speed': _parse_float(row.get(col_map.get('change_speed'))) if 'change_speed' in col_map else None,
                'change_5min': _parse_float(row.get(col_map.get('change_5min'))) if 'change_5min' in col_map else None,
                'change_60d': _parse_float(row.get(col_map.get('change_60d'))) if 'change_60d' in col_map else None,
                'change_ytd': _parse_float(row.get(col_map.get('change_ytd'))) if 'change_ytd' in col_map else None,
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
    2. 数据库没有则从筛选数据表获取昨日数据
    """
    # 1. 先尝试从数据库获取今日数据
    db_result = get_data_from_db()
    if db_result:
        return db_result[0], db_result[1], 'db'
    
    # 2. 今日无数据，获取昨日筛选数据作为后备
    print("[数据源] 今日无数据，尝试获取昨日筛选数据...")
    yesterday_result = get_data_from_yesterday()
    if yesterday_result:
        return yesterday_result[0], yesterday_result[1], 'screening_db'
    
    raise Exception("无法获取股票数据")


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