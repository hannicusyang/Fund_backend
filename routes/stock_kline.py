# routes/stock_kline.py
from flask import Blueprint, jsonify, request
import akshare as ak
import baostock as bs
import pandas as pd
from datetime import datetime, timedelta

stock_kline_bp = Blueprint('stock_kline', __name__)


def get_stock_code_format(code):
    """将股票代码转换为 akshare 需要的格式"""
    code = str(code).strip()
    if code.startswith('6'):
        return f"sh{code}"
    elif code.startswith(('0', '3')):
        return f"sz{code}"
    return code


def get_stock_name(code):
    """从baostock获取股票名称"""
    try:
        if code.startswith('6'):
            bs_code = f"sh.{code}"
        elif code.startswith(('0', '3')):
            bs_code = f"sz.{code}"
        else:
            return None
        
        lg = bs.login()
        if lg.error_code != '0':
            return None
        
        rs = bs.query_stock_basic(bs_code)
        name = None
        while (rs.error_code == '0') & rs.next():
            name = rs.get_row_data()[1]
            break
        
        bs.logout()
        return name
    except:
        return None


def get_kline_baostock(code, start_date, end_date):
    """从baostock获取K线数据"""
    try:
        # 转换代码格式
        if code.startswith('6'):
            bs_code = f"sh.{code}"
        elif code.startswith(('0', '3')):
            bs_code = f"sz.{code}"
        else:
            return None
        
        # 清理日期格式 (YYYYMMDD -> YYYY-MM-DD)
        def clean_date(d):
            d = str(d).replace('/', '').replace('-', '')
            if len(d) == 8:
                return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
            return d
        
        start = clean_date(start_date)
        end = clean_date(end_date)
        
        lg = bs.login()
        if lg.error_code != '0':
            return None
        
        rs = bs.query_history_k_data_plus(
            bs_code,
            'date,open,high,low,close,volume,amount,pctChg',
            start_date=start,
            end_date=end,
            frequency='d'
        )
        
        if rs is None:
            bs.logout()
            return None
        
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        
        bs.logout()
        
        if not data_list:
            return None
        
        df = pd.DataFrame(data_list, columns=rs.fields)
        df = df[df['close'].notna() & (df['close'] != '')]
        
        data = []
        for _, row in df.iterrows():
            try:
                data.append({
                    'date': row['date'],
                    'open': float(row['open']) if row['open'] else 0,
                    'close': float(row['close']) if row['close'] else 0,
                    'high': float(row['high']) if row['high'] else 0,
                    'low': float(row['low']) if row['low'] else 0,
                    'volume': float(row['volume']) if row['volume'] else 0,
                    'amount': float(row['amount']) if row['amount'] else 0,
                    'change_percent': float(row['pctChg']) if row.get('pctChg') else 0,
                    'turnover': 0
                })
            except:
                continue
        
        return data if data else None
    except:
        return None


@stock_kline_bp.route('/kline/<stock_code>', methods=['GET'])
def get_kline(stock_code):
    """获取股票K线数据"""
    period = request.args.get('period', 'daily')  # daily, weekly, monthly
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    try:
        # 转换代码格式
        symbol = get_stock_code_format(stock_code)
        
        # 如果没有指定日期，默认获取一年数据
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        
        # 获取K线数据
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"  # 前复权
        )
        
        if df.empty:
            return jsonify({
                "success": False,
                "data": [],
                "message": "暂无数据"
            })
        
        # 转换数据格式
        data = []
        for _, row in df.iterrows():
            # 日期格式转换
            date_str = row['日期']
            if isinstance(date_str, str):
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    date_str = date_obj.strftime('%Y-%m-%d')
                except:
                    pass
            
            data.append({
                'date': date_str,
                'open': float(row['开盘']) if row['开盘'] else 0,
                'close': float(row['收盘']) if row['收盘'] else 0,
                'high': float(row['最高']) if row['最高'] else 0,
                'low': float(row['最低']) if row['最低'] else 0,
                'volume': float(row['成交量']) if row['成交量'] else 0,
                'amount': float(row['成交额']) if row['成交额'] else 0,
                'amplitude': float(row['振幅']) if row['振幅'] else 0,
                'change_percent': float(row['涨跌幅']) if row['涨跌幅'] else 0,
                'change_amount': float(row['涨跌额']) if row['涨跌额'] else 0,
                'turnover': float(row['换手率']) if row['换手率'] else 0
            })
        
        # 返回最新在前
        # data.reverse()  # Oldest to newest
        
        return jsonify({
            "success": True,
            "data": data,
            "message": "获取成功",
            "total": len(data)
        })
        
    except Exception as e:
        # akshare失败，使用baostock备选
        data = get_kline_baostock(stock_code, start_date, end_date or datetime.now().strftime('%Y-%m-%d'))
        if data:
            # data.reverse()  # Oldest to newest
            return jsonify({
                "success": True,
                "data": data,
                "message": "获取成功 (baostock)",
                "total": len(data)
            })
        return jsonify({
            "success": False,
            "data": [],
            "message": f"获取失败: {str(e)}"
        }), 500



