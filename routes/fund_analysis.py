# routes/fund_analysis.py
# 基金智能分析API

from flask import Blueprint, request, jsonify
from services.fund_analysis import (
    analyze_fund_with_ai,
    compare_funds_with_ai
)
from config.logging_config import logger
import traceback

fund_analysis_bp = Blueprint('fund_analysis', __name__)


@fund_analysis_bp.route('/ai-analysis', methods=['POST'])
def fund_ai_analysis():
    """
    基金AI分析接口
    
    请求参数:
    {
        "fund_codes": ["000001", "000002"],  # 基金代码列表
        "period": "1y"  # 分析周期
    }
    
    返回:
    {
        "success": true,
        "data": {
            "fund_code": "000001",
            "analysis_date": "2026-03-08",
            "综合评分": "82/100",
            ...
        }
    }
    """
    try:
        data = request.get_json() or {}
        fund_codes = data.get('fund_codes', [])
        period = data.get('period', '1y')
        
        if not fund_codes:
            return jsonify({'success': False, 'error': '请提供基金代码'}), 400
        
        # 直接创建新实例，避免单例问题
        from services.fund_analysis import FundAnalysisService
        service = FundAnalysisService()
        
        logger.info(f"Service enabled: {service.enabled}, base_url: {service.base_url}")
        
        # 获取额外分析数据（相关性、风险收益分布等）
        extra_data = _get_extra_analysis_data(fund_codes, period)
        
        # 如果只有一个基金
        if len(fund_codes) == 1:
            # 这里需要先获取基金数据
            # 暂时返回模拟数据，实际需要从数据库获取
            fund_data = _get_fund_data(fund_codes[0], period)
            if not fund_data:
                return jsonify({'success': False, 'error': '基金数据不存在'}), 404
            
            logger.info(f"Calling AI analysis for fund {fund_codes[0]}...")
            result = service.analyze_fund(fund_data, extra_data.get('risk_return_data'))
            logger.info(f"AI analysis result method: {result.get('analysis_method')}")
            return jsonify({'success': True, 'data': result})
        
        # 如果是多个基金，进行对比分析
        funds_data = [_get_fund_data(code, period) for code in fund_codes]
        funds_data = [f for f in funds_data if f]  # 过滤None
        
        if not funds_data:
            return jsonify({'success': False, 'error': '基金数据不存在'}), 404
        
        # 传递相关性数据和风险收益数据
        result = service.compare_funds(funds_data, extra_data)
        return jsonify({'success': True, 'data': result})
    
    except Exception as e:
        logger.error(f"基金AI分析异常: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@fund_analysis_bp.route('/report', methods=['GET'])
def fund_report():
    """
    生成基金分析报告
    
    参数:
    - fund_code: 基金代码
    - type: 报告类型 (pdf/html/json)
    """
    try:
        fund_code = request.args.get('fund_code')
        report_type = request.args.get('type', 'json')
        
        if not fund_code:
            return jsonify({'success': False, 'error': '请提供基金代码'}), 400
        
        # 获取基金数据
        fund_data = _get_fund_data(fund_code, '1y')
        if not fund_data:
            return jsonify({'success': False, 'error': '基金数据不存在'}), 404
        
        from services.fund_analysis import FundAnalysisService
        service = FundAnalysisService()
        result = service.analyze_fund(fund_data)
        
        if report_type == 'json':
            return jsonify({'success': True, 'data': result})
        else:
            # 其他格式暂不支持
            return jsonify({'success': False, 'error': '暂不支持该格式'}), 400
    
    except Exception as e:
        logger.error(f"生成基金报告异常: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def _get_fund_data(fund_code: str, period: str) -> dict:
    """
    获取基金数据 - 从数据库获取真实数据（如果可用）
    """
    period_map = {
        '1m': 30, '3m': 90, '6m': 180, '1y': 365, '2y': 730, '3y': 1095
    }
    days = period_map.get(period, 365)
    
    # 尝试从数据库获取
    try:
        from models.fund import Fund
        fund = Fund.query.filter_by(fund_code=fund_code).first()
        
        if fund:
            return {
                'fund_code': fund.fund_code,
                'fund_name': fund.fund_name,
                'nav': fund.net_value,
                'accumulated_net_value': fund.accumulated_net_value,
                'period_returns': {
                    '1m': fund.monthly_1_growth_rate,
                    '3m': fund.monthly_3_growth_rate,
                    '6m': fund.monthly_6_growth_rate,
                    '1y': fund.yearly_1_growth_rate,
                    '2y': fund.yearly_2_growth_rate,
                    '3y': fund.yearly_3_growth_rate
                },
                'annual_return': fund.yearly_1_growth_rate,
                'ytd_return': fund.ytd_growth_rate,
                'daily_return': fund.daily_growth_rate,
                'weekly_return': fund.weekly_growth_rate,
                'rank': fund.rank,
                'sharpe': fund.sharpe_ratio,
                'max_drawdown': fund.max_drawdown,
                'volatility': fund.volatility,
                'risk_level': fund.risk_level,
                'top10_ratio': fund.top10_holdings_ratio,
                'top_sectors': fund.top_sectors.split(',') if fund.top_sectors else [],
                'turnover_rate': fund.turnover_rate,
                'scale': fund.scale,
                'fee_rate': fund.fee_rate,
                'manager': fund.manager,
                'establish_date': fund.establish_date,
                'since_inception_return': fund.since_inception_growth_rate
            }
    except Exception as e:
        logger.warning(f"数据库查询失败: {e}，使用模拟数据")
    
    # 使用更丰富的模拟数据用于测试
    import random
    return {
        'fund_code': fund_code,
        'fund_name': f'基金{fund_code}',
        'nav': round(1.0 + random.uniform(0, 2), 4),
        'accumulated_net_value': round(1.5 + random.uniform(0, 2), 4),
        'period_returns': {
            '1m': round(random.uniform(-5, 15), 2),
            '3m': round(random.uniform(-10, 30), 2),
            '6m': round(random.uniform(0, 40), 2),
            '1y': round(random.uniform(10, 80), 2),
            '2y': round(random.uniform(20, 100), 2),
            '3y': round(random.uniform(30, 120), 2)
        },
        'annual_return': round(random.uniform(10, 80), 2),
        'ytd_return': round(random.uniform(-5, 20), 2),
        'daily_return': round(random.uniform(-3, 3), 2),
        'weekly_return': round(random.uniform(-10, 10), 2),
        'rank': f'{random.randint(1, 500)}/{random.randint(500, 2000)}',
        'sharpe': round(random.uniform(0.5, 2.5), 2),
        'max_drawdown': round(random.uniform(-30, -5), 2),
        'volatility': round(random.uniform(10, 30), 2),
        'risk_level': random.choice(['低风险', '中低风险', '中风险', '中高风险', '高风险']),
        'top10_ratio': round(random.uniform(20, 60), 2),
        'top_sectors': random.sample(['新能源', '半导体', '医药', '消费', '金融', '科技', '高端制造'], 3),
        'turnover_rate': round(random.uniform(50, 300), 2),
        'scale': round(random.uniform(1, 100), 2),
        'fee_rate': round(random.uniform(0, 1.5), 2),
        'manager': f'基金经理{random.randint(1, 10)}',
        'establish_date': f'201{random.randint(0, 9)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}',
        'since_inception_return': round(random.uniform(20, 200), 2)
    }


def _get_extra_analysis_data(fund_codes: list, period: str) -> dict:
    """
    获取额外的分析数据：相关性矩阵、风险收益分布等
    """
    result = {
        'correlation_matrix': None,
        'risk_return_data': None,
        'period': period
    }
    
    if len(fund_codes) < 2:
        return result
    
    # 计算日期范围
    from datetime import datetime, timedelta
    period_days = {'1m': 30, '3m': 90, '6m': 180, '1y': 365, '2y': 730, '3y': 1095}
    days = period_days.get(period, 365)
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    # 获取相关性数据
    try:
        from services.fund_analysis import calculate_fund_correlation
        correlation_data = calculate_fund_correlation(fund_codes, start_date, end_date)
        if correlation_data:
            result['correlation_matrix'] = correlation_data
            logger.info(f"获取到相关性数据: {len(correlation_data.get('matrix', []))}x{len(correlation_data.get('matrix', [[]])[0])}")
    except Exception as e:
        logger.warning(f"获取相关性数据失败: {e}")
    
    # 获取风险收益数据
    try:
        from services.fund_analysis import calculate_fund_risk_return
        risk_return = calculate_fund_risk_return(fund_codes, period)
        if risk_return:
            result['risk_return_data'] = risk_return
            logger.info(f"获取到风险收益数据: {len(risk_return)}只基金")
    except Exception as e:
        logger.warning(f"获取风险收益数据失败: {e}")
    
    return result
