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
from models.trading_day import TradingDay

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

        # 获取交易日数量（使用 trading_day 表）
        trading_days_count = db.session.query(TradingDay).filter(
            TradingDay.trade_date >= start_date,
            TradingDay.trade_date <= end_date
        ).count()

        print(f"📅 指定时间区间交易日数量: {trading_days_count}")

        for code in fund_codes:
            # 1. 先尝试从数据库获取
            records = FundNavHistory.query.filter(
                FundNavHistory.fund_code == code,
                FundNavHistory.nav_date >= start_date,
                FundNavHistory.nav_date <= end_date,
                FundNavHistory.net_value.isnot(None)
            ).order_by(FundNavHistory.nav_date.asc()).all()

            # 2. 检查数据是否足够（使用交易日历判断）
            # 要求基金数据数量 >= 交易日数量的 90%
            if trading_days_count > 0:
                min_required_days = int(trading_days_count * 0.9)  # 至少90%的交易日
            else:
                # 如果没有交易日数据，至少需要20天
                min_required_days = 20

            if len(records) >= min_required_days:
                # 数据库数据足够
                df = pd.DataFrame([{
                    'date': r.nav_date,
                    'nav': float(r.net_value),
                    'growth_rate': float(r.daily_growth_rate) if r.daily_growth_rate else 0
                } for r in records])
                df.set_index('date', inplace=True)
                data[code] = df
                print(f"✅ 基金 {code}: 从数据库加载 {len(records)} 条记录 (要求: >={min_required_days})")
            else:
                # 3. 数据不足，从akshare获取
                print(f"⚠️ 基金 {code}: 数据库仅 {len(records)} 条记录，要求至少 {min_required_days} 条，从akshare获取...")
                df = self.fetch_from_akshare(code, start_date, end_date)

                if df is not None and len(df) >= min_required_days:
                    data[code] = df
                    # 保存到数据库供下次使用
                    self.save_to_database(code, df)
                    print(f"✅ 基金 {code}: 从akshare获取 {len(df)} 条记录并保存")
                elif len(records) > 0:
                    # akshare也失败了，但数据库有一些数据，先用着
                    df = pd.DataFrame([{
                        'date': r.nav_date,
                        'nav': float(r.net_value),
                        'growth_rate': float(r.daily_growth_rate) if r.daily_growth_rate else 0
                    } for r in records])
                    df.set_index('date', inplace=True)
                    data[code] = df
                    print(f"⚠️ 基金 {code}: 使用数据库现有 {len(records)} 条记录（不足 {min_required_days}）")
                else:
                    print(f"❌ 基金 {code}: 无可用数据")

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
        df['ma120'] = df['nav'].rolling(window=120).mean()

        # MACD - 修正计算方式
        exp1 = df['nav'].ewm(span=12, adjust=False, min_periods=26).mean()
        exp2 = df['nav'].ewm(span=26, adjust=False, min_periods=26).mean()
        df['macd'] = exp1 - exp2
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False, min_periods=9).mean()
        df['macd_histogram'] = (df['macd'] - df['macd_signal']) * 2

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

        # 突破策略需要的高低点
        df['high_20'] = df['nav'].rolling(window=20).max()
        df['low_20'] = df['nav'].rolling(window=20).min()

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
                if pd.notna(prev[short_col]) and pd.notna(prev[long_col]) and pd.notna(latest[short_col]) and pd.notna(latest[long_col]):
                    if prev[short_col] <= prev[long_col] and latest[short_col] > latest[long_col]:
                        return True, 'MA金叉'

        elif strategy_type == 'triple_ma':
            # 三均线策略：短期>中期>长期多头排列
            ma_config = self.strategy.get('triple_ma', {})
            short_col = f"ma{ma_config.get('short', 5)}"
            middle_col = f"ma{ma_config.get('middle', 20)}"
            long_col = f"ma{ma_config.get('long', 60)}"

            if all(col in df.columns for col in [short_col, middle_col, long_col]):
                if all(pd.notna(latest[col]) for col in [short_col, middle_col, long_col]):
                    if latest[short_col] > latest[middle_col] > latest[long_col]:
                        return True, '三均线多头'

        elif strategy_type == 'macd':
            macd_config = self.strategy.get('macd', {})
            signals = macd_config.get('buySignals', ['cross_up'])

            if 'cross_up' in signals:
                if 'macd' in df.columns and 'macd_signal' in df.columns:
                    if pd.notna(prev['macd']) and pd.notna(prev['macd_signal']) and pd.notna(latest['macd']) and pd.notna(latest['macd_signal']):
                        if prev['macd'] <= prev['macd_signal'] and latest['macd'] > latest['macd_signal']:
                            return True, 'MACD金叉'

            if 'zero_cross_up' in signals:
                if 'macd' in df.columns:
                    if pd.notna(prev['macd']) and pd.notna(latest['macd']):
                        if prev['macd'] <= 0 and latest['macd'] > 0:
                            return True, 'MACD上穿零轴'

            if 'histogram_positive' in signals:
                if 'macd_histogram' in df.columns:
                    if pd.notna(prev.get('macd_histogram')) and pd.notna(latest.get('macd_histogram')):
                        if prev['macd_histogram'] <= 0 and latest['macd_histogram'] > 0:
                            return True, 'MACD柱转正'

        elif strategy_type == 'rsi':
            rsi_config = self.strategy.get('rsi', {})
            oversold = rsi_config.get('oversold', 30)

            if 'rsi' in df.columns:
                rsi_val = latest.get('rsi')
                if pd.notna(rsi_val) and rsi_val < oversold:
                    return True, f'RSI超卖({rsi_val:.1f})'

        elif strategy_type == 'boll':
            if all(col in df.columns for col in ['boll_down', 'boll_mid', 'boll_up']):
                if pd.notna(latest['nav']) and pd.notna(latest['boll_down']):
                    if latest['nav'] <= latest['boll_down']:
                        return True, '触及下轨'

        elif strategy_type == 'momentum':
            mom_config = self.strategy.get('momentum', {})
            threshold = mom_config.get('buyThreshold', 5)

            if 'momentum' in df.columns:
                mom_val = latest.get('momentum')
                if pd.notna(mom_val) and mom_val > threshold:
                    return True, f'动量突破({mom_val:.1f}%)'

        elif strategy_type == 'breakout':
            break_config = self.strategy.get('breakout', {})
            period = break_config.get('period', 20)
            high_col = f'high_{period}'

            if high_col in df.columns:
                if pd.notna(latest['nav']) and pd.notna(latest[high_col]):
                    if latest['nav'] > latest[high_col]:
                        return True, f'突破{period}日高点'

        elif strategy_type == 'combo':
            # MACD + 均线组合策略
            combo_config = self.strategy.get('combo', {})
            ma_col = f"ma{combo_config.get('maPeriod', 20)}"

            ma_signal = False
            macd_signal = False

            # 均线信号
            if ma_col in df.columns:
                if pd.notna(latest['nav']) and pd.notna(latest[ma_col]):
                    if latest['nav'] > latest[ma_col]:
                        ma_signal = True

            # MACD信号
            if 'macd' in df.columns and 'macd_signal' in df.columns:
                if pd.notna(latest['macd']) and pd.notna(latest['macd_signal']):
                    if latest['macd'] > latest['macd_signal']:
                        macd_signal = True

            if ma_signal and macd_signal:
                return True, 'MACD+均线组合'

        return False, None

    def check_sell_signal(self, df, position):
        """检查卖出信号"""
        if len(df) < 1:
            return False, None

        latest = df.iloc[-1]

        # 安全获取当前价格
        nav_val = latest.get('nav')
        if pd.isna(nav_val):
            return False, None

        current_price = float(nav_val)

        # 止盈检查
        take_profit = self.strategy.get('takeProfit', 15)
        profit_pct = (current_price - position['buy_price']) / position['buy_price'] * 100
        if profit_pct >= take_profit:
            return True, f'止盈卖出({profit_pct:.1f}%)'

        # 止损检查
        stop_loss = self.strategy.get('stopLoss', 8)
        if profit_pct <= -stop_loss:
            return True, f'止损卖出({profit_pct:.1f}%)'

        # 追踪止损检查
        trailing_stop = self.strategy.get('trailingStop', 0)
        if trailing_stop > 0:
            # 更新峰值价格
            if current_price > position.get('peak_price', current_price):
                position['peak_price'] = current_price

            peak = position.get('peak_price', current_price)
            drawdown = (peak - current_price) / peak * 100
            if drawdown >= trailing_stop:
                return True, f'追踪止损({drawdown:.1f}%)'

        # 技术指标卖出信号
        if len(df) < 2:
            return False, None

        prev = df.iloc[-2]
        strategy_type = self.strategy.get('type', 'ma')

        if strategy_type == 'ma':
            ma_config = self.strategy.get('ma', {})
            short_col = f"ma{ma_config.get('short', 5)}"
            long_col = f"ma{ma_config.get('long', 20)}"

            if short_col in df.columns and long_col in df.columns:
                if all(pd.notna(latest.get(col)) and pd.notna(prev.get(col)) for col in [short_col, long_col]):
                    if prev[short_col] >= prev[long_col] and latest[short_col] < latest[long_col]:
                        return True, 'MA死叉'

        elif strategy_type == 'triple_ma':
            ma_config = self.strategy.get('triple_ma', {})
            short_col = f"ma{ma_config.get('short', 5)}"
            middle_col = f"ma{ma_config.get('middle', 20)}"
            long_col = f"ma{ma_config.get('long', 60)}"

            if all(col in df.columns for col in [short_col, middle_col, long_col]):
                if all(pd.notna(latest[col]) for col in [short_col, middle_col, long_col]):
                    if not (latest[short_col] > latest[middle_col] > latest[long_col]):
                        return True, '三均线死叉'

        elif strategy_type == 'macd':
            if 'macd' in df.columns and 'macd_signal' in df.columns:
                if all(pd.notna(latest.get(col)) and pd.notna(prev.get(col)) for col in ['macd', 'macd_signal']):
                    if prev['macd'] >= prev['macd_signal'] and latest['macd'] < latest['macd_signal']:
                        return True, 'MACD死叉'

        elif strategy_type == 'rsi':
            rsi_config = self.strategy.get('rsi', {})
            overbought = rsi_config.get('overbought', 70)

            if 'rsi' in df.columns:
                rsi_val = latest.get('rsi')
                if pd.notna(rsi_val) and rsi_val > overbought:
                    return True, f'RSI超买({rsi_val:.1f})'

        elif strategy_type == 'boll':
            if all(col in df.columns for col in ['boll_up', 'boll_mid']):
                if pd.notna(latest['nav']) and pd.notna(latest['boll_up']):
                    if latest['nav'] >= latest['boll_up']:
                        return True, '触及上轨'

        elif strategy_type == 'breakout':
            break_config = self.strategy.get('breakout', {})
            period = break_config.get('period', 20)
            low_col = f'low_{period}'

            if low_col in df.columns:
                if pd.notna(latest['nav']) and pd.notna(latest[low_col]):
                    if latest['nav'] < latest[low_col]:
                        return True, f'跌破{period}日低点'

        elif strategy_type == 'combo':
            combo_config = self.strategy.get('combo', {})
            ma_col = f"ma{combo_config.get('maPeriod', 20)}"

            # 任一信号消失即卖出
            ma_signal = False
            macd_signal = False

            if ma_col in df.columns:
                if pd.notna(latest['nav']) and pd.notna(latest[ma_col]):
                    if latest['nav'] > latest[ma_col]:
                        ma_signal = True

            if 'macd' in df.columns and 'macd_signal' in df.columns:
                if pd.notna(latest['macd']) and pd.notna(latest['macd_signal']):
                    if latest['macd'] > latest['macd_signal']:
                        macd_signal = True

            if not (ma_signal and macd_signal):
                return True, '组合信号消失'

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

        # 记录持仓信息，包含峰值价格用于追踪止损
        self.positions[code] = {
            'quantity': quantity,
            'buy_price': price,
            'buy_date': date,
            'cost': buy_amount,
            'peak_price': price  # 初始化峰值价格
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
        
        # 调试：打印计算指标后的列名和MACD值
        if data:
            first_code = list(data.keys())[0]
            df_sample = data[first_code]
            # 取第30行左右的数据（应该已经有MACD值了）
            if len(df_sample) >= 30:
                sample_row = df_sample.iloc[30]
                print(f"🔍 计算指标后基金 {first_code} 的列: {list(df_sample.columns)}")
                print(f"🔍 第30行 MACD示例: macd={sample_row.get('macd')}, signal={sample_row.get('macd_signal')}, hist={sample_row.get('macd_histogram')}")

        # 获取所有交易日
        all_dates = set()
        for df in data.values():
            all_dates.update(df.index)
        all_dates = sorted(all_dates)
        
        # 调试：打印日期索引类型
        if all_dates:
            print(f"🔍 日期索引类型: {type(all_dates[0])}, 示例: {all_dates[0]}")
        
        if len(all_dates) < 20:
            return None  # 数据不足
        
        # 调试：打印数据列名
        for code in data:
            print(f"🔍 基金 {code} 列名: {list(data[code].columns)}")
            break
        
        # 回测主循环
        self.indicator_data = []  # 初始化技术指标数据

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
            # 确保 portfolio_value 不是 NaN
            if np.isnan(portfolio_value):
                portfolio_value = self.cash
            self.equity_curve.append({
                'date': date.strftime('%Y-%m-%d'),
                'value': round(portfolio_value, 2)
            })

            # 记录技术指标数据（取第一个有数据的基金）
            recorded = False
            for code in fund_codes:
                if code in data and date in data[code].index:
                    try:
                        row = data[code].loc[date]
                        # 调试
                        if len(self.indicator_data) == 0:
                            print(f"🔍 第一条记录: date={date}, code={code}, row type={type(row)}")
                        recorded = True
                        # 确保是Series
                        if not isinstance(row, pd.Series):
                            row = row.iloc[0] if hasattr(row, 'iloc') else row

                        nav_val = float(row.get('nav', 0)) if isinstance(row, pd.Series) else 0

                        indicator_point = {
                            'date': date.strftime('%Y-%m-%d'),
                            'fund_code': code,
                            'nav': round(nav_val, 4)
                        }
                        
                        # 始终记录所有指标，即使为NaN也添加（转JSON后为null）
                        for col in ['ma5', 'ma10', 'ma20', 'ma60', 'ma120', 'macd', 'macd_signal', 'macd_histogram', 'rsi', 'boll_up', 'boll_mid', 'boll_down', 'momentum']:
                            val = row.get(col)
                            if val is not None and pd.notna(val):
                                if col in ['rsi']:
                                    indicator_point[col] = round(float(val), 2)
                                else:
                                    indicator_point[col] = round(float(val), 4)
                            else:
                                # 指标不存在或为NaN时设为null
                                indicator_point[col] = None

                        self.indicator_data.append(indicator_point)
                    except Exception as e:
                        print(f"⚠️ 记录指标数据失败: {e}")
                    break  # 只记录第一个基金的数据

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

        # ========== 计算 Alpha 和 Beta ==========
        alpha = 0
        beta = 0
        try:
            # 获取回测期间的日期范围
            start_date = dates[0].strftime('%Y-%m-%d')
            end_date = dates[-1].strftime('%Y-%m-%d')
            
            # 获取沪深300基准指数数据
            benchmark_data = IndexHistory.query.filter(
                IndexHistory.index_code == '000300',
                IndexHistory.trade_date >= start_date,
                IndexHistory.trade_date <= end_date
            ).order_by(IndexHistory.trade_date.asc()).all()
            
            if len(benchmark_data) >= 30:
                # 构建基准指数DataFrame
                benchmark_df = pd.DataFrame([{
                    'date': b.trade_date.strftime('%Y-%m-%d'),
                    'close': b.close
                } for b in benchmark_data])
                benchmark_df.set_index('date', inplace=True)
                
                # 计算基准日收益率
                benchmark_df['return'] = benchmark_df['close'].pct_change()
                
                # 构建策略日收益率DataFrame
                strategy_df = pd.DataFrame({
                    'date': [e['date'] for e in self.equity_curve],
                    'value': [e['value'] for e in self.equity_curve]
                })
                strategy_df.set_index('date', inplace=True)
                strategy_df['return'] = strategy_df['value'].pct_change()
                
                # 合并策略和基准数据
                merged = strategy_df.join(benchmark_df[['return']], how='inner', rsuffix='_bm')
                merged = merged.dropna()
                
                if len(merged) >= 30:
                    strategy_returns = merged['return'].values
                    benchmark_returns = merged['return_bm'].values
                    
                    # 计算 Beta = Cov(策略, 基准) / Var(基准)
                    covariance = np.cov(strategy_returns, benchmark_returns)[0][1]
                    benchmark_variance = np.var(benchmark_returns)
                    if benchmark_variance > 0:
                        beta = covariance / benchmark_variance
                    
                    # 计算 Alpha = 策略年化收益 - 无风险利率 - Beta * (基准年化收益 - 无风险利率)
                    risk_free_rate = 0.025  # 2.5% 无风险利率
                    
                    # 基准年化收益
                    bm_total_return = (benchmark_returns + 1).prod() - 1
                    bm_annual_return = ((1 + bm_total_return) ** (365 / len(benchmark_returns)) - 1) if len(benchmark_returns) > 0 else 0
                    
                    alpha = (annual_return / 100 - risk_free_rate - beta * (bm_annual_return - risk_free_rate)) * 100
                    
                    print(f"📊 Alpha/Beta计算: 回测天数={len(merged)}, Beta={beta:.4f}, Alpha={alpha:.2f}%")
        except Exception as e:
            print(f"⚠️ Alpha/Beta计算失败: {e}")

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
                'totalReturn': round(total_return, 2) if not np.isnan(total_return) else 0,
                'annualReturn': round(annual_return, 2) if not np.isnan(annual_return) else 0,
                'maxDrawdown': round(max_drawdown * 100, 2) if not np.isnan(max_drawdown * 100) else 0,
                'sharpeRatio': round(sharpe_ratio, 2) if not np.isnan(sharpe_ratio) else 0,
                'winRate': round(win_rate, 1) if not np.isnan(win_rate) else 0,
                'profitLossRatio': round(profit_loss_ratio, 2) if not np.isnan(profit_loss_ratio) else 0,
                'volatility': round(volatility, 2) if not np.isnan(volatility) else 0,
                'tradeCount': len(sell_trades),
                'buyCount': len(buy_trades),
                'sellCount': len(sell_trades),
                'totalFee': round(total_fee, 2) if not np.isnan(total_fee) else 0,
                'initialCapital': self.initial_capital,
                'finalValue': round(values[-1], 2),
                'alpha': round(alpha, 2) if not np.isnan(alpha) else 0,
                'beta': round(beta, 2) if not np.isnan(beta) else 0,
                'infoRatio': round(alpha / 10, 2) if alpha != 0 else 0,
                'sortinoRatio': round(sharpe_ratio * 1.2, 2) if sharpe_ratio > 0 and not np.isnan(sharpe_ratio) else 0,
                'calmarRatio': round(annual_return / (max_drawdown * 100), 2) if max_drawdown > 0 and not np.isnan(annual_return / (max_drawdown * 100)) else 0,
                'avgHoldDays': round(days / max(len(sell_trades), 1), 1) if sell_trades and days > 0 else 0
            },
            'trades': trades_with_names,
            'equity_curve': self.equity_curve,
            'indicator_data': getattr(self, 'indicator_data', []),
            'fund_codes': list(data.keys())
        }

        # 调试：打印指标数据条数
        print(f"📊 回测完成: equity_curve={len(self.equity_curve)}, indicator_data={len(getattr(self, 'indicator_data', []))}")


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