@stock_kline_bp.route('/kline/indicators/<stock_code>', methods=['GET'])
def get_kline_with_indicators(stock_code):
    """获取带技术指标的K线数据"""
    period = request.args.get('period', 'daily')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    try:
        symbol = get_stock_code_format(stock_code)
        
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=730)).strftime('%Y%m%d')
        
        # 获取原始K线数据
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"
        )
        
        if df.empty:
            return jsonify({
                "success": False,
                "data": [],
                "message": "暂无数据"
            })
        
        # 计算技术指标
        closes = df['收盘'].astype(float).values
        highs = df['最高'].astype(float).values
        lows = df['最低'].astype(float).values
        volumes = df['成交量'].astype(float).values
        
        # 计算MA
        df['MA5'] = df['收盘'].rolling(window=5).mean()
        df['MA10'] = df['收盘'].rolling(window=10).mean()
        df['MA20'] = df['收盘'].rolling(window=20).mean()
        df['MA60'] = df['收盘'].rolling(window=60).mean()
        
        # 计算MACD
        exp1 = df['收盘'].ewm(span=12, adjust=False).mean()
        exp2 = df['收盘'].ewm(span=26, adjust=False).mean()
        df['DIF'] = exp1 - exp2
        df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
        df['MACD'] = 2 * (df['DIF'] - df['DEA'])
        
        # 计算RSI
        delta = df['收盘'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # 计算KDJ
        low_n = df['最低'].rolling(window=9).min()
        high_n = df['最高'].rolling(window=9).max()
        rsv = (df['收盘'] - low_n) / (high_n - low_n) * 100
        df['K'] = rsv.ewm(com=2, adjust=False).mean()
        df['D'] = df['K'].ewm(com=2, adjust=False).mean()
        df['J'] = 3 * df['K'] - 2 * df['D']
        
        # 计算布林带
        df['BOLL_MID'] = df['收盘'].rolling(window=20).mean()
        std = df['收盘'].rolling(window=20).std()
        df['BOLL_UPPER'] = df['BOLL_MID'] + 2 * std
        df['BOLL_LOWER'] = df['BOLL_MID'] - 2 * std
        
        # 计算CCI
        typical_price = (df['最高'] + df['最低'] + df['收盘']) / 3
        sma = typical_price.rolling(window=20).mean()
        mean_deviation = typical_price.rolling(window=20).apply(lambda x: abs(x - x.mean()).mean())
        df['CCI'] = (typical_price - sma) / (0.015 * mean_deviation)
        
        # 计算威廉指标
        df['WR'] = (high_n - df['收盘']) / (high_n - low_n) * 100
        
        # 计算DMI指标 (修复)
        try:
            high = df['最高'].astype(float)
            low = df['最低'].astype(float)
            close = df['收盘'].astype(float)
            
            # 真实波幅TR
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            tr = tr.fillna(0)
            tr[tr == 0] = 0.0001  # 避免除零
            
            # DM计算
            up_move = high - high.shift(1)
            down_move = low.shift(1) - low
            
            plus_dm = pd.Series(0, index=high.index)
            minus_dm = pd.Series(0, index=high.index)
            
            plus_dm = plus_dm.where(~((up_move > down_move) & (up_move > 0)), up_move)
            minus_dm = minus_dm.where(~((down_move > up_move) & (down_move > 0)), down_move)
            plus_dm = plus_dm.fillna(0)
            minus_dm = minus_dm.fillna(0)
            
            # 计算DI
            plus_di = plus_dm.rolling(window=14, min_periods=1).sum() / tr.rolling(window=14, min_periods=1).sum() * 100
            minus_di = minus_dm.rolling(window=14, min_periods=1).sum() / tr.rolling(window=14, min_periods=1).sum() * 100
            
            # 计算ADX
            dx = abs(plus_di - minus_di) / (plus_di + minus_di + 0.0001) * 100
            adx = dx.rolling(window=14, min_periods=1).mean()
            
            df['PLUS_DI'] = plus_di
            df['MINUS_DI'] = minus_di
            df['ADX'] = adx
        except Exception as e:
            print(f"DMI计算错误: {e}")
            df['PLUS_DI'] = None
            df['MINUS_DI'] = None
            df['ADX'] = None
        
        # 计算OBV能量潮 (修复)
        try:
            close_diff = df['收盘'].astype(float).diff()
            volume = df['成交量'].astype(float)
            obv = pd.Series(0, index=df.index)
            obv = obv.where(close_diff <= 0, volume)
            obv = obv.where(close_diff >= 0, -volume)
            df['OBV'] = obv.cumsum()
        except Exception as e:
            print(f"OBV计算错误: {e}")
            df['OBV'] = None
        
        # 计算SAR抛物线指标
        df['SAR'] = df['收盘'].copy()
        df['SAR'] = df['SAR'].rolling(window=2).min()
        
        # 计算DMA平行线差
        df['DMA'] = df['收盘'].rolling(window=10).mean() - df['收盘'].rolling(window=50).mean()
        df['AMA'] = df['DMA'].rolling(window=10).mean()
        
        # 转换数据格式
        data = []
        for _, row in df.iterrows():
            date_str = row['日期']
            if isinstance(date_str, str):
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    date_str = date_obj.strftime('%Y-%m-%d')
                except:
                    pass
            
            data.append({
                'date': date_str,
                'open': float(row['开盘']) if row['开盘'] else 0,
                'close': float(row['收盘']) if row['收盘'] else 0,
                'high': float(row['最高']) if row['最高'] else 0,
                'low': float(row['最低']) if row['最低'] else 0,
                'volume': float(row['成交量']) if row['成交量'] else 0,
                'amount': float(row['成交额']) if row['成交额'] else 0,
                'change_percent': float(row['涨跌幅']) if row['涨跌幅'] else 0,
                'turnover': float(row['换手率']) if row['换手率'] else 0,
                'ma5': float(row['MA5']) if pd.notna(row['MA5']) else None,
                'ma10': float(row['MA10']) if pd.notna(row['MA10']) else None,
                'ma20': float(row['MA20']) if pd.notna(row['MA20']) else None,
                'ma60': float(row['MA60']) if pd.notna(row['MA60']) else None,
                'macd': {
                    'dif': float(row['DIF']) if pd.notna(row['DIF']) else None,
                    'dea': float(row['DEA']) if pd.notna(row['DEA']) else None,
                    'bar': float(row['MACD']) if pd.notna(row['MACD']) else None
                },
                'rsi': float(row['RSI']) if pd.notna(row['RSI']) else None,
                'kdj': {
                    'k': float(row['K']) if pd.notna(row['K']) else None,
                    'd': float(row['D']) if pd.notna(row['D']) else None,
                    'j': float(row['J']) if pd.notna(row['J']) else None
                },
                'boll': {
                    'upper': float(row['BOLL_UPPER']) if pd.notna(row['BOLL_UPPER']) else None,
                    'middle': float(row['BOLL_MID']) if pd.notna(row['BOLL_MID']) else None,
                    'lower': float(row['BOLL_LOWER']) if pd.notna(row['BOLL_LOWER']) else None
                },
                'cci': float(row['CCI']) if pd.notna(row['CCI']) else None,
                'wr': float(row['WR']) if pd.notna(row['WR']) else None,
                'dmi': {
                    'plus_di': float(row['PLUS_DI']) if pd.notna(row.get('PLUS_DI')) else None,
                    'minus_di': float(row['MINUS_DI']) if pd.notna(row.get('MINUS_DI')) else None,
                    'adx': float(row['ADX']) if pd.notna(row.get('ADX')) else None
                },
                'obv': float(row['OBV']) if pd.notna(row.get('OBV')) else None,
                'dma': float(row['DMA']) if pd.notna(row.get('DMA')) else None,
                'ama': float(row['AMA']) if pd.notna(row.get('AMA')) else None
            })
        
        # data.reverse()  # Oldest to newest
        
        # 获取股票名称
        stock_name = get_stock_name(stock_code)
        
        return jsonify({
            "success": True,
            "data": data,
            "stock_name": stock_name,
            "message": "获取成功",
            "total": len(data)
        })
        
    except Exception as e:
        # akshare失败，使用baostock备选
        data = get_kline_baostock(stock_code, start_date, end_date or datetime.now().strftime('%Y-%m-%d'))
        if data:
            # 计算技术指标
            try:
                df = pd.DataFrame(data)
                closes = pd.to_numeric(df['close'], errors='coerce')
                
                # 计算MA
                df['MA5'] = closes.rolling(window=5).mean()
                df['MA10'] = closes.rolling(window=10).mean()
                df['MA20'] = closes.rolling(window=20).mean()
                
                # 计算MACD
                exp1 = closes.ewm(span=12, adjust=False).mean()
                exp2 = closes.ewm(span=26, adjust=False).mean()
                df['DIF'] = exp1 - exp2
                df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
                df['MACD'] = 2 * (df['DIF'] - df['DEA'])
                
                # 计算RSI
                delta = closes.diff()
                gain = delta.where(delta > 0, 0).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                df['RSI'] = 100 - (100 / (1 + rs))
                
                # 计算KDJ
                lows = pd.to_numeric(df['low'], errors='coerce')
                highs = pd.to_numeric(df['high'], errors='coerce')
                low_n = lows.rolling(window=9).min()
                high_n = highs.rolling(window=9).max()
                rsv = (closes - low_n) / (high_n - low_n) * 100
                df['K'] = rsv.ewm(com=2, adjust=False).mean()
                df['D'] = df['K'].ewm(com=2, adjust=False).mean()
                df['J'] = 3 * df['K'] - 2 * df['D']
                
                # 计算布林带
                df['BOLL_MID'] = closes.rolling(window=20).mean()
                std = closes.rolling(window=20).std()
                df['BOLL_UPPER'] = df['BOLL_MID'] + 2 * std
                df['BOLL_LOWER'] = df['BOLL_MID'] - 2 * std
                
                # 计算DMI指标 (修复)
                try:
                    high = df['high'].astype(float)
                    low = df['low'].astype(float)
                    close = df['close'].astype(float)
                    
                    # 真实波幅TR
                    tr1 = high - low
                    tr2 = abs(high - close.shift(1))
                    tr3 = abs(low - close.shift(1))
                    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                    tr = tr.fillna(0)
                    tr[tr == 0] = 0.0001
                    
                    # DM计算
                    up_move = high - high.shift(1)
                    down_move = low.shift(1) - low
                    
                    plus_dm = pd.Series(0, index=high.index)
                    minus_dm = pd.Series(0, index=high.index)
                    
                    plus_dm = plus_dm.where(~((up_move > down_move) & (up_move > 0)), up_move)
                    minus_dm = minus_dm.where(~((down_move > up_move) & (down_move > 0)), down_move)
                    plus_dm = plus_dm.fillna(0)
                    minus_dm = minus_dm.fillna(0)
                    
                    # 计算DI
                    plus_di = plus_dm.rolling(window=14, min_periods=1).sum() / tr.rolling(window=14, min_periods=1).sum() * 100
                    minus_di = minus_dm.rolling(window=14, min_periods=1).sum() / tr.rolling(window=14, min_periods=1).sum() * 100
                    
                    # 计算ADX
                    dx = abs(plus_di - minus_di) / (plus_di + minus_di + 0.0001) * 100
                    adx = dx.rolling(window=14, min_periods=1).mean()
                    
                    df['PLUS_DI'] = plus_di
                    df['MINUS_DI'] = minus_di
                    df['ADX'] = adx
                except Exception as e:
                    df['PLUS_DI'] = None
                    df['MINUS_DI'] = None
                    df['ADX'] = None
                
                # 计算OBV能量潮 (修复)
                try:
                    close_diff = df['close'].astype(float).diff()
                    volume = df['volume'].astype(float)
                    obv = pd.Series(0, index=df.index)
                    obv = obv.where(close_diff <= 0, volume)
                    obv = obv.where(close_diff >= 0, -volume)
                    df['OBV'] = obv.cumsum()
                except:
                    df['OBV'] = None
                
                # 转换格式
                result = []
                for _, row in df.iterrows():
                    result.append({
                        'date': row['date'],
                        'open': row['open'],
                        'close': row['close'],
                        'high': row['high'],
                        'low': row['low'],
                        'volume': row['volume'],
                        'amount': row['amount'],
                        'change_percent': row['change_percent'],
                        'turnover': 0,
                        'ma5': float(row['MA5']) if pd.notna(row['MA5']) else None,
                        'ma10': float(row['MA10']) if pd.notna(row['MA10']) else None,
                        'ma20': float(row['MA20']) if pd.notna(row['MA20']) else None,
                        'ma60': None,
                        'macd': {
                            'dif': float(row['DIF']) if pd.notna(row['DIF']) else None,
                            'dea': float(row['DEA']) if pd.notna(row['DEA']) else None,
                            'bar': float(row['MACD']) if pd.notna(row['MACD']) else None
                        },
                        'rsi': float(row['RSI']) if pd.notna(row['RSI']) else None,
                        'kdj': {
                            'k': float(row['K']) if pd.notna(row['K']) else None,
                            'd': float(row['D']) if pd.notna(row['D']) else None,
                            'j': float(row['J']) if pd.notna(row['J']) else None
                        },
                        'boll': {
                            'upper': float(row['BOLL_UPPER']) if pd.notna(row['BOLL_UPPER']) else None,
                            'middle': float(row['BOLL_MID']) if pd.notna(row['BOLL_MID']) else None,
                            'lower': float(row['BOLL_LOWER']) if pd.notna(row['BOLL_LOWER']) else None
                        },
                        'cci': None,
                        'wr': None,
                        'dmi': {
                            'plus_di': float(row['PLUS_DI']) if pd.notna(row.get('PLUS_DI')) else None,
                            'minus_di': float(row['MINUS_DI']) if pd.notna(row.get('MINUS_DI')) else None,
                            'adx': float(row['ADX']) if pd.notna(row.get('ADX')) else None
                        },
                        'obv': float(row['OBV']) if pd.notna(row.get('OBV')) else None,
                        'dma': None,
                        'ama': None
                    })
                
                # result.reverse()  # Oldest to newest
                stock_name = get_stock_name(stock_code)
                return jsonify({
                    "success": True,
                    "data": result,
                    "stock_name": stock_name,
                    "message": "获取成功 (baostock)",
                    "total": len(result)
                })
            except Exception as calc_err:
                print(f"技术指标计算错误: {calc_err}")
        
        return jsonify({
            "success": False,
            "data": [],
            "message": f"获取失败: {str(e)}"
        }), 500
