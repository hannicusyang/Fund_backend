from flask import Blueprint, jsonify, request
import akshare as ak
from datetime import datetime, timedelta
import pandas as pd
stock_realtime_bp = Blueprint('stock_realtime', __name__)

# 缓存数据
_cache = {
    'data': None,
    'last_update': None
}
CACHE_DURATION = timedelta(seconds=30)  # 30秒缓存


def get_cached_realtime_data():
    """获取缓存的实时数据，如果过期则重新获取"""
    now = datetime.now()
    if _cache['data'] is None or _cache['last_update'] is None or \
       (now - _cache['last_update']) > CACHE_DURATION:
        try:
            df = ak.stock_zh_a_spot_em()
            _cache['data'] = df
            _cache['last_update'] = now
        except Exception as e:
            print(f"获取实时数据失败: {e}")
            if _cache['data'] is None:
                raise
    return _cache['data']


def convert_to_api_format(df):
    """将akshare数据转换为API格式"""
    result = []
    for _, row in df.iterrows():
        result.append({
            'index': int(row['序号']) if '序号' in row else 0,
            'code': str(row['代码']) if '代码' in row else '',
            'name': str(row['名称']) if '名称' in row else '',
            'latest_price': float(row['最新价']) if pd.notna(row.get('最新价')) else 0,
            'change_percent': float(row['涨跌幅']) if pd.notna(row.get('涨跌幅')) else 0,
            'change_amount': float(row['涨跌额']) if pd.notna(row.get('涨跌额')) else 0,
            'volume': float(row['成交量']) if pd.notna(row.get('成交量')) else 0,
            'turnover': float(row['成交额']) if pd.notna(row.get('成交额')) else 0,
            'amplitude': float(row['振幅']) if pd.notna(row.get('振幅')) else 0,
            'high': float(row['最高']) if pd.notna(row.get('最高')) else 0,
            'low': float(row['最低']) if pd.notna(row.get('最低')) else 0,
            'open': float(row['今开']) if pd.notna(row.get('今开')) else 0,
            'prev_close': float(row['昨收']) if pd.notna(row.get('昨收')) else 0,
            'volume_ratio': float(row['量比']) if pd.notna(row.get('量比')) else 0,
            'turnover_rate': float(row['换手率']) if pd.notna(row.get('换手率')) else 0,
            'pe_dynamic': float(row['市盈率-动态']) if pd.notna(row.get('市盈率-动态')) else None,
            'pb_ratio': float(row['市净率']) if pd.notna(row.get('市净率')) else None,
            'total_market_cap': float(row['总市值']) if pd.notna(row.get('总市值')) else 0,
            'circulating_market_cap': float(row['流通市值']) if pd.notna(row.get('流通市值')) else 0,
            'change_speed': float(row['涨速']) if pd.notna(row.get('涨速')) else 0,
            'change_5min': float(row['5分钟涨跌']) if pd.notna(row.get('5分钟涨跌')) else 0,
            'change_60d': float(row['60日涨跌幅']) if pd.notna(row.get('60日涨跌幅')) else 0,
            'change_ytd': float(row['年初至今涨跌幅']) if pd.notna(row.get('年初至今涨跌幅')) else 0,
        })
    return result


@stock_realtime_bp.route('/realtime', methods=['GET'])
def get_realtime_list():
    """获取所有A股实时行情"""
    try:
        import pandas as pd
        df = get_cached_realtime_data()
        data = convert_to_api_format(df)
        return jsonify({
            "success": True,
            "data": data,
            "message": "获取成功",
            "total": len(data)
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "data": [],
            "message": f"获取实时行情失败: {str(e)}"
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
        import pandas as pd
        df = get_cached_realtime_data()
        
        # 按代码或名称搜索
        keyword_lower = keyword.lower()
        mask = df['代码'].astype(str).str.lower().str.contains(keyword_lower) | \
               df['名称'].astype(str).str.lower().str.contains(keyword_lower)
        filtered_df = df[mask].head(20)  # 最多返回20条
        
        data = convert_to_api_format(filtered_df)
        return jsonify({
            "success": True,
            "data": data,
            "message": "搜索成功",
            "total": len(data)
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "data": [],
            "message": f"搜索失败: {str(e)}"
        }), 500


@stock_realtime_bp.route('/detail/<stock_code>', methods=['GET'])
def get_stock_detail(stock_code):
    """获取单只股票详情"""
    try:
        import pandas as pd
        df = get_cached_realtime_data()
        
        stock = df[df['代码'].astype(str) == stock_code]
        if stock.empty:
            return jsonify({
                "success": False,
                "data": None,
                "message": "股票不存在"
            }), 404
        
        data = convert_to_api_format(stock)
        return jsonify({
            "success": True,
            "data": data[0] if data else None,
            "message": "获取成功"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "data": None,
            "message": f"获取详情失败: {str(e)}"
        }), 500