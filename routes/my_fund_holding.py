# routes/holding.py
import json

import requests
from flask import Blueprint, jsonify
from models import db, FundNavHistory
from models.my_fund_holding import MyFundHolding
from models.fund_estimation import FundEstimation
from models.fund_open_rank import FundOpenRankAll  # 用于获取基金名称
from datetime import date
from flask import request
from datetime import datetime, timedelta
from sqlalchemy import and_, func
from collections import defaultdict

from config import *

holding_bp = Blueprint('holding', __name__)
USER_ID = 'default'  # 单用户系统

# ✅ 排序字段白名单（仅允许安全字段）
ALLOWED_SORT_FIELDS = {
    'fund_code',
    'fund_name',
    'cost_price',
    'shares',
    'holding_value',
    'total_cost',
    'profit',
    'profit_rate',
    'estimated_nav',
    'daily_growth_rate',
    'last_nav',
    'net_value_date',
    'purchased_at'
}


def calculate_profit_and_rate(cost_price, shares, current_nav):
    """计算持有收益和持有收益率"""
    try:
        # 统一转为 float，避免 Decimal 和 float 混用
        cost_price_f = float(cost_price) if cost_price is not None else 0.0
        shares_f = float(shares) if shares is not None else 0.0
        current_nav_f = float(current_nav) if current_nav is not None else 0.0
    except (TypeError, ValueError):
        return 0.0, 0.0

    if cost_price_f == 0 or shares_f == 0 or current_nav_f == 0:
        return 0.0, 0.0

    total_cost = cost_price_f * shares_f
    current_value = current_nav_f * shares_f
    profit = current_value - total_cost
    profit_rate = profit / total_cost if total_cost != 0 else 0.0

    return round(profit, 2), round(profit_rate * 100, 2)


def get_fund_estimation_from_tian_tian(fund_code):
    """
    从天天基金网获取单只基金的估值数据
    返回: dict 或 None
    """
    try:
        url = f"http://fundgz.1234567.com.cn/js/{fund_code}.js"
        response = requests.get(url, timeout=5)

        if response.status_code == 200 and len(response.text) > 20:
            # 解析 JSONP: jsonpgz({...})
            data_str = response.text[8:-2]  # 去掉 jsonpgz( 和 );
            data = json.loads(data_str)

            # 提取所需字段
            estimated_nav = float(data.get("gsz", 0))  # 估算净值
            daily_growth_rate = float(data.get("gszzl", 0))  # 估算增长率 (%)
            gztime = data.get("gztime", "")  # 估算时间

            # 从 gztime 中提取日期部分 (格式: "2025-01-20 15:00")
            net_value_date = None
            if gztime and len(gztime) >= 10:
                date_str = gztime[:10]  # "2025-01-20"
                try:
                    net_value_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                except ValueError:
                    pass

            return {
                'estimated_nav': estimated_nav,
                'daily_growth_rate': daily_growth_rate,
                'net_value_date': net_value_date,
                'last_nav': float(data.get("dwjz", 0))  # 上一日单位净值
            }
    except Exception as e:
        # 记录错误但不中断主流程
        print(f"获取天天基金估值失败 {fund_code}: {str(e)}")
        pass

    return None

