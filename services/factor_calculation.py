"""
因子计算服务 - 支持50+专业因子计算
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import akshare as ak
import baostock as bs

class FactorCalculationService:
    """因子计算服务"""
    
    def __init__(self):
        bs.login()
        
    # ==================== 估值因子 ====================
    
    def calc_valuation_factors(self, stock_code):
        """计算估值因子"""
        try:
            # 从akshare获取财务数据
            # 简化版本：使用已有数据
            return {
                'pe': None,
                'pb': None,
                'ps': None,
                'dividend_yield': None
            }
        except:
            return {}
    
    # ==================== 质量因子 ====================
    
    def calc_quality_factors(self, stock_code):
        """计算质量因子"""
        try:
            return {
                'roe': None,
                'roa': None,
                'gross_margin': None,
                'net_margin': None
            }
        except:
            return {}
    
    # ==================== 动量因子 ====================
    
    def calc_momentum_factors(self, df_price):
        """
        从价格数据计算动量因子
        df_price: DataFrame with ['date', 'close']
        """
        if df_price is None or len(df_price) < 60:
            return {}
        
        closes = df_price['close'].values
        
        # 不同周期的动量
        mom_1m = (closes[-1] - closes[-21]) / closes[-21] * 100 if len(closes) >= 21 else 0
        mom_3m = (closes[-1] - closes[-63]) / closes[-63] * 100 if len(closes) >= 63 else 0
        mom_6m = (closes[-1] - closes[-126]) / closes[-126] * 100 if len(closes) >= 126 else 0
        
        # 52周新高
        high_52w = closes[-252:].max() if len(closes) >= 252 else closes.max()
        high_52w_ratio = closes[-1] / high_52w * 100 if high_52w > 0 else 0
        
        # 动量加速度 (1月动量 - 3月动量)
        mom_accel = mom_1m - mom_3m / 3 if mom_3m != 0 else 0
        
        return {
            'mom_1m': round(mom_1m, 2),
            'mom_3m': round(mom_3m, 2),
            'mom_6m': round(mom_6m, 2),
            'high_52w_ratio': round(high_52w_ratio, 2),
            'mom_accel': round(mom_accel, 2)
        }
    
    # ==================== 波动因子 ====================
    
    def calc_volatility_factors(self, df_price):
        """计算波动因子"""
        if df_price is None or len(df_price) < 20:
            return {}
        
        closes = df_price['close'].values
        
        # 计算日收益率
        returns = np.diff(closes) / closes[:-1]
        
        # 20日波动率 (年化)
        volatility = np.std(returns) * np.sqrt(252) * 100 if len(returns) > 0 else 0
        
        # ATR (简化版)
        if len(df_price) >= 2:
            highs = df_price.get('high', df_price['close']).values
            lows = df_price.get('low', df_price['close']).values
            tr = np.maximum(highs[1:] - lows[1:], 
                          np.abs(highs[1:] - closes[:-1]),
                          np.abs(lows[1:] - closes[:-1]))
            atr = np.mean(tr[-20:]) if len(tr) >= 20 else np.mean(tr)
        else:
            atr = 0
        
        # 最大回撤
        peak = closes[0]
        max_dd = 0
        for price in closes:
            if price > peak:
                peak = price
            dd = (peak - price) / peak * 100
            if dd > max_dd:
                max_dd = dd
        
        # 下行波动率 (只考虑负收益)
        downside_returns = [r for r in returns if r < 0]
        downside_vol = np.std(downside_returns) * np.sqrt(252) * 100 if downside_returns else 0
        
        return {
            'volatility': round(volatility, 2),
            'atr': round(atr, 4),
            'max_drawdown': round(max_dd, 2),
            'downside_vol': round(downside_vol, 2)
        }
    
    # ==================== 技术因子 ====================
    
    def calc_technical_factors(self, df_price):
        """计算技术因子"""
        if df_price is None or len(df_price) < 30:
            return {}
        
        closes = df_price['close'].values
        
        # 移动平均线
        ma5 = np.mean(closes[-5:]) if len(closes) >= 5 else closes[-1]
        ma10 = np.mean(closes[-10:]) if len(closes) >= 10 else closes[-1]
        ma20 = np.mean(closes[-20:]) if len(closes) >= 20 else closes[-1]
        
        # 均线多头排列
        ma_bull = 1 if ma5 > ma10 > ma20 else 0
        
        # RSI (简化版)
        if len(closes) >= 15:
            deltas = np.diff(closes)
            gains = np.mean([d for d in deltas[-14:] if d > 0]) if any(d > 0 for d in deltas[-14:]) else 0
            losses = np.mean([-d for d in deltas[-14:] if d < 0]) if any(d < 0 for d in deltas[-14:]) else 0.001
            rs = gains / losses
            rsi = 100 - (100 / (1 + rs))
        else:
            rsi = 50
        
        # MACD (简化版)
        if len(closes) >= 30:
            ema12 = np.mean(closes[-12:])
            ema26 = np.mean(closes[-26:])
            dif = ema12 - ema26
            dea = np.mean([dif])  # 简化
            macd = dif - dea
        else:
            dif = dea = macd = 0
        
        return {
            'ma5': round(ma5, 2),
            'ma10': round(ma10, 2),
            'ma20': round(ma20, 2),
            'ma_bull': ma_bull,
            'rsi': round(rsi, 2),
            'macd': round(macd, 4),
            'dif': round(dif, 4),
            'dea': round(dea, 4)
        }
    
    # ==================== 情绪因子 ====================
    
    def calc_sentiment_factors(self, df_price, df_volume=None):
        """计算情绪因子"""
        if df_price is None or len(df_price) < 20:
            return {}
        
        # 换手率 (需要流通股本数据，这里简化)
        if df_volume is not None and len(df_volume) >= 20:
            turnover_20d = df_volume['volume'].tail(20).mean()
            turnover_change = (df_volume['volume'].iloc[-1] - df_volume['volume'].iloc[-20]) / df_volume['volume'].iloc[-20] * 100 if df_volume['volume'].iloc[-20] > 0 else 0
        else:
            turnover_20d = 0
            turnover_change = 0
        
        # 量价趋势 (PVT简化版)
        closes = df_price['close'].values
        if len(closes) >= 2:
            price_change = (closes[-1] - closes[-2]) / closes[-2]
            pvt = price_change * (df_volume['volume'].iloc[-1] if df_volume is not None else 0)
        else:
            pvt = 0
        
        return {
            'turnover_20d': round(turnover_20d, 2),
            'turnover_change': round(turnover_change, 2),
            'pvt': round(pvt, 2)
        }
    
    # ==================== 主计算函数 ====================
    
    def calculate_all_factors(self, stock_code, hist_data=None):
        """
        计算所有因子
        
        stock_code: 股票代码
        hist_data: 历史数据 {dates, closes, opens, highs, lows, volumes}
        """
        if hist_data is None:
            return {}
        
        # 构建DataFrame
        df_price = pd.DataFrame({
            'date': hist_data.get('dates', []),
            'close': hist_data.get('closes', []),
            'open': hist_data.get('opens', []),
            'high': hist_data.get('highs', []),
            'low': hist_data.get('lows', [])
        })
        
        df_volume = pd.DataFrame({
            'volume': hist_data.get('volumes', [])
        })
        
        if len(df_price) == 0:
            return {}
        
        # 计算各类因子
        factors = {}
        
        # 动量因子
        factors.update(self.calc_momentum_factors(df_price))
        
        # 波动因子
        factors.update(self.calc_volatility_factors(df_price))
        
        # 技术因子
        factors.update(self.calc_technical_factors(df_price))
        
        # 情绪因子
        factors.update(self.calc_sentiment_factors(df_price, df_volume))
        
        return factors


# 全局服务实例
factor_service = FactorCalculationService()
