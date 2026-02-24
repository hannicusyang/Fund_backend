from flask import Blueprint, jsonify, request
from models import db, StockWatchlist
from models.stock_screening import StockScreening

stock_watchlist_bp = Blueprint('stock_watchlist', __name__)

USER_ID = 'default'  # 单用户系统


@stock_watchlist_bp.route('/add', methods=['POST'])
def add_to_watchlist():
    """添加股票到自选清单"""
    data = request.get_json()
    stock_code = data.get('stock_code')
    stock_name = data.get('stock_name', '')

    if not stock_code:
        return jsonify({"success": False, "message": "缺少 stock_code"}), 400

    # 检查是否已关注
    existing = StockWatchlist.query.filter_by(user_id=USER_ID, stock_code=stock_code).first()
    if existing:
        return jsonify({"success": True, "message": "已在自选清单中"}), 200

    # 添加到自选清单
    watch_item = StockWatchlist(
        user_id=USER_ID,
        stock_code=stock_code,
        stock_name=stock_name
    )
    db.session.add(watch_item)
    db.session.commit()

    return jsonify({"success": True, "message": "已加入自选清单"}), 201


@stock_watchlist_bp.route('/remove/<stock_code>', methods=['DELETE'])
def remove_from_watchlist(stock_code):
    """从自选清单移除"""
    if not stock_code:
        return jsonify({"success": False, "message": "缺少 stock_code"}), 400

    # 查找自选记录
    watch_item = StockWatchlist.query.filter_by(user_id=USER_ID, stock_code=stock_code).first()
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
    """获取自选清单（含实时价格和动量数据）"""
    items = StockWatchlist.query.filter_by(user_id=USER_ID) \
        .order_by(StockWatchlist.added_at.desc()) \
        .all()

    result = []
    for item in items:
        # 查询股票实时数据
        stock_data = StockScreening.query.filter_by(stock_code=item.stock_code).first()
        
        result.append({
            "stock_code": item.stock_code,
            "stock_name": item.stock_name,
            "added_at": item.added_at.isoformat() if item.added_at else None,
            "latest_price": stock_data.latest_price if stock_data and stock_data.latest_price else 0,
            "change_5d": stock_data.change_5d if stock_data and stock_data.change_5d else 0,
            "change_10d": stock_data.change_10d if stock_data and stock_data.change_10d else 0,
            "change_20d": stock_data.change_20d if stock_data and stock_data.change_20d else 0,
            "change_percent": stock_data.change_percent if stock_data and stock_data.change_percent else 0,
            "volume": stock_data.volume if stock_data and stock_data.volume else 0,
            "turnover_rate": stock_data.turnover_rate if stock_data and stock_data.turnover_rate else 0,
            "pe": stock_data.pe if stock_data and stock_data.pe else None,
            "market_cap": stock_data.market_cap if stock_data and stock_data.market_cap else None,
        })

    return jsonify({
        "success": True,
        "data": result
    })


@stock_watchlist_bp.route('/check/<stock_code>', methods=['GET'])
def check_in_watchlist(stock_code):
    """检查是否在自选清单中"""
    exists = StockWatchlist.query.filter_by(
        user_id=USER_ID,
        stock_code=stock_code
    ).first() is not None

    return jsonify({
        "success": True,
        "data": {
            "is_watched": exists
        }
    })
