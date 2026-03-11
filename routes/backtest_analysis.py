# routes/backtest_analysis.py
# 回测智能分析API

from flask import Blueprint, request, jsonify
from services.backtest_analysis import (
    get_backtest_analysis_service,
    analyze_backtest_with_ai,
    optimize_strategy_params,
    compare_strategies_with_ai
)
from config.logging_config import logger
import traceback

backtest_analysis_bp = Blueprint('backtest_analysis', __name__)


@backtest_analysis_bp.route('/ai-analysis', methods=['POST'])
def backtest_ai_analysis():
    """
    回测AI分析接口
    
    请求参数:
    {
        "backtest_result": {
            "total_return": 85.35,
            "annual_return": 12.15,
            "benchmark_return": 8.5,
            "excess_return": 25.32,
            "max_drawdown": -18.65,
            "sharpe": 1.35,
            "calmar": 0.65,
            "volatility": 16.8,
            "win_rate": 58.5,
            "trade_count": 156,
            "win_count": 91,
            "loss_count": 65,
            "avg_holding_days": 18,
            "avg_win": 5.2,
            "avg_loss": -3.1,
            "trades": [...]
        }
    }
    """
    try:
        data = request.get_json() or {}
        backtest_result = data.get('backtest_result', {})
        
        if not backtest_result:
            return jsonify({'success': False, 'error': '请提供回测数据'}), 400
        
        service = get_backtest_analysis_service()
        result = service.analyze_backtest(backtest_result)
        
        return jsonify({'success': True, 'data': result})
    
    except Exception as e:
        logger.error(f"回测AI分析异常: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@backtest_analysis_bp.route('/optimize', methods=['POST'])
def backtest_optimize():
    """
    策略参数优化接口
    
    请求参数:
    {
        "strategy_name": "均线交叉策略",
        "current_params": {"ma_short": 5, "ma_long": 20},
        "backtest_results": [
            {"params": {"ma_short": 5, "ma_long": 20}, "sharpe": 1.2, "annual_return": 12},
            ...
        ]
    }
    """
    try:
        data = request.get_json() or {}
        strategy_name = data.get('strategy_name', '策略')
        current_params = data.get('current_params', {})
        backtest_results = data.get('backtest_results', [])
        
        if not backtest_results:
            return jsonify({'success': False, 'error': '请提供回测结果数据'}), 400
        
        service = get_backtest_analysis_service()
        result = service.optimize_params(strategy_name, current_params, backtest_results)
        
        return jsonify({'success': True, 'data': result})
    
    except Exception as e:
        logger.error(f"策略优化异常: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@backtest_analysis_bp.route('/compare', methods=['POST'])
def backtest_compare():
    """
    策略对比接口
    
    请求参数:
    {
        "strategies": [
            {"name": "策略A", "annual_return": 15, "sharpe": 1.3, "max_drawdown": -15},
            {"name": "策略B", "annual_return": 12, "sharpe": 1.1, "max_drawdown": -12}
        ]
    }
    """
    try:
        data = request.get_json() or {}
        strategies = data.get('strategies', [])
        
        if not strategies:
            return jsonify({'success': False, 'error': '请提供策略数据'}), 400
        
        service = get_backtest_analysis_service()
        result = service.compare_strategies(strategies)
        
        return jsonify({'success': True, 'data': result})
    
    except Exception as e:
        logger.error(f"策略对比异常: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@backtest_analysis_bp.route('/report', methods=['GET'])
def backtest_report():
    """
    生成回测分析报告
    """
    try:
        # 从参数获取回测数据
        import json
        
        bt_data = request.args.get('backtest_result')
        if bt_data:
            backtest_result = json.loads(bt_data)
        else:
            return jsonify({'success': False, 'error': '请提供回测数据'}), 400
        
        service = get_backtest_analysis_service()
        result = service.analyze_backtest(backtest_result)
        
        return jsonify({'success': True, 'data': result})
    
    except Exception as e:
        logger.error(f"生成回测报告异常: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
