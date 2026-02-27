"""
股票回测API - 使用真实数据 (baostock + tushare)
支持多种再平衡策略和交易成本计算
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import math
import baostock as bs
import pandas as pd

# 导入tushare
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.tushare_api import get_pro, get_daily

stock_backtest_bp = Blueprint('stock_backtest', __name__)

# 登录 baostock
bs.login()


def get_stock_historical_data(stock_code, period=60):
    """
    获取股票历史数据 (baostock)
    """
    try:
        # 判断股票市场
        if stock_code.startswith('6'):
            bs_code = f"sh.{stock_code}"
        elif stock_code.startswith('0') or stock_code.startswith('3'):
            bs_code = f"sz.{stock_code}"
        else:
            bs_code = f"sh.{stock_code}"
        
        # 计算日期范围
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=period * 2)).strftime('%Y-%m-%d')
        
        # 获取数据
        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,open,high,low,close,volume",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="2"  # 前复权
        )
        
        data_list = []
        while rs.error_code == '0' and rs.next():
            data_list.append(rs.get_row_data())
        
        if not data_list:
            return None
        
        # 转换为 DataFrame
        df = pd.DataFrame(data_list, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
        
        # 转换为数值类型
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 取最近 period 天
        df = df.tail(period)
        
        if len(df) < period // 2:
            return None
        
        return {
            'dates': df['date'].tolist(),
            'closes': df['close'].tolist(),
            'opens': df['open'].tolist(),
            'highs': df['high'].tolist(),
            'lows': df['low'].tolist(),
            'volumes': df['volume'].tolist()
        }
        
    except Exception as e:
        print(f"获取 {stock_code} 数据失败: {e}")
        return None


def get_index_historical_data(index_code='sh.000300', period=60):
    """
    获取指数历史数据
    """
    try:
        # 指数代码映射
        index_map = {
            'sh.000001': 'sh.000001',  # 上证指数
            'sh.000300': 'sh.000300',  # 沪深300
            'sz.399001': 'sz.399001',  # 深证成指
            'sz.399006': 'sz.399006',  # 创业板指
            'sh.000688': 'sh.000688',  # 科创50
            'sh.000905': 'sh.000905',  # 中证500
            'sh.000016': 'sh.000016',  # 上证50
        }
        
        bs_code = index_map.get(index_code, 'sh.000001')
        
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=period * 2)).strftime('%Y-%m-%d')
        
        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,close",
            start_date=start_date,
            end_date=end_date,
            frequency="d"
        )
        
        data_list = []
        while rs.error_code == '0' and rs.next():
            data_list.append(rs.get_row_data())
        
        if not data_list:
            return None
        
        df = pd.DataFrame(data_list, columns=['date', 'close'])
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df = df.dropna()
        df = df.tail(period)
        
        return {
            'dates': df['date'].tolist(),
            'closes': df['close'].tolist()
        }
        
    except Exception as e:
        print(f"获取指数数据失败: {e}")
        return None


def simulate_trades(stock_data_list, period, initial_capital, rebalance_strategy, commission_rate, stamp_duty, slippage):
    """
    模拟交易
    
    参数:
    - stock_data_list: 股票历史数据列表
    - period: 回测天数
    - initial_capital: 初始资金
    - rebalance_strategy: 再平衡策略 (none/monthly/quarterly/threshold)
    - commission_rate: 佣金费率
    - stamp_duty: 印花税率
    - slippage: 滑点
    """
    
    if not stock_data_list:
        return [], []
    
    # 等权重分配
    n_stocks = len(stock_data_list)
    target_weight = 1.0 / n_stocks
    
    # 初始化持仓
    cash = initial_capital
    positions = {}  # {code: {'shares': x, 'cost': y}}
    trades = []  # 交易记录
    daily_values = []  # 每日组合价值
    
    # 获取所有股票的日期和价格
    min_len = min(len(s['data']['closes']) for s in stock_data_list)
    ref_dates = stock_data_list[0]['data']['dates'][:min_len]
    
    # 第一天建仓
    first_day_prices = {}
    for stock_data in stock_data_list:
        code = stock_data['code']
        closes = stock_data['data']['closes']
        if closes and closes[0] > 0:
            first_day_prices[code] = closes[0]
    
    # 买入建仓
    for stock_data in stock_data_list:
        code = stock_data['code']
        closes = stock_data['data']['closes']
        
        if code not in first_day_prices or first_day_prices[code] <= 0:
            continue
        
        price = first_day_prices[code]
        # 考虑滑点 (买入时滑点不利)
        buy_price = price * (1 + slippage)
        
        # 计算买入金额
        allocate_amount = cash * target_weight
        shares = int(allocate_amount / buy_price / 100) * 100  # 整手
        
        if shares > 0:
            actual_amount = shares * buy_price
            commission = actual_amount * commission_rate
            
            positions[code] = {
                'shares': shares,
                'cost': buy_price,
                'name': stock_data['name']
            }
            cash -= (actual_amount + commission)
            
            trades.append({
                'date': ref_dates[0],
                'code': code,
                'name': stock_data['name'],
                'action': '买入',
                'shares': shares,
                'price': round(buy_price, 2),
                'amount': round(actual_amount, 2),
                'commission': round(commission, 2),
                'reason': '建仓'
            })
    
    # 每日再平衡检查
    rebalance_interval = 21  # 每月约21个交易日
    if rebalance_strategy == 'quarterly':
        rebalance_interval = 63
    elif rebalance_strategy == 'threshold':
        rebalance_interval = 999999  # 不会自动触发
    
    last_rebalance_day = 0
    
    for day in range(1, min_len):
        # 计算当前持仓价值
        current_value = cash
        for code, pos in positions.items():
            stock_data = next((s for s in stock_data_list if s['code'] == code), None)
            if stock_data:
                closes = stock_data['data']['closes']
                if day < len(closes) and closes[day] > 0:
                    current_value += pos['shares'] * closes[day]
        
        # 检查是否需要再平衡
        need_rebalance = False
        
        if rebalance_strategy == 'monthly' and day - last_rebalance_day >= rebalance_interval:
            need_rebalance = True
        elif rebalance_strategy == 'quarterly' and day - last_rebalance_day >= rebalance_interval:
            need_rebalance = True
        elif rebalance_strategy == 'threshold':
            # 检查各持仓权重偏差
            for code, pos in positions.items():
                stock_data = next((s for s in stock_data_list if s['code'] == code), None)
                if stock_data:
                    closes = stock_data['data']['closes']
                    if day < len(closes) and closes[day] > 0:
                        pos_value = pos['shares'] * closes[day]
                        current_weight = pos_value / current_value if current_value > 0 else 0
                        if abs(current_weight - target_weight) > 0.1:  # 偏差超过10%
                            need_rebalance = True
                            break
        
        if need_rebalance and rebalance_strategy != 'none':
            # 再平衡: 卖出所有持仓，再按目标权重买入
            # 先卖出
            for code, pos in list(positions.items()):
                stock_data = next((s for s in stock_data_list if s['code'] == code), None)
                if stock_data:
                    closes = stock_data['data']['closes']
                    if day < len(closes) and closes[day] > 0:
                        sell_price = closes[day] * (1 - slippage)  # 考虑滑点
                        sell_value = pos['shares'] * sell_price
                        commission = sell_value * commission_rate
                        stamp = sell_value * stamp_duty  # 印花税
                        
                        cash += (sell_value - commission - stamp)
                        
                        trades.append({
                            'date': ref_dates[day],
                            'code': code,
                            'name': pos['name'],
                            'action': '卖出',
                            'shares': pos['shares'],
                            'price': round(sell_price, 2),
                            'amount': round(sell_value, 2),
                            'commission': round(commission + stamp, 2),
                            'reason': '再平衡'
                        })
            
            positions = {}
            last_rebalance_day = day
            
            # 再买入
            for stock_data in stock_data_list:
                code = stock_data['code']
                closes = stock_data['data']['closes']
                
                if day < len(closes) and closes[day] > 0:
                    buy_price = closes[day] * (1 + slippage)
                    
                    allocate_amount = cash * target_weight
                    shares = int(allocate_amount / buy_price / 100) * 100
                    
                    if shares > 0:
                        actual_amount = shares * buy_price
                        commission = actual_amount * commission_rate
                        
                        positions[code] = {
                            'shares': shares,
                            'cost': buy_price,
                            'name': stock_data['name']
                        }
                        cash -= (actual_amount + commission)
                        
                        trades.append({
                            'date': ref_dates[day],
                            'code': code,
                            'name': stock_data['name'],
                            'action': '买入',
                            'shares': shares,
                            'price': round(buy_price, 2),
                            'amount': round(actual_amount, 2),
                            'commission': round(commission, 2),
                            'reason': '再平衡'
                        })
        
        # 记录每日价值
        day_value = cash
        for code, pos in positions.items():
            stock_data = next((s for s in stock_data_list if s['code'] == code), None)
            if stock_data:
                closes = stock_data['data']['closes']
                if day < len(closes) and closes[day] > 0:
                    day_value += pos['shares'] * closes[day]
        
        daily_values.append(day_value)
    
    return trades, daily_values


@stock_backtest_bp.route('/backtest', methods=['POST'])
def run_stock_backtest():
    """股票回测"""
    data = request.get_json() or {}
    stocks = data.get('stocks', [])
    period = int(data.get('period', 60))
    benchmark = data.get('benchmark', 'sh.000300')
    initial_capital = float(data.get('initialCapital', 1000000))
    
    # 新增参数
    rebalance_strategy = data.get('rebalanceStrategy', 'none')
    commission_rate = float(data.get('commissionRate', 0.0003))
    stamp_duty = float(data.get('stampDuty', 0.001))
    slippage = float(data.get('slippage', 0.001))
    
    if not stocks:
        return jsonify({'success': False, 'message': '请选择股票'})
    
    # 获取基准指数数据
    index_data = get_index_historical_data(benchmark, period)
    
    if not index_data:
        index_data = get_index_historical_data('sh.000001', period)
    
    if not index_data:
        return jsonify({'success': False, 'message': '无法获取基准指数数据'})
    
    # 获取各股票数据
    stock_data_list = []
    valid_stocks = []
    
    for stock_code in stocks[:20]:
        if isinstance(stock_code, dict):
            code = stock_code.get('code', '')
            name = stock_code.get('name', code)
        else:
            code = str(stock_code)
            name = code
        
        code = code.strip().replace('.sh', '').replace('.sz', '')
        
        if not code:
            continue
        
        hist_data = get_stock_historical_data(code, period)
        
        if hist_data and len(hist_data['closes']) >= 10:
            valid_closes = [c for c in hist_data['closes'] if c and c > 0]
            if len(valid_closes) >= 10:
                stock_data_list.append({
                    'code': code,
                    'name': name,
                    'data': hist_data
                })
                valid_stocks.append({'code': code, 'name': name})
    
    if not stock_data_list:
        return jsonify({'success': False, 'message': '无法获取股票数据'})
    
    # 对齐数据
    min_len = min(len(s['data']['closes']) for s in stock_data_list)
    min_len = min(min_len, len(index_data['closes']))
    
    aligned_dates = index_data['dates'][-min_len:]
    aligned_benchmark = index_data['closes'][-min_len:]
    
    # 模拟交易
    trades, portfolio_values = simulate_trades(
        stock_data_list, 
        min_len, 
        initial_capital, 
        rebalance_strategy,
        commission_rate,
        stamp_duty,
        slippage
    )
    
    # 如果没有交易记录（不再平衡），使用简单计算
    if not portfolio_values:
        # 简单计算组合净值
        portfolio_values = [initial_capital]
        for i in range(1, min_len):
            daily_return = 0
            valid_count = 0
            for stock_data in stock_data_list:
                closes = stock_data['data']['closes']
                if i > 0 and closes[i-1] > 0 and closes[i] > 0:
                    ret = (closes[i] - closes[i-1]) / closes[i-1]
                    daily_return += ret
                    valid_count += 1
            if valid_count > 0:
                daily_return /= valid_count
            portfolio_values.append(portfolio_values[-1] * (1 + daily_return))
    
    # 计算基准累计净值
    benchmark_values = [initial_capital]
    for i in range(1, min_len):
        if aligned_benchmark[i-1] > 0 and aligned_benchmark[i] > 0:
            ret = (aligned_benchmark[i] - aligned_benchmark[i-1]) / aligned_benchmark[i-1]
            benchmark_values.append(benchmark_values[-1] * (1 + ret))
        else:
            benchmark_values.append(benchmark_values[-1])
    
    # 计算指标
    if portfolio_values[-1] > 0 and initial_capital > 0:
        total_return = (portfolio_values[-1] - initial_capital) / initial_capital * 100
    else:
        total_return = 0
    
    years = min_len / 252
    if portfolio_values[-1] > 0 and initial_capital > 0 and years > 0:
        annual_return = ((portfolio_values[-1] / initial_capital) ** (1 / years) - 1) * 100
    else:
        annual_return = 0
    
    # 波动率
    daily_returns = []
    for i in range(1, len(portfolio_values)):
        ret = (portfolio_values[i] - portfolio_values[i-1]) / portfolio_values[i-1]
        daily_returns.append(ret)
    
    if daily_returns:
        volatility = math.sqrt(sum([r**2 for r in daily_returns]) / len(daily_returns)) * math.sqrt(252) * 100
    else:
        volatility = 0
    
    # 夏普比率
    risk_free = 0.025
    sharpe = (annual_return/100 - risk_free) / (volatility/100) if volatility > 0 else 0
    
    # 最大回撤
    peak = portfolio_values[0] if portfolio_values else 0
    max_drawdown = 0
    for v in portfolio_values:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak * 100
            if dd > max_drawdown:
                max_drawdown = dd
    
    # 阿尔法
    if aligned_benchmark[-1] > 0 and aligned_benchmark[0] > 0:
        benchmark_return = (aligned_benchmark[-1] - aligned_benchmark[0]) / aligned_benchmark[0] * 100
    else:
        benchmark_return = 0
    alpha = annual_return - benchmark_return
    
    # 生成月度收益
    monthly_returns = []
    for i in range(0, min_len, 21):
        if i > 0 and i < len(portfolio_values):
            if portfolio_values[i-1] > 0:
                monthly_ret = (portfolio_values[min(i+20, len(portfolio_values)-1)] / portfolio_values[i-1] - 1) * 100
                monthly_returns.append(round(monthly_ret, 2))
            else:
                monthly_returns.append(0)
        else:
            monthly_returns.append(0)
    
    # 持仓分析 - 使用最新价格
    position_analysis = []
    final_prices = {}
    for stock_data in stock_data_list:
        closes = stock_data['data']['closes']
        if closes and closes[-1] > 0:
            final_prices[stock_data['code']] = closes[-1]
    
    # 计算最终各持仓市值
    final_value = portfolio_values[-1] if portfolio_values else initial_capital
    
    # 统计交易次数
    buy_count = sum(1 for t in trades if t['action'] == '买入')
    sell_count = sum(1 for t in trades if t['action'] == '卖出')
    total_trades = buy_count + sell_count
    
    # 计算总交易成本
    total_commission = sum(t.get('commission', 0) for t in trades)
    
    # 简化: 按等权重显示持仓
    for stock_data in stock_data_list[:10]:
        code = stock_data['code']
        closes = stock_data['data']['closes']
        
        if len(closes) >= 2 and closes[0] > 0 and closes[-1] > 0:
            stock_return = (closes[-1] - closes[0]) / closes[0] * 100
        else:
            stock_return = 0
        
        # 估算当前持仓市值
        if code in final_prices and trades:
            # 找到该股票最近一次买入
            last_buy = None
            for t in reversed(trades):
                if t['code'] == code and t['action'] == '买入':
                    last_buy = t
                    break
            
            if last_buy:
                current_value = last_buy['shares'] * final_prices[code]
                weight = (current_value / final_value * 100) if final_value > 0 else 0
            else:
                weight = 100 / len(stock_data_list)
        else:
            weight = 100 / len(stock_data_list)
        
        position_analysis.append({
            'code': code,
            'name': stock_data['name'],
            'weight': round(weight, 2),
            'return': round(stock_return, 2)
        })
    
    result = {
        'success': True,
        'data': {
            'summary': {
                'total_return': round(total_return, 2),
                'annual_return': round(annual_return, 2),
                'benchmark_return': round(benchmark_return, 2),
                'alpha': round(alpha, 2),
                'volatility': round(volatility, 2),
                'sharpe_ratio': round(sharpe, 2),
                'max_drawdown': round(max_drawdown, 2),
                'initial_capital': initial_capital,
                'final_value': round(portfolio_values[-1], 2) if portfolio_values else initial_capital,
                'stock_count': len(stock_data_list),
                'total_trades': total_trades,
                'buy_trades': buy_count,
                'sell_trades': sell_count,
                'total_commission': round(total_commission, 2)
            },
            'curve': {
                'dates': aligned_dates,
                'portfolio': [round(v, 2) for v in portfolio_values] if portfolio_values else [initial_capital],
                'benchmark': [round(v, 2) for v in benchmark_values]
            },
            'monthly': {
                'returns': monthly_returns
            },
            'positions': position_analysis,
            'trades': trades[-50:] if trades else []  # 最多返回50条交易记录
        }
    }
    
    return jsonify(result)


@stock_backtest_bp.route('/stocks/<stock_code>/info', methods=['GET'])
def get_stock_info(stock_code):
    """获取股票基本信息"""
    try:
        code = stock_code.replace('.sh', '').replace('.sz', '')
        
        rs = bs.query_stock_basic(code=f"{'sh.' if code.startswith('6') else 'sz.'}{code}")
        
        data = rs.get_row_data()
        
        if data:
            return jsonify({
                'success': True,
                'data': {
                    'code': code,
                    'name': data[1] if len(data) > 1 else code,
                    'industry': '',
                    'market': data[3] if len(data) > 3 else ''
                }
            })
        
        return jsonify({'success': False, 'message': '无法获取股票信息'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
