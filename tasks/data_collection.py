"""
股票因子数据采集服务
从akshare/baostock获取股票因子数据并存储到数据库
"""
import akshare as ak
import baostock as bs
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from app import app
from models import db
from models.stock_screening import StockScreeningData

class StockDataCollector:
    """股票数据采集器"""
    
    def __init__(self):
        self.bs = bs
        self.bs.login()
        self.today = datetime.now().strftime('%Y-%m-%d')
        
    def __del__(self):
        self.bs.logout()
    
    def get_stock_list(self):
        """获取A股股票列表"""
        try:
            # 使用baostock获取A股列表
            rs = self.bs.query_stock_basic()
            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                return pd.DataFrame()
            
            df = pd.DataFrame(data_list, columns=rs.fields)
            # 过滤A股: sh.6xxxxx (沪市主板), sz.0xxxxx (深市主板), sz.3xxxxx (创业板)
            df = df[df['code'].str.match(r'^(sh\.6|sz\.0|sz\.3)')]
            # 重命名列
            df = df[['code', 'code_name']].rename(columns={'code_name': 'name'})
            return df
        except Exception as e:
            print(f"获取股票列表失败: {e}")
            return pd.DataFrame()
    
    def get_realtime_data(self, symbol="sh.000001"):
        """获取实时行情数据"""
        try:
            df = ak.stock_zh_a_spot_em()
            return df
        except Exception as e:
            print(f"获取实时行情失败: {e}")
            return pd.DataFrame()
    
    def get_kline_data(self, stock_code, days=250):
        """获取K线数据"""
        try:
            # baostock需要格式: sh.600000
            # stock_code 应该是 sh.600000 格式
            code = stock_code  # 保持原格式
            
            # 使用baostock获取历史数据
            rs = self.bs.query_history_k_data_plus(
                code,
                "date,open,high,low,close,volume,amount,turn",
                start_date=(datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d'),
                end_date=self.today,
                frequency="d",
                adjustflag="2"  # 前复权
            )
            
            if rs.error_code != '0':
                print(f"获取K线失败 {stock_code}: {rs.error_msg}")
                return None
                
            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                return None
                
            df = pd.DataFrame(data_list, columns=rs.fields)
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            df['open'] = pd.to_numeric(df['open'], errors='coerce')
            df['high'] = pd.to_numeric(df['high'], errors='coerce')
            df['low'] = pd.to_numeric(df['low'], errors='coerce')
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
            df['turn'] = pd.to_numeric(df['turn'], errors='coerce')
            
            return df
        except Exception as e:
            print(f"获取K线数据失败 {stock_code}: {e}")
            return None
    
    def calculate_technical_factors(self, df):
        """计算技术因子"""
        if df is None or len(df) < 20:
            return {}
        
        closes = df['close'].values
        
        # 动量因子
        mom_1m = (closes[-1] - closes[-21]) / closes[-21] * 100 if len(closes) >= 21 and closes[-21] != 0 else 0
        mom_3m = (closes[-1] - closes[-63]) / closes[-63] * 100 if len(closes) >= 63 and closes[-63] != 0 else 0
        mom_6m = (closes[-1] - closes[-126]) / closes[-126] * 100 if len(closes) >= 126 and closes[-126] != 0 else 0
        
        # 52周新高
        high_52w = max(closes[-252:]) if len(closes) >= 252 else max(closes)
        high_52w_ratio = closes[-1] / high_52w * 100 if high_52w > 0 else 0
        
        # 动量加速度
        mom_accel = mom_1m - mom_3m / 3 if mom_3m != 0 else 0
        
        # 波动因子
        returns = np.diff(closes) / closes[:-1]
        returns = returns[~np.isnan(returns)]
        volatility = np.std(returns) * np.sqrt(252) * 100 if len(returns) > 0 else 0
        
        # ATR
        if len(df) >= 14:
            high = df['high'].values.astype(float)
            low = df['low'].values.astype(float)
            close = df['close'].values.astype(float)
            tr = np.maximum(
                high[1:] - low[1:],
                np.abs(high[1:] - close[:-1]),
                np.abs(low[1:] - close[:-1])
            )
            atr = np.mean(tr[-14:]) if len(tr) >= 14 else 0
        else:
            atr = 0
        
        # 最大回撤
        peak = closes[0]
        max_dd = 0
        for price in closes:
            if price > peak:
                peak = price
            dd = (peak - price) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        
        # 下行波动率
        downside_returns = [r for r in returns if r < 0]
        downside_vol = np.std(downside_returns) * np.sqrt(252) * 100 if len(downside_returns) > 1 else 0
        
        # 技术指标
        # RSI
        if len(closes) >= 15:
            deltas = np.diff(closes)
            gains = [d for d in deltas if d > 0]
            losses = [-d for d in deltas if d < 0]
            avg_gain = np.mean(gains) if gains else 0
            avg_loss = np.mean(losses) if losses else 0.001
            rs_val = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs_val))
        else:
            rsi = 50
        
        # MACD
        if len(closes) >= 26:
            ema12 = self._ema(closes, 12)
            ema26 = self._ema(closes, 26)
            dif = ema12 - ema26
            macd = dif * 0.2  # 简化MACD柱
        else:
            dif = macd = 0
        
        # 均线多头
        ma5 = np.mean(closes[-5:]) if len(closes) >= 5 else closes[-1]
        ma10 = np.mean(closes[-10:]) if len(closes) >= 10 else closes[-1]
        ma20 = np.mean(closes[-20:]) if len(closes) >= 20 else closes[-1]
        ma_bull = 1 if ma5 > ma10 > ma20 else 0
        
        return {
            'mom_1m': round(mom_1m, 2),
            'mom_3m': round(mom_3m, 2),
            'mom_6m': round(mom_6m, 2),
            'high_52w_ratio': round(high_52w_ratio, 2),
            'mom_accel': round(mom_accel, 2),
            'volatility': round(volatility, 2),
            'atr': round(atr, 4),
            'max_drawdown': round(max_dd, 2),
            'downside_vol': round(downside_vol, 2),
            'rsi': round(rsi, 2),
            'macd': round(macd, 4),
            'ma_bull': ma_bull
        }
    
    def _ema(self, data, period):
        """计算EMA"""
        ema = data[0]
        multiplier = 2 / (period + 1)
        for price in data[1:]:
            ema = (price - ema) * multiplier + ema
        return ema
    
    def format_stock_code(self, code):
        """标准化股票代码格式"""
        # sh.600000 -> sh.600000, sh.6 -> sh.600000
        code = code.strip()
        if '.' in code:
            parts = code.split('.')
            if len(parts[1]) < 6:
                parts[1] = parts[1].zfill(6)
            return '.'.join(parts)
        else:
            return code.zfill(6)
    
    def collect_stock_data(self, stock_code, stock_name):
        """采集单只股票数据"""
        # 标准化代码格式
        stock_code = self.format_stock_code(stock_code)
        
        # 获取K线数据
        df = self.get_kline_data(stock_code)
        
        if df is None or len(df) < 5:
            return None
        
        latest = df.iloc[-1]
        
        # 计算技术因子
        tech_factors = self.calculate_technical_factors(df)
        
        # 计算涨跌幅
        change_5d = (df['close'].iloc[-1] - df['close'].iloc[-6]) / df['close'].iloc[-6] * 100 if len(df) >= 6 else 0
        change_10d = (df['close'].iloc[-1] - df['close'].iloc[-11]) / df['close'].iloc[-11] * 100 if len(df) >= 11 else 0
        change_20d = (df['close'].iloc[-1] - df['close'].iloc[-21]) / df['close'].iloc[-21] * 100 if len(df) >= 21 else 0
        change_60d = (df['close'].iloc[-1] - df['close'].iloc[-61]) / df['close'].iloc[-61] * 100 if len(df) >= 61 else 0
        
        # 换手率
        if len(df) >= 20:
            turnover_20d = df['turn'].tail(20).mean()
        else:
            turnover_20d = float(latest.get('turn', 0) or 0)
        
        # 换手率变化
        if len(df) >= 2:
            turnover_change = (float(latest.get('turn', 0) or 0) - df['turn'].iloc[-2]) / df['turn'].iloc[-2] * 100 if df['turn'].iloc[-2] > 0 else 0
        else:
            turnover_change = 0
        
        # 组合数据
        data = {
            'stock_code': stock_code.replace('sh.', '').replace('sz.', ''),
            'stock_name': stock_name,
            'latest_price': float(latest['close']) if latest['close'] else None,
            'open_price': float(latest['open']) if latest['open'] else None,
            'high': float(latest['high']) if latest['high'] else None,
            'low': float(latest['low']) if latest['low'] else None,
            'pre_close': float(df['close'].iloc[-2]) if len(df) >= 2 and df['close'].iloc[-2] else None,
            'change_percent': round((float(latest['close'] or 0) - float(df['close'].iloc[-2] if len(df) >= 2 else latest['close'])) / float(df['close'].iloc[-2] if len(df) >= 2 else 1) * 100, 2) if len(df) >= 2 else 0,
            'volume': float(latest['volume']) if latest['volume'] else 0,
            'turnover': float(latest['amount']) if latest['amount'] else 0,
            'turnover_rate': float(latest['turn']) if latest['turn'] else 0,
            'change_5d': round(change_5d, 2),
            'change_10d': round(change_10d, 2),
            'change_20d': round(change_20d, 2),
            'change_60d': round(change_60d, 2),
            'turnover_change': round(turnover_change, 2),
            'trade_date': datetime.strptime(self.today, '%Y-%m-%d').date()
        }
        
        # 添加技术因子
        data.update(tech_factors)
        
        return data
    
    def batch_collect(self, limit=100):
        """批量采集股票数据"""
        print(f"开始采集股票数据... 目标: {limit}只")
        
        # 获取股票列表
        stocks = self.get_stock_list()
        if stocks.empty:
            print("获取股票列表失败")
            return 0
        
        # 取前limit只
        stocks = stocks.head(limit)
        
        success_count = 0
        error_count = 0
        
        for idx, row in stocks.iterrows():
            stock_code = row['code']
            stock_name = row['name']
            
            try:
                data = self.collect_stock_data(stock_code, stock_name)
                
                if data:
                    # 检查是否已存在
                    existing = StockScreeningData.query.filter_by(
                        stock_code=data['stock_code'],
                        trade_date=data['trade_date']
                    ).first()
                    
                    if existing:
                        for key, value in data.items():
                            setattr(existing, key, value)
                    else:
                        record = StockScreeningData(**data)
                        db.session.add(record)
                    
                    success_count += 1
                    
                    if success_count % 100 == 0:
                        db.session.commit()
                        print(f"已采集 {success_count}/{limit} 只股票")
                        
            except Exception as e:
                error_count += 1
                if error_count <= 3:
                    print(f"失败 {stock_code}: {str(e)[:40]}")
        
        # 最后提交
        db.session.commit()
        print(f"采集完成! 成功 {success_count}/{limit} 只股票")
        return success_count


def run_data_collection():
    """定时任务入口"""
    print(f"[{datetime.now()}] 开始执行数据采集任务...")
    with app.app_context():
        collector = StockDataCollector()
        count = collector.batch_collect(limit=5000)  # 采集全量A股
    print(f"[{datetime.now()}] 数据采集任务完成! 共采集 {count} 只股票")
    return count


if __name__ == '__main__':
    run_data_collection()
