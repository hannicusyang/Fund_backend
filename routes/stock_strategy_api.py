# routes/stock_strategy_api.py
# 股票策略持久化API

from flask import Blueprint, request, jsonify
from datetime import datetime
from models import db
from models.stock_strategy import PortfolioConfig, BacktestTemplate, BacktestReport
from models.factor_definition import ScreeningStrategy

stock_strategy_bp = Blueprint('stock_strategy', __name__)


# ==================== 组合配置API ====================

@stock_strategy_bp.route('/portfolio/configs', methods=['GET'])
def get_portfolio_configs():
    """获取用户的组合配置列表"""
    user_id = request.args.get('user_id', 'default')
    
    configs = PortfolioConfig.query.filter_by(user_id=user_id).order_by(
        PortfolioConfig.update_time.desc()
    ).all()
    
    return jsonify({
        'success': True,
        'data': [c.to_dict() for c in configs]
    })


@stock_strategy_bp.route('/portfolio/configs', methods=['POST'])
def save_portfolio_config():
    """保存组合配置"""
    data = request.get_json() or {}
    
    user_id = data.get('user_id', 'default')
    config_id = data.get('id')
    
    # 检查同名配置
    existing = PortfolioConfig.query.filter_by(
        user_id=user_id, 
        name=data.get('name')
    ).first()
    
    if existing and (not config_id or existing.id != config_id):
        return jsonify({'success': False, 'message': '配置名称已存在'})
    
    if config_id:
        # 更新
        config = PortfolioConfig.query.get(config_id)
        if not config:
            return jsonify({'success': False, 'message': '配置不存在'})
    else:
        # 新建
        config = PortfolioConfig(user_id=user_id)
    
    # 更新字段
    config.name = data.get('name', config.name or '未命名组合')
    config.description = data.get('description', config.description)
    config.stocks = data.get('stocks', config.stocks or [])
    config.strategy_type = data.get('strategyType', config.strategy_type or 'equal')
    config.strategy_config = data.get('strategyConfig', config.strategy_config)
    config.constraints = data.get('constraints', config.constraints)
    config.backtest_settings = data.get('backtestSettings', config.backtest_settings)
    config.stock_count = len(config.stocks)
    config.total_weight = sum(s.get('weight', 0) for s in config.stocks)
    
    db.session.add(config)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'data': config.to_dict(),
        'message': '保存成功'
    })


@stock_strategy_bp.route('/portfolio/configs/<int:config_id>', methods=['DELETE'])
def delete_portfolio_config(config_id):
    """删除组合配置"""
    config = PortfolioConfig.query.get(config_id)
    if not config:
        return jsonify({'success': False, 'message': '配置不存在'})
    
    db.session.delete(config)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '删除成功'})


@stock_strategy_bp.route('/portfolio/configs/<int:config_id>/default', methods=['POST'])
def set_default_portfolio(config_id):
    """设为默认组合"""
    user_id = request.json.get('user_id', 'default')
    
    # 取消其他默认
    PortfolioConfig.query.filter_by(user_id=user_id, is_default=True).update(
        {'is_default': False}
    )
    
    # 设置当前
    config = PortfolioConfig.query.get(config_id)
    if config:
        config.is_default = True
        db.session.commit()
    
    return jsonify({'success': True})


@stock_strategy_bp.route('/portfolio/configs/default', methods=['GET'])
def get_default_portfolio():
    """获取默认组合配置"""
    user_id = request.args.get('user_id', 'default')
    
    config = PortfolioConfig.query.filter_by(
        user_id=user_id, is_default=True
    ).first()
    
    if not config:
        # 返回最新的
        config = PortfolioConfig.query.filter_by(user_id=user_id).order_by(
            PortfolioConfig.update_time.desc()
        ).first()
    
    if config:
        return jsonify({'success': True, 'data': config.to_dict()})
    
    return jsonify({'success': False, 'message': '暂无配置'})


# ==================== 回测模板API ====================

@stock_strategy_bp.route('/backtest/templates', methods=['GET'])
def get_backtest_templates():
    """获取回测模板列表"""
    user_id = request.args.get('user_id', 'default')
    
    templates = BacktestTemplate.query.filter_by(user_id=user_id).order_by(
        BacktestTemplate.create_time.desc()
    ).all()
    
    return jsonify({
        'success': True,
        'data': [t.to_dict() for t in templates]
    })


@stock_strategy_bp.route('/backtest/templates', methods=['POST'])
def save_backtest_template():
    """保存回测模板"""
    data = request.get_json() or {}
    user_id = data.get('user_id', 'default')
    template_id = data.get('id')
    
    params = data.get('params', {})
    
    if template_id:
        template = BacktestTemplate.query.get(template_id)
        if not template:
            return jsonify({'success': False, 'message': '模板不存在'})
    else:
        template = BacktestTemplate(user_id=user_id)
    
    template.name = data.get('name', template.name or '未命名模板')
    template.description = data.get('description', template.description)
    template.template_type = data.get('templateType', template.template_type)
    
    # 参数
    template.period = params.get('period', template.period)
    template.benchmark = params.get('benchmark', template.benchmark)
    template.rebalance_freq = params.get('rebalanceFreq', template.rebalance_freq)
    template.initial_capital = params.get('initialCapital', template.initial_capital)
    template.commission_rate = params.get('commissionRate', template.commission_rate)
    template.stamp_duty = params.get('stampDuty', template.stamp_duty)
    template.slippage = params.get('slippage', template.slippage)
    template.position_limit = params.get('positionLimit', template.position_limit)
    template.stop_loss = params.get('stopLoss', template.stop_loss)
    template.stop_profit = params.get('stopProfit', template.stop_profit)
    
    db.session.add(template)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'data': template.to_dict()
    })


