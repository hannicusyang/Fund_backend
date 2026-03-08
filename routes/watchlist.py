# routes/watchlist.py
from datetime import datetime, timezone, timedelta
from flask import Blueprint, jsonify, request
from models import db
from models.fund_watchlist import FundWatchlist
from models.fund_open_rank import FundOpenRankAll
from models.my_fund_holding import MyFundHolding
from utils.auth import get_current_user_id_or_default

# 东八区时区
SHANGHAI_TZ = timezone(timedelta(hours=8))

watchlist_bp = Blueprint('watchlist', __name__)


@watchlist_bp.route('/add', methods=['POST'])
def add_to_watchlist():
    """添加基金到观察清单，并设置 is_checked=1"""
    data = request.get_json()
    fund_code = data.get('fund_code')
    user_id = get_current_user_id_or_default()


    if not fund_code:
        return jsonify({"success": False, "message": "缺少 fund_code"}), 400

    # 检查基金是否存在于排行表中
    rank_record = FundOpenRankAll.query.filter_by(fund_code=fund_code).first()
    if not rank_record:
        return jsonify({"success": False, "message": "基金代码不存在于排行表"}), 404

    # 检查是否已关注
    existing = FundWatchlist.query.filter_by(user_id=user_id, fund_code=fund_code).first()
    if existing:
        # 如果已存在，但仍需确保 is_checked=1（修复不一致）
        if not rank_record.is_checked:
            rank_record.is_checked = True
            db.session.commit()
        return jsonify({"success": True, "message": "已在观察清单中"}), 200

    # 创建 MyFundHolding 初始化记录 ===
    from datetime import datetime
    holding = MyFundHolding(
        user_id=user_id,
        fund_code=fund_code,
        cost_price=0,
        shares=0,
        total_cost=0,
        purchased_at=datetime.now(SHANGHAI_TZ)  # 首次“虚拟”买入时间
    )
    db.session.add(holding)

    # 添加到观察清单
    watch_item = FundWatchlist(user_id=user_id, fund_code=fund_code)
    db.session.add(watch_item)

    # 同步设置 is_checked = 1
    rank_record.is_checked = True

    db.session.commit()
    return jsonify({"success": True, "message": "已加入观察清单并初始化持仓"}), 201


@watchlist_bp.route('/remove/<fund_code>', methods=['DELETE'])
def remove_from_watchlist(fund_code):
    """从观察清单移除，并设置 is_checked=0"""
    user_id = get_current_user_id_or_default()
    if not fund_code:
        return jsonify({"success": False, "message": "缺少 fund_code"}), 400

    # 查找观察记录
    watch_item = FundWatchlist.query.filter_by(user_id=user_id, fund_code=fund_code).first()
    if not watch_item:
        # 如果不在观察清单，但 is_checked=1，也应修复为 0（保持一致性）
        rank_record = FundOpenRankAll.query.filter_by(fund_code=fund_code).first()
        if rank_record and rank_record.is_checked:
            rank_record.is_checked = False
            db.session.commit()
        return jsonify({"success": False, "message": "未在观察清单中"}), 404

    # === 新增：删除 MyFundHolding 记录 ===
    holding = MyFundHolding.query.filter_by(user_id=user_id, fund_code=fund_code).first()
    if holding:
        db.session.delete(holding)

    # 删除观察记录
    db.session.delete(watch_item)

    # 同步设置 is_checked = 0
    rank_record = FundOpenRankAll.query.filter_by(fund_code=fund_code).first()
    if rank_record:
        rank_record.is_checked = False

    db.session.commit()
    return jsonify({"success": True, "message": "已移除观察清单及持仓记录"}), 200


@watchlist_bp.route('/list', methods=['GET'])
def get_watchlist():
    """获取观察清单（可选：只返回 is_checked=1 的，但我们以 watchlist 表为准）"""
    user_id = get_current_user_id_or_default()
    items = db.session.query(FundWatchlist, FundOpenRankAll.fund_name) \
        .join(FundOpenRankAll, FundWatchlist.fund_code == FundOpenRankAll.fund_code) \
        .filter(FundWatchlist.user_id == user_id) \
        .order_by(FundWatchlist.added_at.desc()) \
        .all()

    result = []
    for watch, fund_name in items:
        result.append({
            "fund_code": watch.fund_code,
            "fund_name": fund_name or watch.fund_code,
            "added_at": watch.added_at.isoformat() if watch.added_at else None
        })

    return jsonify({
        "success": True,
        "data": result
    })


@watchlist_bp.route('/check/<fund_code>', methods=['GET'])
def check_in_watchlist(fund_code):
    """检查是否在观察清单中（也可直接查 is_checked，但以 watchlist 为准更可靠）"""
    user_id = get_current_user_id_or_default()
    exists = FundWatchlist.query.filter_by(
        user_id=user_id,
        fund_code=fund_code
    ).first() is not None

    return jsonify({
        "success": True,
        "data": {
            "is_watched": exists
        }
    })