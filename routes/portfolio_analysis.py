# routes/portfolio_analysis.py
# 组合智能分析API

from flask import Blueprint, request, jsonify
from services.portfolio_analysis import (
    get_portfolio_analysis_service,
    analyze_portfolio_with_ai,
    generate_rebalance_advice
)
from config.logging_config import logger
import traceback

portfolio_analysis_bp = Blueprint('portfolio_analysis', __name__)


@portfolio_analysis_bp.route('/ai-analysis', methods=['POST'])
def portfolio_ai_analysis():
    """
    组合AI分析接口
    
    请求参数:
    {
        "holdings": [
            {"stock_code": "600519", "stock_name": "贵州茅台", "value": 500000, "sector": "白酒"},
            {"stock_code": "000858", "stock_name": "五粮液", "value": 300000, "sector": "白酒"}
        ],
        "weights": [62.5, 37.5]  # 百分比
    }
    """
    try:
        data = request.get_json() or {}
        holdings = data.get('holdings', [])
        weights = data.get('weights', [])
        
        if not holdings:
            return jsonify({'success': False, 'error': '请提供持仓数据'}), 400
        
        # 归一化权重
        if weights and len(weights) == len(holdings):
            total = sum(weights)
            if total > 0:
                weights = [w / total * 100 for w in weights]
        else:
            # 等权重
            weights = [100 / len(holdings)] * len(holdings)
        
        service = get_portfolio_analysis_service()
        result = service.analyze_portfolio(holdings, weights)
        
        return jsonify({'success': True, 'data': result})
    
    except Exception as e:
        logger.error(f"组合AI分析异常: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@portfolio_analysis_bp.route('/rebalance-advice', methods=['POST'])
def portfolio_rebalance_advice():
    """
    组合调仓建议接口
    
    请求参数:
    {
        "holdings": [...],
        "weights": [...],
        "target_weights": [...]  # 可选，目标权重
    }
    """
    try:
        data = request.get_json() or {}
        holdings = data.get('holdings', [])
        weights = data.get('weights', [])
        target_weights = data.get('target_weights')
        
        if not holdings:
            return jsonify({'success': False, 'error': '请提供持仓数据'}), 400
        
        # 归一化权重
        if weights and len(weights) == len(holdings):
            total = sum(weights)
            if total > 0:
                weights = [w / total * 100 for w in weights]
        else:
            weights = [100 / len(holdings)] * len(holdings)
        
        if target_weights:
            total = sum(target_weights)
            if total > 0:
                target_weights = [w / total * 100 for w in target_weights]
        
        service = get_portfolio_analysis_service()
        result = service.generate_rebalance_advice(holdings, weights, target_weights)
        
        return jsonify({'success': True, 'data': result})
    
    except Exception as e:
        logger.error(f"调仓建议异常: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@portfolio_analysis_bp.route('/report', methods=['GET'])
def portfolio_report():
    """
    生成组合分析报告
    """
    try:
        holdings_param = request.args.get('holdings')
        weights_param = request.args.get('weights')
        
        import json
        holdings = json.loads(holdings_param) if holdings_param else []
        weights = json.loads(weights_param) if weights_param else []
        
        if not holdings:
            return jsonify({'success': False, 'error': '请提供持仓数据'}), 400
        
        service = get_portfolio_analysis_service()
        result = service.analyze_portfolio(holdings, weights)
        
        return jsonify({'success': True, 'data': result})
    
    except Exception as e:
        logger.error(f"生成组合报告异常: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