@stock_strategy_bp.route('/backtest/templates/<int:template_id>', methods=['DELETE'])
def delete_backtest_template(template_id):
    """删除回测模板"""
    template = BacktestTemplate.query.get(template_id)
    if not template:
        return jsonify({'success': False, 'message': '模板不存在'})
    
    db.session.delete(template)
    db.session.commit()
    
    return jsonify({'success': True})


@stock_strategy_bp.route('/backtest/templates/presets', methods=['GET'])
def get_preset_templates():
    """获取预设模板"""
    presets = [
        {
            'name': '保守型',
            'description': '低波动，稳健收益',
            'templateType': 'conservative',
            'params': {
                'period': 180,
                'rebalanceFreq': 'quarterly',
                'commissionRate': 0.0003,
                'slippage': 0.001,
                'positionLimit': 0.8,
                'stopLoss': 0.08,
                'stopProfit': 0.15
            }
        },
        {
            'name': '稳健型',
            'description': '平衡风险收益',
            'templateType': 'balanced',
            'params': {
                'period': 90,
                'rebalanceFreq': 'monthly',
                'commissionRate': 0.0003,
                'slippage': 0.001,
                'positionLimit': 1.0,
                'stopLoss': None,
                'stopProfit': None
            }
        },
        {
            'name': '激进型',
            'description': '高频调仓，追求超额',
            'templateType': 'aggressive',
            'params': {
                'period': 60,
                'rebalanceFreq': 'weekly',
                'commissionRate': 0.00025,
                'slippage': 0.0005,
                'positionLimit': 1.0,
                'stopLoss': None,
                'stopProfit': None
            }
        }
    ]
    
    return jsonify({'success': True, 'data': presets})


# ==================== 筛选策略API ====================

@stock_strategy_bp.route('/screening/strategies', methods=['GET'])
def get_screening_strategies():
    """获取筛选策略列表"""
    user_id = request.args.get('user_id', 'default')
    
    strategies = ScreeningStrategy.query.filter_by(user_id=user_id).order_by(
        ScreeningStrategy.update_time.desc()
    ).all()
    
    return jsonify({
        'success': True,
        'data': [s.to_dict() for s in strategies]
    })


@stock_strategy_bp.route('/screening/strategies', methods=['POST'])
def save_screening_strategy():
    """保存筛选策略"""
    data = request.get_json() or {}
    user_id = data.get('user_id', 'default')
    strategy_id = data.get('id')
    
    if strategy_id:
        strategy = ScreeningStrategy.query.get(strategy_id)
        if not strategy:
            return jsonify({'success': False, 'message': '策略不存在'})
    else:
        strategy = ScreeningStrategy(user_id=user_id)
    
    strategy.strategy_name = data.get('name', strategy.strategy_name)
    strategy.strategy_desc = data.get('description', strategy.strategy_desc)
    strategy.factor_config = data.get('factors', strategy.factor_config)
    strategy.sort_by = data.get('sortBy', strategy.sort_by)
    strategy.sort_order = data.get('sortOrder', strategy.sort_order)
    strategy.limit = data.get('limit', strategy.limit)
    
    db.session.add(strategy)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'data': strategy.to_dict()
    })


@stock_strategy_bp.route('/screening/strategies/<int:strategy_id>', methods=['DELETE'])
def delete_screening_strategy(strategy_id):
    """删除筛选策略"""
    strategy = ScreeningStrategy.query.get(strategy_id)
    if not strategy:
        return jsonify({'success': False, 'message': '策略不存在'})
    
    db.session.delete(strategy)
    db.session.commit()
    
    return jsonify({'success': True})


# ==================== 回测报告API ====================

@stock_strategy_bp.route('/backtest/reports', methods=['POST'])
def save_backtest_report():
    """保存回测报告"""
    data = request.get_json() or {}
    
    report = BacktestReport(
        user_id=data.get('user_id', 'default'),
        portfolio_id=data.get('portfolioId'),
        template_id=data.get('templateId'),
        backtest_params=data.get('params'),
        summary=data.get('summary'),
        curve_data=data.get('curve'),
        trades=data.get('trades'),
        tags=data.get('tags'),
        notes=data.get('notes')
    )
    
    db.session.add(report)
    db.session.commit()
    
    # 更新组合的最后回测结果
    if report.portfolio_id:
        portfolio = PortfolioConfig.query.get(report.portfolio_id)
        if portfolio and report.summary:
            portfolio.last_backtest_return = report.summary.get('total_return')
            portfolio.last_backtest_sharpe = report.summary.get('sharpe_ratio')
            db.session.commit()
    
    return jsonify({
        'success': True,
        'data': report.to_dict()
    })


@stock_strategy_bp.route('/backtest/reports', methods=['GET'])
def get_backtest_reports():
    """获取回测报告列表"""
    user_id = request.args.get('user_id', 'default')
    portfolio_id = request.args.get('portfolio_id')
    
    query = BacktestReport.query.filter_by(user_id=user_id)
    if portfolio_id:
        query = query.filter_by(portfolio_id=portfolio_id)
    
    reports = query.order_by(BacktestReport.create_time.desc()).limit(50).all()
    
    return jsonify({
        'success': True,
        'data': [r.to_dict() for r in reports]
    })