@holding_bp.route('/list', methods=['GET'])
def get_holding_list():
    """
    分页查询用户持仓列表（含实时估算净值和收益）
    Query Params:
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 20（最大 100）
        sort_field (str): 排序字段（需在白名单中）
        sort_order (str): 'asc' 或 'desc'，默认 'asc'
    """

    print("排序字段:", request.args.get('sort_field'), "顺序:", request.args.get('sort_order'))
    try:
        # 分页参数
        page = request.args.get('page', default=1, type=int)
        page_size = min(max(request.args.get('page_size', default=20, type=int), 1), 100)
        if page < 1:
            page = 1

        # 构建基础查询（只查当前用户）
        query = MyFundHolding.query.filter_by(user_id=USER_ID)
        if query.count() == 0:
            return jsonify({
                "success": True,
                "data": {
                    "items": [],
                    "total": 0,
                    "page": page,
                    "page_size": page_size,
                    "pages": 0
                }
            })

        # 获取所有持仓用于后续关联（先不分页，因为要 join 估值和名称）
        all_holdings = query.all()
        fund_codes = [h.fund_code for h in all_holdings]

        # 批量获取最新估算数据
        latest_estimations = {}
        if fund_codes:
            estimation_subq = db.session.query(
                FundEstimation.fund_code,
                db.func.max(FundEstimation.fetch_time).label('max_fetch_time')
            ).filter(FundEstimation.fund_code.in_(fund_codes)) \
             .group_by(FundEstimation.fund_code).subquery()

            estimations = db.session.query(FundEstimation) \
                .join(estimation_subq,
                      (FundEstimation.fund_code == estimation_subq.c.fund_code) &
                      (FundEstimation.fetch_time == estimation_subq.c.max_fetch_time)) \
                .all()
            for est in estimations:
                latest_estimations[est.fund_code] = est

        # 获取基金名称
        fund_names = {}
        if fund_codes:
            rank_records = FundOpenRankAll.query.filter(FundOpenRankAll.fund_code.in_(fund_codes)).all()
            for rec in rank_records:
                fund_names[rec.fund_code] = rec.fund_name

        # 构建完整结果列表（用于排序和分页）
        full_result = []
        for holding in all_holdings:
            fund_code = holding.fund_code
            est = latest_estimations.get(fund_code)

            current_nav = None
            net_value_date = None
            daily_growth_rate = None
            last_nav = None

            if est:
                current_nav = est.published_nav or est.estimated_nav
                net_value_date = est.estimation_date
                daily_growth_rate = est.published_growth_rate or est.estimated_growth_rate
                last_nav = est.last_nav


            # 如果数据库中没有估值数据，则从天天基金接口获取
            if current_nav is None:
                tian_tian_data = get_fund_estimation_from_tian_tian(fund_code)
                if tian_tian_data:
                    current_nav = tian_tian_data['estimated_nav']
                    net_value_date = tian_tian_data['net_value_date']
                    daily_growth_rate = tian_tian_data['daily_growth_rate']
                    last_nav = tian_tian_data['last_nav']

            profit, profit_rate = 0.0, 0.0
            if current_nav is not None and holding.shares > 0:
                profit, profit_rate = calculate_profit_and_rate(
                    holding.cost_price, holding.shares, current_nav
                )

            item = {
                "fund_code": fund_code,
                "fund_name": fund_names.get(fund_code, fund_code),
                "net_value_date": net_value_date.isoformat() if net_value_date else None,
                "estimated_nav": float(current_nav) if current_nav else None,
                "last_nav": float(last_nav) if last_nav else None,
                "holding_value": float(holding.total_cost) + profit,
                "cost_price": float(holding.cost_price),
                "shares": float(holding.shares),
                "total_cost": float(holding.total_cost),
                "profit": profit,
                "daily_growth_rate": float(daily_growth_rate) if daily_growth_rate else None,
                "profit_rate": profit_rate,
                "purchased_at": holding.purchased_at.isoformat() if holding.purchased_at else None,
                "is_checked": True,
                # 临时保留原始对象用于排序
                "_holding_obj": holding,
                "_est_obj": est
            }
            full_result.append(item)

        # ✅ 排序逻辑
        sort_field = request.args.get('sort_field', '').strip()
        sort_order = request.args.get('sort_order', 'desc').lower()

        if sort_field in ALLOWED_SORT_FIELDS:
            # 提取排序值的函数
            def get_sort_value(item):
                value = item.get(sort_field)
                # 处理 None 值：排在最后
                if value is None:
                    return (1, '') if sort_order == 'asc' else (0, '')
                return (0, value)

            full_result.sort(
                key=get_sort_value,
                reverse=(sort_order == 'desc')
            )
        else:
            # 默认排序：按 fund_code 升序
            full_result.sort(key=lambda x: x['fund_code'] or '')

        # ✅ 手动分页
        total = len(full_result)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_items = full_result[start:end]
        pages = (total + page_size - 1) // page_size

        # 移除临时字段
        for item in paginated_items:
            item.pop('_holding_obj', None)
            item.pop('_est_obj', None)

        return jsonify({
            "success": True,
            "data": {
                "items": paginated_items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "pages": pages
            }
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"查询失败: {str(e)}"
        }), 500

