# routes/fund_rank.py
from flask import Blueprint, request, jsonify
from models import db
from models.fund_open_rank import FundOpenRankAll
import  akshare as ak
import pandas as pd
fund_rank_bp = Blueprint('fund_rank', __name__)

# 排序字段白名单（仅允许安全字段）
ALLOWED_SORT_FIELDS = {
    'rank',
    'fund_code',
    'fund_name',
    'net_value',
    'daily_growth_rate',
    'weekly_growth_rate',
    'monthly_1_growth_rate',
    'monthly_3_growth_rate',
    'monthly_6_growth_rate',
    'yearly_1_growth_rate',
    'yearly_2_growth_rate',
    'yearly_3_growth_rate',
    'ytd_growth_rate',
    'update_time'
}

@fund_rank_bp.route('/list', methods=['GET'])
def get_fund_rank_list():
    """
    分页查询基金排行列表
    Query Params:
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 20（最大 100）
        fund_code (str): 基金代码（前缀匹配）
        fund_name (str): 基金名称（模糊包含）
        sort_field (str): 排序字段（需在白名单中）
        sort_order (str): 'asc' 或 'desc'，默认 'asc'（因 rank 小者靠前）
    """
    try:
        # 分页参数
        page = request.args.get('page', default=1, type=int)
        page_size = min(max(request.args.get('page_size', default=20, type=int), 1), 100)
        if page < 1:
            page = 1

        # 搜索条件
        fund_code = request.args.get('fund_code', '').strip()
        fund_name = request.args.get('fund_name', '').strip()

        # 构建基础查询
        query = FundOpenRankAll.query

        if fund_code:
            query = query.filter(FundOpenRankAll.fund_code.like(f"{fund_code}%"))
        if fund_name:
            query = query.filter(FundOpenRankAll.fund_name.like(f"%{fund_name}%"))

        # 排序逻辑
        sort_field = request.args.get('sort_field', '').strip()
        sort_order = request.args.get('sort_order', 'asc').lower()

        if sort_field in ALLOWED_SORT_FIELDS:
            column = getattr(FundOpenRankAll, sort_field)
            if sort_order == 'desc':
                query = query.order_by(column.desc())
            else:
                query = query.order_by(column.asc())
        else:
            # 默认排序：rank ASC（排名靠前优先），若 rank 为 NULL 则按 fund_code 排
            query = query.order_by(
                db.case((FundOpenRankAll.rank.isnot(None), FundOpenRankAll.rank), else_=999999),
                FundOpenRankAll.fund_code
            )

        # 执行分页
        paginated = query.paginate(page=page, per_page=page_size, error_out=False)

        # 序列化数据
        items = []
        for fund in paginated.items:
            items.append({
                "id": fund.id,
                "rank": fund.rank,
                "fund_code": fund.fund_code,
                "fund_name": fund.fund_name,
                "date": fund.date,  # 如 '01-13'
                "net_value": fund.net_value,
                "accumulated_net_value": fund.accumulated_net_value,
                "daily_growth_rate": fund.daily_growth_rate,      # %
                "weekly_growth_rate": fund.weekly_growth_rate,
                "monthly_1_growth_rate": fund.monthly_1_growth_rate,
                "monthly_3_growth_rate": fund.monthly_3_growth_rate,
                "monthly_6_growth_rate": fund.monthly_6_growth_rate,
                "yearly_1_growth_rate": fund.yearly_1_growth_rate,
                "yearly_2_growth_rate": fund.yearly_2_growth_rate,
                "yearly_3_growth_rate": fund.yearly_3_growth_rate,
                "ytd_growth_rate": fund.ytd_growth_rate,
                "since_inception_growth_rate": fund.since_inception_growth_rate,
                "custom_growth_rate": fund.custom_growth_rate,
                "fee_rate": fund.fee_rate,
                "is_checked": bool(fund.is_checked) if fund.is_checked is not None else False,
                "update_time": fund.update_time.isoformat() if fund.update_time else None
            })

        return jsonify({
            "success": True,
            "data": {
                "items": items,
                "total": paginated.total,
                "page": page,
                "page_size": page_size,
                "pages": paginated.pages
            }
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"查询失败: {str(e)}"
        }), 500


@fund_rank_bp.route('/detail/<fund_code>', methods=['GET'])
def get_fund_detail(fund_code):
    try:
        # 调用 akshare 接口获取基金详情
        df = ak.fund_individual_basic_info_xq(symbol=fund_code)

        if df.empty:
            return jsonify({
                'success': False,
                'message': '未找到基金信息'
            }), 404

        print(f"正在获取基金详情: {fund_code}")

        # 转换为字典格式
        fund_info = {}
        for _, row in df.iterrows():
            key = str(row['item']) if pd.notna(row['item']) else ''
            value = str(row['value']) if pd.notna(row['value']) else ''
            fund_info[key] = value

        return jsonify({
            'success': True,
            'data': fund_info
        })

    except Exception as e:
        print(f"获取基金详情失败 {fund_code}: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取基金详情失败，请稍后重试'
        }), 500
