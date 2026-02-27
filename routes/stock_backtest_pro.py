"""
专业股票回测引擎 - 支持多种调仓策略和完整成本计算
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import math
import pandas as pd
import numpy as np
import baostock as bs

# 导入tushare
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.tushare_api import get_pro, get_daily

stock_backtest_pro_bp = Blueprint('stock_backtest_pro', __name__)

# 登录 baostock
bs.login()


class ProfessionalBacktestEngine:
    """
    专业回测引擎
    支持：多种调仓频率、完整交易成本、风险控制、详细交易记录
    """
    
    def __init__(self, config):
        self.initial_capital = float(config.get('initialCapital', 1000000))
        self.benchmark = config.get('benchmark', 'sh.000300')
        self.rebalance_freq = config.get('rebalanceFreq', 'monthly')
        self.commission_rate = float(config.get('commissionRate', 0.0003))
        self.stamp_duty = float(config.get('stampDuty', 0.001))
        self.slippage = float(config.get('slippage', 0.001))
        self.position_limit = float(config.get('positionLimit', 1.0))
        self.stop_loss = float(config.get('stopLoss', 0)) if config.get('stopLoss') else None
        self.stop_profit = float(config.get('stopProfit', 0)) if config.get('stopProfit') else None
        
        # 运行时状态
        self.cash = self.initial_capital
        self.positions = {}  # {code: {'shares': int, 'cost': float, 'name': str}}
        self.trades = []  # 交易记录
        self.daily_values = []  # 每日组合价值
        self.daily_dates = []  # 日期列表
        
    def get_rebalance_dates(self, dates):
        """根据调仓频率获取调仓日期索引"""
        if not dates:
            return []
        
        rebalance_indices = [0]  # 首日建仓
        
        if self.rebalance_freq == 'daily':
            return list(range(len(dates)))
        elif self.rebalance_freq == 'weekly':
            # 每周第一个交易日
            for i in range(1, len(dates)):
                if i % 5 == 0:
                    rebalance_indices.append(i)
        elif self.rebalance_freq == 'monthly':
            # 每月第一个交易日（约21天）
            for i in range(21, len(dates), 21):
                rebalance_indices.append(i)
        elif self.rebalance_freq == 'quarterly':
            # 每季度第一个交易日（约63天）
            for i in range(63, len(dates), 63):
                rebalance_indices.append(i)
        elif self.rebalance_freq == 'threshold':
            # 阈值再平衡 - 在execute_rebalance中处理
            return list(range(len(dates)))
        
        # 确保包含最后一天
        if rebalance_indices[-1] != len(dates) - 1:
            rebalance_indices.append(len(dates) - 1)
            
        return rebalance_indices
    
    def calculate_target_weights(self, stocks, strategy_type='equal'):
        """计算目标权重"""
        n = len(stocks)
        if n == 0:
            return {}
        
        if strategy_type == 'equal':
            # 等权重
            return {s['code']: 1.0/n for s in stocks}
        elif strategy_type == 'value':
            # 价值加权（低PE权重高）
            # 简化处理，实际应该根据PE计算
            return {s['code']: 1.0/n for s in stocks}
        elif strategy_type == 'momentum':
            # 动量加权（近期涨幅大的权重高）
            return {s['code']: 1.0/n for s in stocks}
        else:
            # 自定义权重
            total_weight = sum(s.get('weight', 0) for s in stocks)
            if total_weight > 0:
                return {s['code']: s.get('weight', 0) / total_weight for s in stocks}
            return {s['code']: 1.0/n for s in stocks}
    
    def execute_trade(self, date, stock_code, stock_name, shares, price, action, reason=''):
        """执行交易，计算成本"""
        if shares <= 0 or price <= 0:
            return
        
        # 考虑滑点
        if action == 'buy':
            exec_price = price * (1 + self.slippage)
        else:  # sell
            exec_price = price * (1 - self.slippage)
        
        amount = shares * exec_price
        commission = amount * self.commission_rate
        
        # 印花税仅卖出收取
        stamp_tax = amount * self.stamp_duty if action == 'sell' else 0
        total_cost = commission + stamp_tax
        
        if action == 'buy':
            total_payment = amount + total_cost
            if total_payment > self.cash:
                # 资金不足，调整股数
                max_amount = self.cash / (1 + self.commission_rate + self.slippage)
                shares = int(max_amount / price / 100) * 100
                if shares <= 0:
                    return
                amount = shares * exec_price
                commission = amount * self.commission_rate
                total_cost = commission
            
            self.cash -= (amount + total_cost)
            
            if stock_code in self.positions:
                # 加仓，更新成本
                old_shares = self.positions[stock_code]['shares']
                old_cost = self.positions[stock_code]['cost']
                total_shares = old_shares + shares
                avg_cost = (old_shares * old_cost + shares * exec_price) / total_shares
                self.positions[stock_code]['shares'] = total_shares
                self.positions[stock_code]['cost'] = avg_cost
            else:
                self.positions[stock_code] = {
                    'shares': shares,
                    'cost': exec_price,
                    'name': stock_name
                }
        else:  # sell
            if stock_code not in self.positions or self.positions[stock_code]['shares'] < shares:
                return
            
            self.cash += (amount - total_cost)
            self.positions[stock_code]['shares'] -= shares
            
            if self.positions[stock_code]['shares'] == 0:
                del self.positions[stock_code]
        
        self.trades.append({
            'date': date,
            'code': stock_code,
            'name': stock_name,
            'action': '买入' if action == 'buy' else '卖出',
            'shares': shares,
            'price': round(exec_price, 2),
            'amount': round(amount, 2),
            'commission': round(commission, 2),
            'stamp_tax': round(stamp_tax, 2),
            'total_cost': round(total_cost, 2),
            'reason': reason
        })
    
    def execute_rebalance(self, date, current_prices, target_weights, reason='再平衡'):
        """执行再平衡"""
        # 计算当前总价值
        total_value = self.cash
        current_weights = {}
        
        for code, pos in list(self.positions.items()):
            if code in current_prices and current_prices[code] > 0:
                value = pos['shares'] * current_prices[code]
                total_value += value
                current_weights[code] = value
        
        if total_value <= 0:
            return
        
        # 转换为权重
        for code in current_weights:
            current_weights[code] /= total_value
        
        # 计算调仓目标
        for code, target_weight in target_weights.items():
            if code not in current_prices or current_prices[code] <= 0:
                continue
            
            current_weight = current_weights.get(code, 0)
            weight_diff = target_weight - current_weight
            
            # 阈值再平衡：只有偏差超过阈值才调仓
            if self.rebalance_freq == 'threshold' and abs(weight_diff) < 0.05:
                continue
            
            target_value = total_value * target_weight * self.position_limit
            current_value = current_weights.get(code, 0) * total_value
            value_diff = target_value - current_value
            
            price = current_prices[code]
            shares_diff = int(abs(value_diff) / price / 100) * 100
            
            if shares_diff < 100:
                continue
            
            if value_diff > 0:
                # 买入
                self.execute_trade(date, code, 
                    self.positions.get(code, {}).get('name', code),
                    shares_diff, price, 'buy', reason)
            elif value_diff < 0 and code in self.positions:
                # 卖出
                sell_shares = min(shares_diff, self.positions[code]['shares'])
                if sell_shares > 0:
                    self.execute_trade(date, code, self.positions[code]['name'],
                        sell_shares, price, 'sell', reason)
        
        # 处理止损止盈
        if self.stop_loss or self.stop_profit:
            for code, pos in list(self.positions.items()):
                if code not in current_prices:
                    continue
                
                current_price = current_prices[code]
                cost = pos['cost']
                return_pct = (current_price - cost) / cost
                
                if self.stop_loss and return_pct <= -self.stop_loss:
                    self.execute_trade(date, code, pos['name'],
                        pos['shares'], current_price, 'sell', '止损')
                elif self.stop_profit and return_pct >= self.stop_profit:
                    self.execute_trade(date, code, pos['name'],
                        pos['shares'], current_price, 'sell', '止盈')
    
    def run(self, stocks, start_date, end_date):
        """
        运行回测
        
        stocks: [{'code': str, 'name': str, 'data': {...}, 'weight': float}]
        """
        if not stocks:
            return None
        
        # 对齐数据
        min_len = min(len(s['data']['closes']) for s in stocks)
        dates = stocks[0]['data']['dates'][:min_len]
        
        # 获取基准数据
        benchmark_data = self._get_benchmark_data(dates)
        
        # 计算目标权重
        target_weights = self.calculate_target_weights(stocks)
        
        # 获取调仓日期
        rebalance_indices = self.get_rebalance_dates(dates)
        
        # 首日建仓
        first_day_prices = {s['code']: s['data']['closes'][0] for s in stocks}
        self._initial_build(dates[0], stocks, first_day_prices)
        
        # 逐日回测
        for i in range(1, min_len):
            current_date = dates[i]
            
            # 获取当日价格
            current_prices = {}
            for s in stocks:
                if i < len(s['data']['closes']):
                    current_prices[s['code']] = s['data']['closes'][i]
            
            # 检查是否需要调仓
            if i in rebalance_indices:
                self.execute_rebalance(current_date, current_prices, target_weights)
            
            # 计算当日组合价值
            day_value = self._calculate_portfolio_value(current_prices)
            self.daily_values.append(day_value)
            self.daily_dates.append(current_date)
        
        # 计算绩效指标
        return self._calculate_performance(benchmark_data)
    
    def _initial_build(self, date, stocks, prices):
        """初始建仓"""
        target_weights = self.calculate_target_weights(stocks)
        
        for stock in stocks:
            code = stock['code']
            if code not in prices or prices[code] <= 0:
                continue
            
            weight = target_weights.get(code, 1/len(stocks))
            allocate_amount = self.cash * weight
            
            price = prices[code]
            shares = int(allocate_amount / price / 100) * 100
            
            if shares > 0:
                self.execute_trade(date, code, stock['name'], shares, price, 'buy', '建仓')
    
    def _calculate_portfolio_value(self, prices):
        """计算组合当前价值"""
        value = self.cash
        for code, pos in self.positions.items():
            if code in prices and prices[code] > 0:
                value += pos['shares'] * prices[code]
        return value
    
    def _get_benchmark_data(self, dates):
        """获取基准数据"""
        try:
            from .stock_backtest import get_index_historical_data
            data = get_index_historical_data(self.benchmark, len(dates))
            if data and len(data['closes']) >= len(dates):
                return {
                    'dates': data['dates'][:len(dates)],
                    'closes': data['closes'][:len(dates)]
                }
        except:
            pass
        return None
    
    def _calculate_performance(self, benchmark_data):
        """计算绩效指标"""
        if not self.daily_values:
            return None
        
        values = [self.initial_capital] + self.daily_values
        dates = self.daily_dates
        
        # 总收益
        total_return = (values[-1] - self.initial_capital) / self.initial_capital * 100
        
        # 年化收益
        days = len(values) - 1
        years = days / 252
        annual_return = ((values[-1] / self.initial_capital) ** (1/years) - 1) * 100 if years > 0 else 0
        
        # 日收益率序列
        daily_returns = [(values[i] - values[i-1]) / values[i-1] for i in range(1, len(values))]
        
        # 波动率
        if daily_returns:
            volatility = np.std(daily_returns) * np.sqrt(252) * 100
        else:
            volatility = 0
        
        # 夏普比率
        risk_free = 0.025
        sharpe = (annual_return/100 - risk_free) / (volatility/100) if volatility > 0 else 0
        
        # 最大回撤
        peak = values[0]
        max_drawdown = 0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100
            if dd > max_drawdown:
                max_drawdown = dd
        
        # 卡玛比率
        calmar = annual_return / max_drawdown if max_drawdown > 0 else 0
        
        # 索提诺比率（只考虑下行波动）
        downside_returns = [r for r in daily_returns if r < 0]
        if downside_returns:
            downside_std = np.std(downside_returns) * np.sqrt(252)
            sortino = (annual_return/100 - risk_free) / downside_std if downside_std > 0 else 0
        else:
            sortino = sharpe
        
        # 基准对比
        if benchmark_data and len(benchmark_data['closes']) >= 2:
            bench_values = [self.initial_capital]
            for i in range(1, len(benchmark_data['closes'])):
                ret = (benchmark_data['closes'][i] - benchmark_data['closes'][i-1]) / benchmark_data['closes'][i-1]
                bench_values.append(bench_values[-1] * (1 + ret))
            benchmark_return = (bench_values[-1] - self.initial_capital) / self.initial_capital * 100
            alpha = annual_return - benchmark_return
        else:
            benchmark_return = 0
            alpha = 0
        
        # 交易统计
        buy_trades = [t for t in self.trades if t['action'] == '买入']
        sell_trades = [t for t in self.trades if t['action'] == '卖出']
        total_commission = sum(t['total_cost'] for t in self.trades)
        
        # 胜率（简化：以卖出交易计算）
        profitable_sells = 0
        for t in sell_trades:
            # 找到对应的买入成本
            cost_basis = None
            for bt in self.trades:
                if bt['code'] == t['code'] and bt['action'] == '买入':
                    cost_basis = bt['price']
                    break
            if cost_basis and t['price'] > cost_basis:
                profitable_sells += 1
        
        win_rate = (profitable_sells / len(sell_trades) * 100) if sell_trades else 0
        
        # 换手率
        total_turnover = sum(t['amount'] for t in self.trades)
        avg_capital = (self.initial_capital + values[-1]) / 2
        turnover_rate = (total_turnover / avg_capital * 100) if avg_capital > 0 else 0
        
        return {
            'summary': {
                'total_return': round(total_return, 2),
                'annual_return': round(annual_return, 2),
                'benchmark_return': round(benchmark_return, 2),
                'alpha': round(alpha, 2),
                'volatility': round(volatility, 2),
                'sharpe_ratio': round(sharpe, 2),
                'sortino_ratio': round(sortino, 2),
                'calmar_ratio': round(calmar, 2),
                'max_drawdown': round(max_drawdown, 2),
                'win_rate': round(win_rate, 2),
                'turnover_rate': round(turnover_rate, 2),
                'initial_capital': self.initial_capital,
                'final_value': round(values[-1], 2),
                'total_trades': len(self.trades),
                'buy_trades': len(buy_trades),
                'sell_trades': len(sell_trades),
                'total_commission': round(total_commission, 2),
                'profit': round(values[-1] - self.initial_capital, 2)
            },
            'curve': {
                'dates': dates,
                'portfolio': [round(v, 2) for v in values[1:]],
                'benchmark': [round(v, 2) for v in bench_values] if benchmark_data else []
            },
            'positions': [
                {
                    'code': code,
                    'name': pos['name'],
                    'shares': pos['shares'],
                    'cost': round(pos['cost'], 2)
                }
                for code, pos in self.positions.items()
            ],
            'trades': self.trades
        }


@stock_backtest_pro_bp.route('/pro/backtest', methods=['POST'])
def run_pro_backtest():
    """专业回测接口"""
    data = request.get_json() or {}
    
    # 解析参数
    stocks = data.get('stocks', [])
    period = int(data.get('period', 60))
    config = {
        'initialCapital': data.get('initialCapital', 1000000),
        'benchmark': data.get('benchmark', 'sh.000300'),
        'rebalanceFreq': data.get('rebalanceFreq', 'monthly'),
        'commissionRate': data.get('commissionRate', 0.0003),
        'stampDuty': data.get('stampDuty', 0.001),
        'slippage': data.get('slippage', 0.001),
        'positionLimit': data.get('positionLimit', 1.0),
        'stopLoss': data.get('stopLoss'),
        'stopProfit': data.get('stopProfit')
    }
    
    if not stocks:
        return jsonify({'success': False, 'message': '请选择股票'})
    
    # 获取股票数据
    from .stock_backtest import get_stock_historical_data
    
    stock_data_list = []
    for stock in stocks[:20]:
        if isinstance(stock, dict):
            code = stock.get('code', '')
            name = stock.get('name', code)
            weight = stock.get('weight', 0)
        else:
            code = str(stock)
            name = code
            weight = 0
        
        code = code.strip().replace('sh.', '').replace('sz.', '')
        if not code:
            continue
        
        hist_data = get_stock_historical_data(code, period)
        if hist_data and len(hist_data['closes']) >= 10:
            valid_closes = [c for c in hist_data['closes'] if c and c > 0]
            if len(valid_closes) >= 10:
                stock_data_list.append({
                    'code': code,
                    'name': name,
                    'data': hist_data,
                    'weight': weight
                })
    
    if not stock_data_list:
        return jsonify({'success': False, 'message': '无法获取股票数据'})
    
    # 运行回测
    engine = ProfessionalBacktestEngine(config)
    result = engine.run(stock_data_list, None, None)
    
    if not result:
        return jsonify({'success': False, 'message': '回测失败'})
    
    return jsonify({
        'success': True,
        'data': result
    })
