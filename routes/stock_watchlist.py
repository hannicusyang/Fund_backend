from flask import Blueprint, jsonify, request
from models import db, StockWatchlist
from models.stock_screening import StockScreeningData
import baostock as bs
from datetime import datetime, timedelta
import math

# 导入tushare
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.tushare_api import get_pro, get_daily
from utils.auth import get_current_user_id_or_default

stock_watchlist_bp = Blueprint('stock_watchlist', __name__)

# 简单的缓存机制
_volatility_cache = {}

def calculate_volatility(stock_code, days=20):
    """计算股票波动率（基于历史K线数据）"""
    # 检查缓存（缓存1小时）
    cache_key = f"{stock_code}_{days}"
    if cache_key in _volatility_cache:
        cached_time, cached_result = _volatility_cache[cache_key]
        if (datetime.now() - cached_time).total_seconds() < 3600:
            return cached_result
    
    try:
        # 转换代码格式
        if stock_code.startswith('6'):
            bs_code = f"sh.{stock_code}"
        elif stock_code.startswith(('0', '3')):
            bs_code = f"sz.{stock_code}"
        else:
            return None, None
        
        # 计算日期范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 30)
        
        lg = bs.login()
        if lg.error_code != '0':
            return None, None
        
        rs = bs.query_history_k_data_plus(
            bs_code,
            'date,close,pctChg',
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            frequency='d',
            adjustflag='2'  # 前复权
        )
        
        if rs is None or rs.error_code != '0':
            bs.logout()
            return None, None
        
        daily_returns = []
        while (rs.error_code == '0') & rs.next():
            row = rs.get_row_data()
            if len(row) >= 3 and row[2]:  # 有涨跌幅数据
                try:
                    daily_returns.append(float(row[2]))
                except:
                    pass
        
        bs.logout()
        
        if len(daily_returns) < 5:
            # 缓存失败结果
            _volatility_cache[cache_key] = (datetime.now(), (None, None))
            return None, None
        
        # 计算日收益率的标准差（波动率）
        mean_return = sum(daily_returns) / len(daily_returns)
        variance = sum((x - mean_return) ** 2 for x in daily_returns) / len(daily_returns)
        daily_volatility = math.sqrt(variance)
        
        # 年化波动率（假设252个交易日）
        annual_volatility = daily_volatility * math.sqrt(252)
        
        # 计算60日累计收益率（作为预期收益的参考）
        return_60d = sum(daily_returns[-60:]) if len(daily_returns) >= 60 else sum(daily_returns)
        
        result = (round(annual_volatility, 2), round(return_60d, 2))
        
        # 缓存结果
        _volatility_cache[cache_key] = (datetime.now(), result)
        
        return result
        
    except Exception as e:
        print(f"计算波动率失败 {stock_code}: {e}")
        # 缓存失败结果
        _volatility_cache[cache_key] = (datetime.now(), (None, None))
        return None, None


@stock_watchlist_bp.route('/add', methods=['POST'])
def add_to_watchlist():
    user_id = get_current_user_id_or_default()
    user_id = get_current_user_id_or_default()
    """添加股票到自选清单"""
    data = request.get_json()
    stock_code = data.get('stock_code')
    stock_name = data.get('stock_name', '')

    if not stock_code:
        return jsonify({"success": False, "message": "缺少 stock_code"}), 400

    # 检查是否已关注
    existing = StockWatchlist.query.filter_by(user_id=user_id, stock_code=stock_code).first()
    if existing:
        return jsonify({"success": True, "message": "已在自选清单中"}), 200

    # 添加到自选清单
    watch_item = StockWatchlist(
        user_id=user_id,
        stock_code=stock_code,
        stock_name=stock_name
    )
    db.session.add(watch_item)
    db.session.commit()

    return jsonify({"success": True, "message": "已加入自选清单"}), 201


@stock_watchlist_bp.route('/remove/<stock_code>', methods=['DELETE'])
def remove_from_watchlist(stock_code):
    user_id = get_current_user_id_or_default()
    """从自选清单移除"""
    if not stock_code:
        return jsonify({"success": False, "message": "缺少 stock_code"}), 400

    # 查找自选记录
    watch_item = StockWatchlist.query.filter_by(user_id=user_id, stock_code=stock_code).first()
    if watch_item:
        # 删除自选记录
        db.session.delete(watch_item)
        db.session.commit()
        return jsonify({"success": True, "message": "已移除自选清单"}), 200
    else:
        # 已经不在自选中，也返回成功（幂等性）
        return jsonify({"success": True, "message": "不在自选清单中"}), 200


@stock_watchlist_bp.route('/list', methods=['GET'])
def get_watchlist():
    user_id = get_current_user_id_or_default()
    """获取自选清单（含实时价格和风险数据）"""
    items = StockWatchlist.query.filter_by(user_id=user_id) \
        .order_by(StockWatchlist.added_at.desc()) \
        .all()

    result = []
    for item in items:
        # 查询股票实时数据
        stock_data = StockScreeningData.query.filter_by(stock_code=item.stock_code).first()
        
        # 使用数据库中的数据
        expected_return = None
        volatility = None
        
        if stock_data:
            # 预期收益：优先用60日，其次20日
            if stock_data.change_60d:
                expected_return = float(stock_data.change_60d)
            elif stock_data.change_20d:
                expected_return = float(stock_data.change_20d)
            
            # 波动率：优先用数据库中预计算的，其次用估算
            if stock_data.volatility:
                volatility = float(stock_data.volatility)
            elif expected_return:
                volatility = abs(expected_return) * 0.5  # 简化估算作为备用
        
        result.append({
            "stock_code": item.stock_code,
            "stock_name": item.stock_name,
            "added_at": item.added_at.isoformat() if item.added_at else None,
            "latest_price": float(stock_data.latest_price) if stock_data and stock_data.latest_price else 0,
            "change_5d": float(stock_data.change_5d) if stock_data and stock_data.change_5d else 0,
            "change_10d": float(stock_data.change_10d) if stock_data and stock_data.change_10d else 0,
            "change_20d": float(stock_data.change_20d) if stock_data and stock_data.change_20d else 0,
            "change_percent": float(stock_data.change_percent) if stock_data and stock_data.change_percent else 0,
            "volume": float(stock_data.volume) if stock_data and stock_data.volume else 0,
            "turnover_rate": float(stock_data.turnover_rate) if stock_data and stock_data.turnover_rate else 0,
            "pe": float(stock_data.pe) if stock_data and stock_data.pe else None,
            "market_cap": float(stock_data.market_cap) if stock_data and stock_data.market_cap else None,
            "volatility": volatility,
            "expected_return": expected_return,
        })

    return jsonify({
        "success": True,
        "data": result
    })


@stock_watchlist_bp.route('/check/<stock_code>', methods=['GET'])
def check_in_watchlist(stock_code):
    user_id = get_current_user_id_or_default()
    """检查是否在自选清单中"""
    exists = StockWatchlist.query.filter_by(
        user_id=user_id,
        stock_code=stock_code
    ).first() is not None

    return jsonify({
        "success": True,
        "data": {
            "is_watched": exists
        }
    })