@holding_bp.route('/update', methods=['PATCH'])
def update_holding():
    """
    更新用户某只基金的持仓信息
    请求体 JSON:
    {
        "fund_code": "001234",
        "cost_price": 1.2500,   # 可选
        "shares": 1000.0000,    # 可选
        "purchased_at": "2026-01-18T10:30:00"  # 可选，ISO 8601 格式
    }
    """
    try:
        data = request.get_json()
        fund_code = data.get('fund_code')

        if not fund_code:
            return jsonify({"success": False, "message": "缺少 fund_code"}), 400

        # 查询持仓记录
        holding = MyFundHolding.query.filter_by(
            user_id=USER_ID,
            fund_code=fund_code
        ).first()

        if not holding:
            return jsonify({"success": False, "message": "持仓记录不存在"}), 404

        # 更新字段（仅更新传入的字段）
        updated = False

        if 'cost_price' in data:
            cost_price = data['cost_price']
            if cost_price < 0:
                return jsonify({"success": False, "message": "成本单价不能为负数"}), 400
            holding.cost_price = cost_price
            updated = True

        if 'shares' in data:
            shares = data['shares']
            if shares < 0:
                return jsonify({"success": False, "message": "持仓份额不能为负数"}), 400
            holding.shares = shares
            updated = True

        if 'purchased_at' in data:
            try:
                # 支持 ISO 8601 字符串（如 "2026-01-18T10:30:00"）
                purchased_at = datetime.fromisoformat(data['purchased_at'].replace('Z', '+00:00'))
                holding.purchased_at = purchased_at
                updated = True
            except ValueError:
                return jsonify({"success": False, "message": "purchased_at 格式无效，应为 ISO 8601"}), 400

        # 如果更新了成本或份额，重新计算 total_cost
        if 'cost_price' in data or 'shares' in data:
            holding.total_cost = holding.cost_price * holding.shares

        if updated:
            db.session.commit()
            return jsonify({"success": True, "message": "持仓更新成功"})
        else:
            return jsonify({"success": True, "message": "无更新内容"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500





@holding_bp.route('/portfolio-history', methods=['GET'])
def get_portfolio_history():
    """
    计算用户投资组合的历史每日资产、收益、收益率
    基于 fund_nav_history 的真实历史净值 + 用户当前持仓份额
    """
    try:
        user_id = USER_ID
        days = request.args.get('days', 30, type=int)
        if days < 1:
            days = 30
        elif days > 365:
            days = 365

        # 获取用户当前有效持仓（shares > 0）
        holdings = MyFundHolding.query.filter(
            MyFundHolding.user_id == user_id,
            MyFundHolding.shares > 0
        ).all()

        if not holdings:
            return jsonify({"success": True, "data": []})

        fund_codes = [h.fund_code for h in holdings]
        holding_map = {h.fund_code: h for h in holdings}

        # 计算起始日期
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days)

        # 查询这些基金在 [start_date, end_date] 的所有历史净值
        nav_records = FundNavHistory.query.filter(
            and_(
                FundNavHistory.fund_code.in_(fund_codes),
                FundNavHistory.nav_date >= start_date,
                FundNavHistory.nav_date <= end_date
            )
        ).order_by(FundNavHistory.nav_date).all()

        # 按日期分组
        date_navs = defaultdict(dict)  # {date: {fund_code: nav}}
        for rec in nav_records:
            date_str = rec.nav_date.isoformat()
            date_navs[date_str][rec.fund_code] = float(rec.net_value)

        # 构建结果
        history_data = []
        for date_str in sorted(date_navs.keys()):
            total_asset = 0.0
            total_cost = 0.0

            for fund_code, nav in date_navs[date_str].items():
                holding = holding_map.get(fund_code)
                if not holding:
                    continue
                shares = float(holding.shares)
                cost = float(holding.total_cost)

                current_value = nav * shares
                total_asset += current_value
                total_cost += cost

            if total_cost <= 0:
                profit = 0.0
                profit_rate = 0.0
            else:
                profit = total_asset - total_cost
                profit_rate = (profit / total_cost) * 100

            history_data.append({
                "date": date_str,
                "total_asset": round(total_asset, 2),
                "total_profit": round(profit, 2),
                "total_profit_rate": round(profit_rate, 2)
            })

        # 确保按日期排序
        history_data.sort(key=lambda x: x["date"])

        return jsonify({"success": True, "data": history_data})

    except Exception as e:
        logger.error(f"获取组合历史失败: {str(e)}")
        return jsonify({"success": False, "message": "获取历史数据失败"}), 500