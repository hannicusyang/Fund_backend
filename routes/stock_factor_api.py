# routes/stock_factor_api.py
# 多因子选股API

from flask import Blueprint, request, jsonify
from utils.auth import get_current_user_id_or_default
from services.stock_factor_service import StockFactorService
import time

stock_factor_bp = Blueprint('stock_factor', __name__)


def success_response(data=None, message="success"):
    return jsonify({
        "success": True,
        "code": 200,
        "message": message,
        "data": data,
        "timestamp": int(time.time())
    })


def error_response(message="error", code=500):
    return jsonify({
        "success": False,
        "code": code,
        "message": message,
        "data": None,
        "timestamp": int(time.time())
    }), code


@stock_factor_bp.route('/api/stock/factors', methods=['GET'])
def get_factors():
    """获取所有因子定义"""
    try:
        factors = StockFactorService.get_factor_definitions()
        return success_response(factors)
    except Exception as e:
        return error_response(str(e))


@stock_factor_bp.route('/api/stock/quick-filters', methods=['GET'])
def get_quick_filters():
    """获取快捷筛选预设"""
    try:
        filters = StockFactorService.get_quick_filters()
        return success_response(filters)
    except Exception as e:
        return error_response(str(e))


@stock_factor_bp.route('/api/stock/screen', methods=['POST', 'GET'])
def screen_stocks():
    """多因子选股筛选"""
    try:
        if request.method == 'POST':
            data = request.json or {}
        else:
            data = request.args.to_dict()
            import json
            filters_str = data.get('filters', '{}')
            try:
                data['filters'] = json.loads(filters_str)
            except:
                data['filters'] = {}
        
        filters = data.get('filters', {})
        sort_by = data.get('sortBy', 'change_20d')
        sort_order = data.get('sortOrder', 'desc')
        page = int(data.get('page', 1))
        page_size = int(data.get('pageSize', 20))
        
        # 调试日志
        print(f"[API] filters={filters}, sort_by={sort_by}, sort_order={sort_order}")
        
        result = StockFactorService.screen_stocks(
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size
        )
        
        if result['success']:
            return success_response({
                'list': result['data'],
                'total': result['total'],
                'page': result['page'],
                'pageSize': result['pageSize'],
                'tradeDate': result.get('tradeDate')
            })
        else:
            return error_response(result['message'])
            
    except Exception as e:
        return error_response(str(e))


@stock_factor_bp.route('/api/stock/strategies', methods=['GET'])
def get_strategies():
    """获取用户的筛选策略列表"""
    try:
        user_id = get_current_user_id_or_default()
        strategies = StockFactorService.get_strategies(user_id)
        return success_response(strategies)
    except Exception as e:
        return error_response(str(e))


@stock_factor_bp.route('/api/stock/strategies', methods=['POST'])
def save_strategy():
    """保存筛选策略"""
    try:
        data = request.json or {}
        
        user_id = get_current_user_id_or_default()
        name = data.get('name')
        description = data.get('description', '')
        factors = data.get('factors', {})
        sort_by = data.get('sortBy', 'change_20d')
        sort_order = data.get('sortOrder', 'desc')
        limit = data.get('limit', 50)
        
        if not name:
            return error_response('策略名称不能为空', 400)
        
        result = StockFactorService.save_strategy(
            user_id=user_id,
            name=name,
            description=description,
            factor_config={'factors': factors},
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit
        )
        
        if result['success']:
            return success_response(result['data'])
        else:
            return error_response(result['message'])
            
    except Exception as e:
        return error_response(str(e))


@stock_factor_bp.route('/api/stock/strategies/<int:strategy_id>', methods=['DELETE'])
def delete_strategy(strategy_id):
    """删除策略"""
    try:
        user_id = get_current_user_id_or_default()
        result = StockFactorService.delete_strategy(strategy_id, user_id)
        
        if result['success']:
            return success_response(None, '删除成功')
        else:
            return error_response(result['message'])
            
    except Exception as e:
        return error_response(str(e))
