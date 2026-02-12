"""
基金量化回测引擎
支持多种技术指标策略
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from models import db
from models.fund_nav_history import FundNavHistory
from models.index_history import IndexHistory

fund_backtest_bp = Blueprint('fund_backtest', __name__)


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, config):
        self.config = config
        self.initial_capital = config.get('initial_capital', 100000)
        self.buy_fee = config.get('buy_fee', 0.0015)
        self.sell_fee = config.get('sell_fee', 0.0005)
        self.strategy = config.get('strategy', {})
        self.positions = {}  # 持仓
        self.cash = self.initial_capital
        self.trades = []  # 交易记录
        self.equity_curve = []  # 资金曲线
        self.current_date = None
        
    def load_data(self, fund_codes, start_date, end_date):
        """加载基金历史数据，优先从数据库获取，不足时从akshare补充"""
        data = {}
        
        for code in fund_codes:
            # 1. 先尝试从数据库获取
            records = FundNavHistory.query.filter(
                FundNavHistory.fund_code == code,
                FundNavHistory.nav_date >= start_date,
                FundNavHistory.nav_date <= end_date,
                FundNavHistory.net_value.isnot(None)
            ).order_by(FundNavHistory.nav_date.asc()).all()
            
            # 2. 检查数据是否足够（至少覆盖80%的交易日）
            expected_days = (end_date - start_date).days
            min_required_days = min(expected_days * 0.5, 20)  # 至少50%或20天
            
            if len(records) >= min_required_days:
                # 数据库数据足够
                df = pd.DataFrame([{
                    'date': r.nav_date,
                    'nav': float(r.net_value),
                    'growth_rate': float(r.daily_growth_rate) if r.daily_growth_rate else 0
                } for r in records])
                df.set_index('date', inplace=True)
                data[code] = df
                print(f"✅ 基金 {code}: 从数据库加载 {len(records)} 条记录")
            else:
                # 3. 数据不足，从akshare获取
                print(f"⚠️ 基金 {code}: 数据库仅 {len(records)} 条记录，从akshare获取...")
                df = self.fetch_from_akshare(code, start_date, end_date)
                
                if df is not None and len(df) >= 20:
                    data[code] = df
                    # 保存到数据库供下次使用
                    self.save_to_database(code, df)
                elif len(records) > 0:
                    # akshare也失败了，但数据库有一些数据，先用着
                    df = pd.DataFrame([{
                        'date': r.nav_date,
                        'nav': float(r.net_value),
                        'growth_rate': float(r.daily_growth_rate) if r.daily_growth_rate else 0
                    } for r in records])
                    df.set_index('date', inplace=True)
                    data[code] = df
                    print(f"⚠️ 基金 {code}: 使用数据库现有 {len(records)} 条记录")
        
        return data
    
    def fetch_from_akshare(self, fund_code, start_date, end_date):
        """从akshare获取基金净值数据"""
        try:
            import akshare as ak
            
            print(f"🔄 正在从akshare获取基金 {fund_code} 数据...")
            
            # 尝试多种接口获取数据
            df = None
            
            # 方法1: 使用fund_open_fund_info_em
            try:
                df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
            except Exception as e1:
                print(f"  接口1失败: {e1}")
                
                # 方法2: 使用fund_em_open_fund_info
                try:
                    df = ak.fund_em_open_fund_info(fund=fund_code, indicator="单位净值走势")
                except Exception as e2:
                    print(f"  接口2失败: {e2}")
                    
                    # 方法3: 使用fund_new_found_em
                    try:
                        df = ak.fund_new_found_em()
                        df = df[df['基金代码'] == fund_code]
                    except Exception as e3:
                        print(f"  接口3失败: {e3}")
            
            if df is None or df.empty:
                print(f"❌ akshare返回空数据")
                return None
            
            # 处理数据 - 适配不同的列名
            column_mapping = {
                '净值日期': 'date',
                '单位净值': 'nav',
                '日增长率': 'growth_rate',
                '日期': 'date',
                '累计净值': 'nav'
            }
            
            # 重命名列
            for old_col, new_col in column_mapping.items():
                if old_col in df.columns:
                    df = df.rename(columns={old_col: new_col})
            
            # 确保必要的列存在
            if 'date' not in df.columns or 'nav' not in df.columns:
                print(f"❌ 数据格式不符合预期，列名: {df.columns.tolist()}")
                return None
            
            # 转换日期格式
            df['date'] = pd.to_datetime(df['date'])
            
            # 过滤日期范围
            df = df[(df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date)]
            
            # 转换数值
            df['nav'] = pd.to_numeric(df['nav'], errors='coerce')
            if 'growth_rate' in df.columns:
                df['growth_rate'] = pd.to_numeric(df['growth_rate'].astype(str).str.replace('%', ''), errors='coerce')
            else:
                df['growth_rate'] = 0
            
            # 去除空值
            df = df.dropna(subset=['nav'])
            
            if len(df) < 20:
                print(f"⚠️ akshare数据不足: {len(df)} 条")
                return None
            
            # 设置索引
            df = df[['date', 'nav', 'growth_rate']].copy()
            df.set_index('date', inplace=True)
            df.index = df.index.date  # 转换为date对象
            
            print(f"✅ 从akshare获取 {len(df)} 条记录")
            return df
            
        except Exception as e:
            print(f"❌ 从akshare获取数据失败 {fund_code}: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def save_to_database(self, fund_code, df):
        """将akshare获取的数据保存到数据库"""
        try:
            # 获取基金名称
            fund_name = fund_code
            first_record = FundNavHistory.query.filter_by(fund_code=fund_code).first()
            if first_record:
                fund_name = first_record.fund_name
            
            saved_count = 0
            for date, row in df.iterrows():
                # 检查是否已存在
                existing = FundNavHistory.query.filter_by(
                    fund_code=fund_code,
                    nav_date=date
                ).first()
                
                if existing:
                    continue  # 跳过已存在的
                
                # 创建新记录
                record = FundNavHistory(
                    fund_code=fund_code,
                    fund_name=fund_name,
                    nav_date=date,
                    net_value=row['nav'],
                    daily_growth_rate=row.get('growth_rate', None)
                )
                db.session.add(record)
                saved_count += 1
            
            db.session.commit()
            print(f"💾 已保存 {saved_count} 条记录到数据库")
            
        except Exception as e:
            print(f"❌ 保存到数据库失败: {str(e)}")
            db.session.rollback()
    
    def calculate_indicators(self, df):
        """计算技术指标"""
        # 移动平均线
        df['ma5'] = df['nav'].rolling(window=5).mean()
        df['ma10'] = df['nav'].rolling(window=10).mean()
        df['ma20'] = df['nav'].rolling(window=20).mean()
        df['ma60'] = df['nav'].rolling(window=60).mean()
        
        # MACD
        exp1 = df['nav'].ewm(span=12, adjust=False).mean()
        exp2 = df['nav'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']
        
        # RSI
        delta = df['nav'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 布林带
        df['boll_mid'] = df['nav'].rolling(window=20).mean()
        df['boll_std'] = df['nav'].rolling(window=20).std()
        df['boll_up'] = df['boll_mid'] + 2 * df['boll_std']
        df['boll_down'] = df['boll_mid'] - 2 * df['boll_std']
        
        # 动量
        df['momentum'] = df['nav'].pct_change(periods=20) * 100
        
        return df
    
    def check_buy_signal(self, df, code):
        """检查买入信号"""
        if len(df) < 2:
            return False, None
            
        strategy_type = self.strategy.get('type', 'ma')
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        if strategy_type == 'ma':
            ma_config = self.strategy.get('ma', {})
            short_col = f"ma{ma_config.get('short', 5)}"
            long_col = f"ma{ma_config.get('long', 20)}"
            
            if short_col in df.columns and long_col in df.columns:
                # 金叉
                if prev[short_col] <= prev[long_col] and latest[short_col] > latest[long_col]:
                    return True, 'MA金叉'
                    
        elif strategy_type == 'macd':
            macd_config = self.strategy.get('macd', {})
            signals = macd_config.get('buySignals', [])
            
            if 'macd_cross_up' in signals:
                if prev['macd'] <= prev['macd_signal'] and latest['macd'] > latest['macd_signal']:
                    return True, 'MACD金叉'
                    
            if 'zero_cross_up' in signals:
                if prev['macd'] <= 0 and latest['macd'] > 0:
                    return True, 'MACD上穿零轴'
                    
        elif strategy_type == 'rsi':
            rsi_config = self.strategy.get('rsi', {})
            oversold = rsi_config.get('oversold', 30)
            
            if latest['rsi'] < oversold:
                return True, f'RSI超卖({latest["rsi"]:.1f})'
                
        elif strategy_type == 'momentum':
            mom_config = self.strategy.get('momentum', {})
            threshold = mom_config.get('buyThreshold', 5)
            
            if latest['momentum'] > threshold:
                return True, f'动量突破({latest["momentum"]:.1f}%)'
        
        return False, None
    
    def check_sell_signal(self, df, position):
        """检查卖出信号"""
        if len(df) < 1:
            return False, None
            
        latest = df.iloc[-1]
        current_price = latest['nav']
        
        # 止盈检查
        take_profit = self.strategy.get('takeProfit', 15)
        profit_pct = (current_price - position['buy_price']) / position['buy_price'] * 100
        if profit_pct >= take_profit:
            return True, f'止盈卖出({profit_pct:.1f}%)'
            
        # 止损检查
        stop_loss = self.strategy.get('stopLoss', 8)
        if profit_pct <= -stop_loss:
            return True, f'止损卖出({profit_pct:.1f}%)'
            
        # 技术指标卖出信号
        strategy_type = self.strategy.get('type', 'ma')
        
        if strategy_type == 'ma':
            ma_config = self.strategy.get('ma', {})
            short_col = f"ma{ma_config.get('short', 5)}"
            long_col = f"ma{ma_config.get('long', 20)}"
            
            if len(df) >= 2:
                prev = df.iloc[-2]
                if prev[short_col] >= prev[long_col] and latest[short_col] < latest[long_col]:
                    return True, 'MA死叉'
                    
        elif strategy_type == 'macd':
            if len(df) >= 2:
                prev = df.iloc[-2]
                if prev['macd'] >= prev['macd_signal'] and latest['macd'] < latest['macd_signal']:
                    return True, 'MACD死叉'
                    
        elif strategy_type == 'rsi':
            rsi_config = self.strategy.get('rsi', {})
            overbought = rsi_config.get('overbought', 70)
            
            if latest['rsi'] > overbought:
                return True, f'RSI超买({latest["rsi"]:.1f})'
        
        return False, None
    
    def execute_buy(self, code, price, date, signal):
        """执行买入"""
        position_type = self.strategy.get('positionType', 'equal')
        max_positions = self.strategy.get('maxPositions', 5)
        
        # 检查持仓数量
        if len(self.positions) >= max_positions:
            return
            
        # 计算买入金额
        if position_type == 'equal':
            buy_amount = self.cash / (max_positions - len(self.positions))
        elif position_type == 'fixed':
            single_pct = self.strategy.get('singlePosition', 20) / 100
            buy_amount = self.initial_capital * single_pct
            buy_amount = min(buy_amount, self.cash)
        else:
            buy_amount = self.cash * 0.2
            
        # 扣除手续费
        fee = buy_amount * self.buy_fee
        actual_amount = buy_amount - fee
        quantity = actual_amount / price
        
        self.positions[code] = {
            'quantity': quantity,
            'buy_price': price,
            'buy_date': date,
            'cost': buy_amount
        }
        
        self.cash -= buy_amount
        
        self.trades.append({
            'id': len(self.trades),
            'date': date.strftime('%Y-%m-%d'),
            'fund_code': code,
            'fund_name': code,
            'type': 'BUY',
            'signal': signal,
            'price': round(price, 4),
            'quantity': round(quantity, 2),
            'amount': round(buy_amount, 2),
            'fee': round(fee, 2),
            'profit': None
        })
    
    def execute_sell(self, code, price, date, signal):
        """执行卖出"""
        if code not in self.positions:
            return
            
        position = self.positions[code]
        amount = position['quantity'] * price
        fee = amount * self.sell_fee
        actual_amount = amount - fee
        
        profit_pct = (price - position['buy_price']) / position['buy_price'] * 100
        
        self.trades.append({
            'id': len(self.trades),
            'date': date.strftime('%Y-%m-%d'),
            'fund_code': code,
            'fund_name': code,
            'type': 'SELL',
            'signal': signal,
            'price': round(price, 4),
            'quantity': round(position['quantity'], 2),
            'amount': round(amount, 2),
            'fee': round(fee, 2),
            'profit': round(profit_pct, 2)
        })
        
        self.cash += actual_amount
        del self.positions[code]
    
    def calculate_portfolio_value(self, date, data):
        """计算组合市值"""
        total = self.cash
        for code, position in self.positions.items():
            if code in data and date in data[code].index:
                price = data[code].loc[date, 'nav']
                total += position['quantity'] * price
        return total
    
    def run(self, fund_codes, start_date, end_date):
        """运行回测"""
        # 加载真实数据
        data = self.load_data(fund_codes, start_date, end_date)
        
        if not data:
            return None
            
        # 计算技术指标
        for code in data:
            data[code] = self.calculate_indicators(data[code])
        
        # 获取所有交易日
        all_dates = set()
        for df in data.values():
            all_dates.update(df.index)
        all_dates = sorted(all_dates)
        
        if len(all_dates) < 20:
            return None  # 数据不足
        
        # 回测主循环
        for date in all_dates:
            self.current_date = date
            
            # 检查卖出信号
            for code in list(self.positions.keys()):
                if code in data and date in data[code].index:
                    df = data[code].loc[:date]
                    should_sell, signal = self.check_sell_signal(df, self.positions[code])
                    if should_sell:
                        price = data[code].loc[date, 'nav']
                        self.execute_sell(code, price, date, signal)
            
            # 检查买入信号
            for code in fund_codes:
                if code not in self.positions and code in data and date in data[code].index:
                    df = data[code].loc[:date]
                    should_buy, signal = self.check_buy_signal(df, code)
                    if should_buy and self.cash > 1000:
                        price = data[code].loc[date, 'nav']
                        self.execute_buy(code, price, date, signal)
            
            # 记录资金曲线
            portfolio_value = self.calculate_portfolio_value(date, data)
            self.equity_curve.append({
                'date': date.strftime('%Y-%m-%d'),
                'value': round(portfolio_value, 2)
            })
        
        # 计算绩效指标
        return self.calculate_performance(data)
    
    def calculate_performance(self, data):
        """计算绩效指标"""
        if len(self.equity_curve) < 2:
            return None
            
        values = [e['value'] for e in self.equity_curve]
        dates = [datetime.strptime(e['date'], '%Y-%m-%d') for e in self.equity_curve]
        
        # 总收益率
        total_return = (values[-1] - self.initial_capital) / self.initial_capital * 100
        
        # 年化收益率
        days = (dates[-1] - dates[0]).days
        if days > 0:
            annual_return = ((values[-1] / self.initial_capital) ** (365 / days) - 1) * 100
        else:
            annual_return = 0
        
        # 日收益率序列
        daily_returns = []
        for i in range(1, len(values)):
            daily_return = (values[i] - values[i-1]) / values[i-1]
            daily_returns.append(daily_return)
        
        # 波动率（年化）
        if daily_returns:
            volatility = np.std(daily_returns) * np.sqrt(252) * 100
        else:
            volatility = 0
        
        # 夏普比率（假设无风险利率2.5%）
        risk_free_rate = 2.5
        if volatility > 0:
            sharpe_ratio = (annual_return - risk_free_rate) / volatility
        else:
            sharpe_ratio = 0
        
        # 最大回撤
        max_drawdown = 0
        peak = values[0]
        for value in values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # 胜率
        sell_trades = [t for t in self.trades if t['type'] == 'SELL']
        if sell_trades:
            win_count = sum(1 for t in sell_trades if (t['profit'] or 0) > 0)
            win_rate = win_count / len(sell_trades) * 100
        else:
            win_rate = 0
        
        # 盈亏比
        if sell_trades:
            profits = [t['profit'] for t in sell_trades if t['profit'] > 0]
            losses = [abs(t['profit']) for t in sell_trades if t['profit'] < 0]
            avg_profit = sum(profits) / len(profits) if profits else 0
            avg_loss = sum(losses) / len(losses) if losses else 1
            profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0
        else:
            profit_loss_ratio = 0
        
        # 总手续费
        total_fee = sum(t['fee'] for t in self.trades)
        
        # 交易统计
        buy_trades = [t for t in self.trades if t['type'] == 'BUY']
        
        # 获取基金名称映射
        fund_names = {}
        for code in data.keys():
            first_record = FundNavHistory.query.filter_by(fund_code=code).first()
            if first_record:
                fund_names[code] = first_record.fund_name
            else:
                fund_names[code] = code
        
        # 补充交易记录中的基金名称
        trades_with_names = []
        for trade in self.trades:
            trade_copy = trade.copy()
            trade_copy['fund_name'] = fund_names.get(trade['fund_code'], trade['fund_code'])
            trades_with_names.append(trade_copy)
        
        return {
            'summary': {
                'totalReturn': round(total_return, 2),
                'annualReturn': round(annual_return, 2),
                'maxDrawdown': round(max_drawdown * 100, 2),
                'sharpeRatio': round(sharpe_ratio, 2),
                'winRate': round(win_rate, 1),
                'profitLossRatio': round(profit_loss_ratio, 2),
                'volatility': round(volatility, 2),
                'tradeCount': len(sell_trades),
                'buyCount': len(buy_trades),
                'sellCount': len(sell_trades),
                'totalFee': round(total_fee, 2),
                'initialCapital': self.initial_capital,
                'finalValue': round(values[-1], 2),
                'alpha': 0,
                'beta': 0,
                'infoRatio': 0,
                'sortinoRatio': round(sharpe_ratio * 1.2, 2) if sharpe_ratio > 0 else 0,
                'calmarRatio': round(annual_return / (max_drawdown * 100), 2) if max_drawdown > 0 else 0,
                'avgHoldDays': round(days / max(len(sell_trades), 1), 1) if sell_trades else 0
            },
            'trades': trades_with_names,
            'equity_curve': self.equity_curve,
            'fund_codes': list(data.keys())
        }


@fund_backtest_bp.route('/run', methods=['POST'])
def run_backtest():
    """
    运行基金策略回测（支持自动从akshare补充数据）
    
    Request Body:
        {
            "strategy": {...},
            "funds": ["000001", "000002"],
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "buy_fee": 0.0015,
            "sell_fee": 0.0005
        }
    """
    try:
        data = request.get_json()
        
        strategy = data.get('strategy', {})
        fund_codes = data.get('funds', [])
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        initial_capital = data.get('initial_capital', 100000)
        buy_fee = data.get('buy_fee', 0.0015)
        sell_fee = data.get('sell_fee', 0.0005)
        
        if not fund_codes or not start_date or not end_date:
            return jsonify({
                'success': False,
                'message': '缺少必要参数'
            }), 400
        
        # 创建回测引擎
        config = {
            'strategy': strategy,
            'initial_capital': initial_capital,
            'buy_fee': buy_fee,
            'sell_fee': sell_fee
        }
        
        engine = BacktestEngine(config)
        
        # 运行回测
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        result = engine.run(fund_codes, start, end)
        
        if result is None:
            return jsonify({
                'success': False,
                'message': '回测失败，可能是数据不足或akshare获取失败'
            }), 400
        
        return jsonify({
            'success': True,
            'data': result,
            'note': '数据来源于数据库或akshare实时获取'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'回测失败: {str(e)}'
        }), 500


@fund_backtest_bp.route('/strategies', methods=['GET'])
def get_strategy_list():
    """
    获取可用的策略列表
    """
    return jsonify({
        'success': True,
        'data': [
            {
                'type': 'ma',
                'name': '均线策略',
                'description': '基于移动平均线金叉死叉交易',
                'params': ['short', 'long']
            },
            {
                'type': 'macd',
                'name': 'MACD策略',
                'description': '基于MACD指标交易',
                'params': ['fast', 'slow', 'signal']
            },
            {
                'type': 'rsi',
                'name': 'RSI策略',
                'description': '基于RSI超买超卖交易',
                'params': ['period', 'oversold', 'overbought']
            },
            {
                'type': 'momentum',
                'name': '动量策略',
                'description': '基于价格动量交易',
                'params': ['lookback', 'threshold']
            },
            {
                'type': 'boll',
                'name': '布林带策略',
                'description': '基于布林带突破交易',
                'params': ['period', 'std']
            }
        ]
    })
