# models/stock_strategy.py
# 股票策略持久化模型 - 组合配置、回测模板

from . import db
from datetime import datetime
import json


class PortfolioConfig(db.Model):
    """
    组合配置表
    保存用户的股票组合配置
    """
    __tablename__ = 'portfolio_configs'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # 基础信息
    user_id = db.Column(db.String(50), nullable=False, default='default', comment='用户ID')
    name = db.Column(db.String(100), nullable=False, comment='组合名称')
    description = db.Column(db.Text, comment='组合描述')
    
    # 股票列表 (JSON格式: [{code, name, weight}, ...])
    stocks = db.Column(db.JSON, nullable=False, comment='股票列表')
    
    # 优化策略
    strategy_type = db.Column(db.String(50), default='equal', comment='优化策略类型')
    strategy_config = db.Column(db.JSON, comment='策略配置参数')
    
    # 约束条件
    constraints = db.Column(db.JSON, comment='约束条件')
    
    # 回测关联
    backtest_settings = db.Column(db.JSON, comment='默认回测设置')
    
    # 统计信息
    stock_count = db.Column(db.Integer, comment='股票数量')
    total_weight = db.Column(db.Float, comment='总权重')
    
    # 绩效记录
    last_backtest_return = db.Column(db.Float, comment='上次回测收益')
    last_backtest_sharpe = db.Column(db.Float, comment='上次回测夏普')
    
    # 状态
    is_default = db.Column(db.Boolean, default=False, comment='是否默认组合')
    
    # 时间戳
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'stocks': self.stocks,
            'strategyType': self.strategy_type,
            'strategyConfig': self.strategy_config,
            'constraints': self.constraints,
            'backtestSettings': self.backtest_settings,
            'stockCount': self.stock_count,
            'totalWeight': self.total_weight,
            'lastBacktestReturn': self.last_backtest_return,
            'lastBacktestSharpe': self.last_backtest_sharpe,
            'isDefault': self.is_default,
            'createTime': self.create_time.isoformat() if self.create_time else None,
            'updateTime': self.update_time.isoformat() if self.update_time else None
        }


class BacktestTemplate(db.Model):
    """
    回测参数模板表
    保存用户的回测参数配置
    """
    __tablename__ = 'backtest_templates'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # 基础信息
    user_id = db.Column(db.String(50), nullable=False, default='default', comment='用户ID')
    name = db.Column(db.String(100), nullable=False, comment='模板名称')
    description = db.Column(db.Text, comment='模板描述')
    template_type = db.Column(db.String(50), default='custom', comment='模板类型')
    
    # 回测参数
    period = db.Column(db.Integer, default=90, comment='回测期间(天)')
    benchmark = db.Column(db.String(50), default='sh.000300', comment='基准指数')
    rebalance_freq = db.Column(db.String(50), default='monthly', comment='调仓频率')
    initial_capital = db.Column(db.Float, default=1000000, comment='初始资金')
    
    # 交易成本
    commission_rate = db.Column(db.Float, default=0.0003, comment='佣金费率')
    stamp_duty = db.Column(db.Float, default=0.001, comment='印花税率')
    slippage = db.Column(db.Float, default=0.001, comment='滑点')
    
    # 风险控制
    position_limit = db.Column(db.Float, default=1.0, comment='仓位上限')
    stop_loss = db.Column(db.Float, comment='止损线')
    stop_profit = db.Column(db.Float, comment='止盈线')
    
    # 状态
    is_default = db.Column(db.Boolean, default=False, comment='是否默认模板')
    
    # 时间戳
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'templateType': self.template_type,
            'params': {
                'period': self.period,
                'benchmark': self.benchmark,
                'rebalanceFreq': self.rebalance_freq,
                'initialCapital': self.initial_capital,
                'commissionRate': self.commission_rate,
                'stampDuty': self.stamp_duty,
                'slippage': self.slippage,
                'positionLimit': self.position_limit,
                'stopLoss': self.stop_loss,
                'stopProfit': self.stop_profit
            },
            'isDefault': self.is_default,
            'createTime': self.create_time.isoformat() if self.create_time else None
        }


class UserFactorPreference(db.Model):
    """
    用户因子偏好表
    记录用户常用的因子组合
    """
    __tablename__ = 'user_factor_preferences'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    user_id = db.Column(db.String(50), nullable=False, default='default')
    factor_category = db.Column(db.String(50), comment='因子类别')
    factor_list = db.Column(db.JSON, comment='因子列表')
    weight_config = db.Column(db.JSON, comment='权重配置')
    
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'category': self.factor_category,
            'factors': self.factor_list,
            'weights': self.weight_config
        }


class BacktestReport(db.Model):
    """
    回测报告表
    保存历史回测结果
    """
    __tablename__ = 'backtest_reports'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # 关联信息
    user_id = db.Column(db.String(50), nullable=False, default='default')
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolio_configs.id'), comment='关联组合')
    template_id = db.Column(db.Integer, db.ForeignKey('backtest_templates.id'), comment='关联模板')
    
    # 回测参数快照
    backtest_params = db.Column(db.JSON, comment='回测参数')
    
    # 结果摘要
    summary = db.Column(db.JSON, comment='结果摘要')
    
    # 完整结果 (可选，大数据量时单独存储)
    curve_data = db.Column(db.JSON, comment='收益曲线')
    trades = db.Column(db.JSON, comment='交易记录')
    
    # 标签
    tags = db.Column(db.JSON, comment='标签')
    notes = db.Column(db.Text, comment='备注')
    
    # 时间戳
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'portfolioId': self.portfolio_id,
            'templateId': self.template_id,
            'params': self.backtest_params,
            'summary': self.summary,
            'tags': self.tags,
            'notes': self.notes,
            'createTime': self.create_time.isoformat() if self.create_time else None
        }
