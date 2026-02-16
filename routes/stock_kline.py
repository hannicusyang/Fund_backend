# routes/stock_kline.py
from flask import Blueprint, jsonify, request
import akshare as ak
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
        data.reverse()
        
        return jsonify({
            "success": True,
            "data": data,
            "message": "获取成功",
            "total": len(data)
        })
        
    except Exception as e:
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
                'wr': float(row['WR']) if pd.notna(row['WR']) else None
            })
        
        data.reverse()
        
        return jsonify({
            "success": True,
            "data": data,
            "message": "获取成功",
            "total": len(data)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "data": [],
            "message": f"获取失败: {str(e)}"
        }), 500
