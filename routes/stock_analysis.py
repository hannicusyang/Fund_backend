# routes/stock_analysis.py
# 股票智能分析API

from flask import Blueprint, request, jsonify
from services.stock_analysis import (
    get_stock_analysis_service,
    analyze_stock_with_ai
)
from config.logging_config import logger
import traceback

stock_analysis_bp = Blueprint('stock_analysis', __name__)


@stock_analysis_bp.route('/ai-analysis', methods=['POST'])
def stock_ai_analysis():
    """
    股票AI分析接口
    
    请求参数:
    {
        "stock_codes": ["600519", "000858"],  # 股票代码列表
        "period": "1y"  # 分析周期
    }
    
    返回:
    {
        "success": true,
        "data": {
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "analysis_date": "2026-03-08",
            "综合评分": "78/100",
            ...
        }
    }
    """
    try:
        data = request.get_json() or {}
        stock_codes = data.get('stock_codes', [])
        period = data.get('period', '1y')
        
        if not stock_codes:
            return jsonify({'success': False, 'error': '请提供股票代码'}), 400
        
        service = get_stock_analysis_service()
        
        # 如果只有一个股票
        if len(stock_codes) == 1:
            stock_data = _get_stock_data(stock_codes[0], period)
            if not stock_data:
                return jsonify({'success': False, 'error': '股票数据不存在'}), 404
            
            result = service.analyze_stock(stock_data)
            return jsonify({'success': True, 'data': result})
        
        # 如果是多个股票
        stocks_data = [_get_stock_data(code, period) for code in stock_codes]
        stocks_data = [s for s in stocks_data if s]
        
        if not stocks_data:
            return jsonify({'success': False, 'error': '股票数据不存在'}), 404
        
        # 逐个分析
        results = []
        for stock_data in stocks_data:
            result = service.analyze_stock(stock_data)
            results.append(result)
        
        return jsonify({'success': True, 'data': results})
    
    except Exception as e:
        logger.error(f"股票AI分析异常: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@stock_analysis_bp.route('/technical-analysis', methods=['POST'])
def stock_technical_analysis():
    """
    股票技术分析接口
    
    请求参数:
    {
        "stock_code": "600519",
        "period": "1y"
    }
    """
    try:
        data = request.get_json() or {}
        stock_code = data.get('stock_code')
        period = data.get('period', '1y')
        
        if not stock_code:
            return jsonify({'success': False, 'error': '请提供股票代码'}), 400
        
        stock_data = _get_stock_data(stock_code, period)
        if not stock_data:
            return jsonify({'success': False, 'error': '股票数据不存在'}), 404
        
        service = get_stock_analysis_service()
        result = service.analyze_technical(stock_data)
        
        return jsonify({'success': True, 'data': result})
    
    except Exception as e:
        logger.error(f"股票技术分析异常: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@stock_analysis_bp.route('/report', methods=['GET'])
def stock_report():
    """
    生成股票分析报告
    
    参数:
    - stock_code: 股票代码
    - type: 报告类型 (pdf/html/json)
    """
    try:
        stock_code = request.args.get('stock_code')
        report_type = request.args.get('type', 'json')
        period = request.args.get('period', '1y')
        
        if not stock_code:
            return jsonify({'success': False, 'error': '请提供股票代码'}), 400
        
        stock_data = _get_stock_data(stock_code, period)
        if not stock_data:
            return jsonify({'success': False, 'error': '股票数据不存在'}), 404
        
        service = get_stock_analysis_service()
        result = service.analyze_stock(stock_data)
        
        if report_type == 'json':
            return jsonify({'success': True, 'data': result})
        else:
            return jsonify({'success': False, 'error': '暂不支持该格式'}), 400
    
    except Exception as e:
        logger.error(f"生成股票报告异常: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def _get_stock_data(stock_code: str, period: str) -> dict:
    """
    获取股票数据
    这里应该从数据库或tushare获取真实数据
    暂时返回模拟数据用于测试
    """
    # TODO: 从数据库获取真实股票数据
    
    return {
        'stock_code': stock_code,
        'stock_name': f'股票{stock_code}',
        'price': 1680.50,
        'basic': {
            'market_cap': 28000,
            'pe': 28.5,
            'pb': 8.2,
            'revenue_growth': 15.3,
            'profit_growth': 12.8
        },
        'kline_data': {
            'volume': '15.2亿',
            'trend': '上升'
        },
        'technical_signals': {
            'ma_trend': 'bullish',
            'ma_signal': '多头排列',
            'macd_signal': '金叉',
            'rsi': 72
        },
        'support': 1600,
        'resistance': 1800
    }
