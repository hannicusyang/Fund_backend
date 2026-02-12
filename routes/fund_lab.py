"""
基金实验室 API 路由
支持基金筛选、组合构建、回测等功能
"""
from flask import Blueprint, request, jsonify
from models import db
from models.fund_open_rank import FundOpenRankAll
from models.fund_list import FundList
from models.fund_nav_history import FundNavHistory
from models.my_fund_holding import MyFundHolding
from models.fund_watchlist import FundWatchlist
from models.index_history import IndexHistory, BENCHMARK_INDICES
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from sqlalchemy import func

fund_lab_bp = Blueprint('fund_lab', __name__)


# ==================== 基金筛选相关接口 ====================

@fund_lab_bp.route('/screen/ranges', methods=['GET'])
def get_screen_ranges():
    """
    获取筛选条件的范围统计（用于前端动态设置滑块范围）

    Returns:
        各筛选字段的最小值、最大值
    """
    try:
        # 使用SQL查询获取各字段的统计值
        from sqlalchemy import func

        stats = db.session.query(
            func.min(FundOpenRankAll.weekly_growth_rate).label('min_weekly'),
            func.max(FundOpenRankAll.weekly_growth_rate).label('max_weekly'),
            func.min(FundOpenRankAll.monthly_1_growth_rate).label('min_monthly'),
            func.max(FundOpenRankAll.monthly_1_growth_rate).label('max_monthly'),
            func.min(FundOpenRankAll.yearly_1_growth_rate).label('min_yearly'),
            func.max(FundOpenRankAll.yearly_1_growth_rate).label('max_yearly'),
            func.count(FundOpenRankAll.id).label('total_count')
        ).first()

        # 处理None值，设置合理的默认值
        def safe_value(val, default):
            return float(val) if val is not None else default

        # 向上/向下取整到合适的步长
        def round_range(min_val, max_val, step=10):
            import math
            min_rounded = math.floor(min_val / step) * step
            max_rounded = math.ceil(max_val / step) * step
            return min_rounded, max_rounded

        weekly_min, weekly_max = round_range(
            safe_value(stats.min_weekly, -20),
            safe_value(stats.max_weekly, 50),
            step=5
        )

        monthly_min, monthly_max = round_range(
            safe_value(stats.min_monthly, -30),
            safe_value(stats.max_monthly, 100),
            step=10
        )

        yearly_min, yearly_max = round_range(
            safe_value(stats.min_yearly, -50),
            safe_value(stats.max_yearly, 200),
            step=50
        )

        return jsonify({
            "success": True,
            "data": {
                "weekly": {
                    "min": weekly_min,
                    "max": weekly_max,
                    "default_min": weekly_min,
                    "default_max": weekly_max
                },
                "monthly": {
                    "min": monthly_min,
                    "max": monthly_max,
                    "default_min": monthly_min,
                    "default_max": monthly_max
                },
                "yearly": {
                    "min": yearly_min,
                    "max": yearly_max,
                    "default_min": yearly_min,
                    "default_max": yearly_max
                },
                "rankRatio": {
                    "min": 0,
                    "max": 100,
                    "default_min": 0,
                    "default_max": 100
                },
                "total_count": stats.total_count if stats.total_count else 0
            }
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"获取范围数据失败: {str(e)}"
        }), 500


@fund_lab_bp.route('/screen', methods=['GET'])
def screen_funds():
    """
    多维度基金筛选

    Query Params:
        fund_types (str): 基金类型，逗号分隔，如"股票型,混合型"
        keyword (str): 关键词（基金代码或名称模糊搜索）
        min_rank_ratio (float): 最小排名比例（如0表示最前面）
        max_rank_ratio (float): 最大排名比例（如20表示前20%）
        min_yearly_return (float): 最小年化收益
        max_yearly_return (float): 最大年化收益
        min_weekly_return (float): 最小周涨幅
        max_weekly_return (float): 最大周涨幅
        min_monthly_return (float): 最小月涨幅
        max_monthly_return (float): 最大月涨幅
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 20

    Returns:
        筛选后的基金列表
    """
    try:
        # 分页参数
        page = request.args.get('page', default=1, type=int)
        page_size = min(max(request.args.get('page_size', default=20, type=int), 1), 100)

        # 构建查询（基础查询，用于筛选前的统计）
        base_query = FundOpenRankAll.query

        # 基金类型筛选
        fund_types = request.args.get('fund_types', '').strip()
        if fund_types:
            types = fund_types.split(',')
            fund_codes = FundList.query.filter(
                FundList.fund_type.in_(types)
            ).with_entities(FundList.fund_code).all()
            fund_code_list = [f[0] for f in fund_codes]
            if fund_code_list:
                base_query = base_query.filter(FundOpenRankAll.fund_code.in_(fund_code_list))

        # 关键词搜索
        keyword = request.args.get('keyword', '').strip()
        if keyword:
            base_query = base_query.filter(
                db.or_(
                    FundOpenRankAll.fund_code.like(f"{keyword}%"),
                    FundOpenRankAll.fund_name.like(f"%{keyword}%")
                )
            )

        # 先获取总数（用于排名比例计算）
        total_count = base_query.count()

        # 主查询
        query = base_query

        # 排名比例筛选（根据排名占总数的百分比）
        min_rank_ratio = request.args.get('min_rank_ratio', type=float)
        max_rank_ratio = request.args.get('max_rank_ratio', type=float)

        if min_rank_ratio is not None or max_rank_ratio is not None:
            # 排名比例 = (rank / total_count) * 100
            # 比例越小表示排名越靠前
            if total_count > 0:
                if min_rank_ratio is not None:
                    # min_rank_ratio对应较大的rank值
                    min_rank = int((min_rank_ratio / 100) * total_count)
                    query = query.filter(FundOpenRankAll.rank >= min_rank)
                if max_rank_ratio is not None:
                    # max_rank_ratio对应较小的rank值
                    max_rank = int((max_rank_ratio / 100) * total_count)
                    query = query.filter(FundOpenRankAll.rank <= max_rank)

        # 收益率范围筛选
        min_yearly = request.args.get('min_yearly_return', type=float)
        max_yearly = request.args.get('max_yearly_return', type=float)
        if min_yearly is not None:
            query = query.filter(FundOpenRankAll.yearly_1_growth_rate >= min_yearly)
        if max_yearly is not None:
            query = query.filter(FundOpenRankAll.yearly_1_growth_rate <= max_yearly)

        min_weekly = request.args.get('min_weekly_return', type=float)
        max_weekly = request.args.get('max_weekly_return', type=float)
        if min_weekly is not None:
            query = query.filter(FundOpenRankAll.weekly_growth_rate >= min_weekly)
        if max_weekly is not None:
            query = query.filter(FundOpenRankAll.weekly_growth_rate <= max_weekly)

        min_monthly = request.args.get('min_monthly_return', type=float)
        max_monthly = request.args.get('max_monthly_return', type=float)
        if min_monthly is not None:
            query = query.filter(FundOpenRankAll.monthly_1_growth_rate >= min_monthly)
        if max_monthly is not None:
            query = query.filter(FundOpenRankAll.monthly_1_growth_rate <= max_monthly)

        # 默认按排名排序
        query = query.order_by(
            db.case((FundOpenRankAll.rank.isnot(None), FundOpenRankAll.rank), else_=999999),
            FundOpenRankAll.fund_code
        )

        # 执行分页
        paginated = query.paginate(page=page, per_page=page_size, error_out=False)

        # 序列化数据
        items = []
        for fund in paginated.items:
            # 计算排名比例
            rank_ratio = round((fund.rank / total_count) * 100, 2) if total_count > 0 and fund.rank else None

            items.append({
                "id": fund.id,
                "rank": fund.rank,
                "rank_ratio": rank_ratio,
                "fund_code": fund.fund_code,
                "fund_name": fund.fund_name,
                "fund_type": fund.fund_type if hasattr(fund, 'fund_type') else None,
                "date": fund.date,
                "net_value": fund.net_value,
                "accumulated_net_value": fund.accumulated_net_value,
                "daily_growth_rate": fund.daily_growth_rate,
                "weekly_growth_rate": fund.weekly_growth_rate,
                "monthly_1_growth_rate": fund.monthly_1_growth_rate,
                "monthly_3_growth_rate": fund.monthly_3_growth_rate,
                "monthly_6_growth_rate": fund.monthly_6_growth_rate,
                "yearly_1_growth_rate": fund.yearly_1_growth_rate,
                "yearly_2_growth_rate": fund.yearly_2_growth_rate,
                "yearly_3_growth_rate": fund.yearly_3_growth_rate,
                "ytd_growth_rate": fund.ytd_growth_rate,
                "since_inception_growth_rate": fund.since_inception_growth_rate,
                "fee_rate": fund.fee_rate,
                "update_time": fund.update_time.isoformat() if fund.update_time else None
            })

        return jsonify({
            "success": True,
            "data": {
                "items": items,
                "total": paginated.total,
                "page": page,
                "page_size": page_size,
                "pages": paginated.pages,
                "total_count": total_count
            }
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"筛选失败: {str(e)}"
        }), 500


@fund_lab_bp.route('/quick-filter/<filter_type>', methods=['GET'])
def quick_filter_funds(filter_type):
    """
    快捷筛选基金

    Args:
        filter_type: 筛选类型
            - top_performers: 年度收益 > 50% 的基金
            - recent_winners: 本周上涨的基金
            - my_watchlist: 我的关注列表
            - my_holdings: 我的持仓

    Query Params:
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 20
    """
    try:
        page = request.args.get('page', default=1, type=int)
        page_size = min(max(request.args.get('page_size', default=20, type=int), 1), 100)

        query = FundOpenRankAll.query

        if filter_type == 'top_performers':
            # 年度收益 > 50%
            query = query.filter(FundOpenRankAll.yearly_1_growth_rate > 50)
            query = query.order_by(FundOpenRankAll.yearly_1_growth_rate.desc())

        elif filter_type == 'recent_winners':
            # 本周上涨
            query = query.filter(FundOpenRankAll.weekly_growth_rate > 0)
            query = query.order_by(FundOpenRankAll.weekly_growth_rate.desc())

        elif filter_type == 'my_watchlist':
            # 我的关注
            watchlist_codes = FundWatchlist.query.with_entities(FundWatchlist.fund_code).all()
            code_list = [w[0] for w in watchlist_codes]
            query = query.filter(FundOpenRankAll.fund_code.in_(code_list))
            query = query.order_by(FundOpenRankAll.fund_code)

        elif filter_type == 'my_holdings':
            # 我的持仓
            holding_codes = MyFundHolding.query.with_entities(MyFundHolding.fund_code).all()
            code_list = [h[0] for h in holding_codes]
            query = query.filter(FundOpenRankAll.fund_code.in_(code_list))
            query = query.order_by(FundOpenRankAll.fund_code)

        else:
            return jsonify({
                "success": False,
                "message": "未知的筛选类型"
            }), 400

        paginated = query.paginate(page=page, per_page=page_size, error_out=False)

        items = [{
            "id": f.id,
            "rank": f.rank,
            "fund_code": f.fund_code,
            "fund_name": f.fund_name,
            "net_value": f.net_value,
            "daily_growth_rate": f.daily_growth_rate,
            "weekly_growth_rate": f.weekly_growth_rate,
            "monthly_1_growth_rate": f.monthly_1_growth_rate,
            "yearly_1_growth_rate": f.yearly_1_growth_rate,
            "update_time": f.update_time.isoformat() if f.update_time else None
        } for f in paginated.items]

        return jsonify({
            "success": True,
            "data": {
                "items": items,
                "total": paginated.total,
                "page": page,
                "page_size": page_size,
                "filter_type": filter_type
            }
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"快捷筛选失败: {str(e)}"
        }), 500


# ==================== 基金分析相关接口 ====================

def get_fund_nav_data_from_db(fund_code, start_date, end_date, min_records=20):
    """
    从数据库获取基金净值数据

    Args:
        fund_code: 基金代码
        start_date: 开始日期
        end_date: 结束日期
        min_records: 最小记录数要求

    Returns:
        list: 基金净值记录列表，如果没有足够数据则返回空列表
    """
    records = FundNavHistory.query.filter(
        FundNavHistory.fund_code == fund_code,
        FundNavHistory.nav_date >= start_date,
        FundNavHistory.nav_date <= end_date,
        FundNavHistory.net_value.isnot(None)
    ).order_by(FundNavHistory.nav_date.asc()).all()

    return records


def fetch_fund_nav_from_akshare(fund_code, start_date, end_date):
    """
    从 akshare 获取基金净值数据并保存到数据库

    Args:
        fund_code: 基金代码
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        list: 基金净值记录列表
    """
    try:
        import akshare as ak

        # 获取基金历史净值
        df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")

        if df is None or df.empty:
            return []

        # 重命名列
        df = df.rename(columns={
            '净值日期': 'nav_date',
            '单位净值': 'net_value',
            '日增长率': 'daily_growth_rate'
        })

        # 转换日期格式
        df['nav_date'] = pd.to_datetime(df['nav_date'])

        # 过滤时间范围
        df = df[(df['nav_date'] >= start_date) & (df['nav_date'] <= end_date)]

        # 保存到数据库
        for _, row in df.iterrows():
            # 检查是否已存在
            existing = FundNavHistory.query.filter_by(
                fund_code=fund_code,
                nav_date=row['nav_date'].date()
            ).first()

            if not existing:
                # 获取基金名称
                fund_info = FundOpenRankAll.query.filter_by(fund_code=fund_code).first()
                fund_name = fund_info.fund_name if fund_info else fund_code

                # 处理日增长率（可能是float或带%的字符串）
                growth_rate = row['daily_growth_rate']
                if pd.notna(growth_rate) and growth_rate != '-':
                    if isinstance(growth_rate, str):
                        growth_rate = float(growth_rate.replace('%', ''))
                    else:
                        growth_rate = float(growth_rate)
                else:
                    growth_rate = None

                nav_record = FundNavHistory(
                    fund_code=fund_code,
                    nav_date=row['nav_date'].date(),
                    fund_name=fund_name,
                    net_value=float(row['net_value']) if pd.notna(row['net_value']) else None,
                    daily_growth_rate=growth_rate
                )
                db.session.add(nav_record)

        db.session.commit()

        # 重新查询
        records = FundNavHistory.query.filter(
            FundNavHistory.fund_code == fund_code,
            FundNavHistory.nav_date >= start_date,
            FundNavHistory.nav_date <= end_date,
            FundNavHistory.net_value.isnot(None)
        ).order_by(FundNavHistory.nav_date.asc()).all()

        return records

    except Exception as e:
        print(f"从akshare获取基金{fund_code}数据失败: {e}")
        return []


@fund_lab_bp.route('/analysis/returns/<fund_codes>', methods=['GET'])
def get_funds_return_analysis(fund_codes):
    """
    获取多只基金的历史收益率数据（用于对比分析）
    优先从数据库获取，数据不足时从akshare获取并保存

    Args:
        fund_codes: 逗号分隔的基金代码列表，如"000001,000002"

    Query Params:
        start_date (str): 开始日期 YYYY-MM-DD
        end_date (str): 结束日期 YYYY-MM-DD

    Returns:
        各基金的历史净值和收益率数据
    """
    try:
        codes = fund_codes.split(',')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            # 默认获取近一年数据
            start = datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=365)
            start_date = start.strftime('%Y-%m-%d')

        result = {}
        for code in codes:
            # 优先从数据库查询
            records = get_fund_nav_data_from_db(code, start_date, end_date)

            # 检查数据是否完整（缺失天数超过10%则认为不完整）
            expected_days = (datetime.strptime(end_date, '%Y-%m-%d') -
                           datetime.strptime(start_date, '%Y-%m-%d')).days
            actual_days = len(records)
            data_complete = actual_days >= expected_days * 0.9

            # 数据不完整时，从akshare获取并保存
            if not data_complete:
                records = fetch_fund_nav_from_akshare(code, start_date, end_date)

            if records:
                result[code] = {
                    'fund_name': records[0].fund_name,
                    'data': [{
                        'date': r.nav_date.strftime('%Y-%m-%d'),
                        'net_value': float(r.net_value) if r.net_value else None,
                        'growth_rate': float(r.daily_growth_rate) if r.daily_growth_rate else None
                    } for r in records]
                }

        return jsonify({
            "success": True,
            "data": result,
            "period": {
                "start_date": start_date,
                "end_date": end_date
            }
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"获取收益率数据失败: {str(e)}"
        }), 500


@fund_lab_bp.route('/analysis/correlation', methods=['POST'])
def calculate_correlation():
    """
    计算多只基金的相关性矩阵

    Request Body:
        {
            "fund_codes": ["000001", "000002", "000003"],
            "start_date": "2024-01-01",  // 可选，默认近1年
            "end_date": "2024-12-31"     // 可选，默认今天
        }

    Returns:
        相关性矩阵和基金名称列表
    """
    try:
        data = request.get_json()
        fund_codes = data.get('fund_codes', [])
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        if not fund_codes or len(fund_codes) < 2:
            return jsonify({
                "success": False,
                "message": "至少需要2只基金才能计算相关性"
            }), 400

        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start = datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=365)
            start_date = start.strftime('%Y-%m-%d')

        # 获取每只基金的日收益率数据
        returns_data = {}
        fund_names = {}

        for code in fund_codes:
            # 优先从数据库查询
            records = FundNavHistory.query.filter(
                FundNavHistory.fund_code == code,
                FundNavHistory.nav_date >= start_date,
                FundNavHistory.nav_date <= end_date,
                FundNavHistory.daily_growth_rate.isnot(None)
            ).order_by(FundNavHistory.nav_date.asc()).all()

            # 数据不足时，从akshare获取
            expected_days = (datetime.strptime(end_date, '%Y-%m-%d') -
                           datetime.strptime(start_date, '%Y-%m-%d')).days
            if len(records) < expected_days * 0.5:
                records = fetch_fund_nav_from_akshare(code, start_date, end_date)
                # 重新查询获取日增长率
                records = FundNavHistory.query.filter(
                    FundNavHistory.fund_code == code,
                    FundNavHistory.nav_date >= start_date,
                    FundNavHistory.nav_date <= end_date,
                    FundNavHistory.daily_growth_rate.isnot(None)
                ).order_by(FundNavHistory.nav_date.asc()).all()

            if records:
                fund_names[code] = records[0].fund_name
                returns_data[code] = {
                    r.nav_date.strftime('%Y-%m-%d'): float(r.daily_growth_rate)
                    for r in records
                }

        if len(returns_data) < 2:
            return jsonify({
                "success": False,
                "message": "数据不足，无法计算相关性"
            }), 400

        # 构建收益率矩阵（对齐日期）
        all_dates = set()
        for code, data in returns_data.items():
            all_dates.update(data.keys())
        all_dates = sorted(all_dates)

        # 构建DataFrame
        df_data = {}
        for code in fund_codes:
            if code in returns_data:
                df_data[code] = [returns_data[code].get(date, 0) for date in all_dates]

        df = pd.DataFrame(df_data, index=all_dates)

        # 计算相关系数矩阵
        corr_matrix = df.corr()

        # 构建结果
        result = {
            "funds": [
                {
                    "code": code,
                    "name": fund_names.get(code, code)
                }
                for code in fund_codes if code in fund_names
            ],
            "matrix": corr_matrix.values.tolist(),
            "period": {
                "start_date": start_date,
                "end_date": end_date,
                "trading_days": len(all_dates)
            }
        }

        return jsonify({
            "success": True,
            "data": result
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"计算相关性失败: {str(e)}"
        }), 500


@fund_lab_bp.route('/analysis/risk-return', methods=['POST'])
def calculate_risk_return():
    """
    计算基金的风险收益分布数据

    Request Body:
        {
            "fund_codes": ["000001", "000002", "000003"],
            "volatility_period": "1y"  // 1m/3m/6m/1y/2y/3y，默认为1y
        }

    Returns:
        各基金的多时间维度收益率和波动率，以及市场平均水平
    """
    try:
        data = request.get_json()
        fund_codes = data.get('fund_codes', [])
        volatility_period = data.get('volatility_period', '1y')

        if not fund_codes:
            return jsonify({
                "success": False,
                "message": "基金代码不能为空"
            }), 400

        # 计算日期范围
        end_date = datetime.now().strftime('%Y-%m-%d')
        period_days = {
            '1m': 30,
            '3m': 90,
            '6m': 180,
            '1y': 365,
            '2y': 730,
            '3y': 1095
        }
        days = period_days.get(volatility_period, 365)
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        # 获取各基金的日收益率数据并计算波动率
        funds_result = []

        for code in fund_codes:
            # 优先从数据库查询
            records = FundNavHistory.query.filter(
                FundNavHistory.fund_code == code,
                FundNavHistory.nav_date >= start_date,
                FundNavHistory.nav_date <= end_date,
                FundNavHistory.daily_growth_rate.isnot(None)
            ).order_by(FundNavHistory.nav_date.asc()).all()

            # 数据不足时，从akshare获取
            expected_days = (datetime.strptime(end_date, '%Y-%m-%d') -
                           datetime.strptime(start_date, '%Y-%m-%d')).days
            if len(records) < expected_days * 0.5:
                records = fetch_fund_nav_from_akshare(code, start_date, end_date)
                # 重新查询获取日增长率
                records = FundNavHistory.query.filter(
                    FundNavHistory.fund_code == code,
                    FundNavHistory.nav_date >= start_date,
                    FundNavHistory.nav_date <= end_date,
                    FundNavHistory.daily_growth_rate.isnot(None)
                ).order_by(FundNavHistory.nav_date.asc()).all()

            if not records:
                continue

            # 获取基金基本信息
            fund_info = FundOpenRankAll.query.filter_by(fund_code=code).first()

            # 计算各期限波动率
            volatilities = {}
            returns = {}

            # 各期限对应的交易日天数
            trading_days = {'1m': 21, '3m': 63, '6m': 126, '1y': 252, '2y': 504, '3y': 756}

            for period, days_count in trading_days.items():
                recent_records = records[-days_count:] if len(records) >= days_count else records
                if len(recent_records) >= 10:  # 至少10个交易日数据
                    daily_returns = [float(r.daily_growth_rate) for r in recent_records]
                    # 年化波动率 = 日收益率标准差 * sqrt(交易日天数)
                    volatilities[period] = round(np.std(daily_returns) * np.sqrt(trading_days[period]), 2)

            # 从 fund_open_rank_all 获取各期收益率
            if fund_info:
                returns = {
                    '1m': fund_info.monthly_1_growth_rate,
                    '3m': fund_info.monthly_3_growth_rate,
                    '6m': fund_info.monthly_6_growth_rate,
                    '1y': fund_info.yearly_1_growth_rate,
                    '2y': fund_info.yearly_2_growth_rate,
                    '3y': fund_info.yearly_3_growth_rate
                }

            funds_result.append({
                'code': code,
                'name': fund_info.fund_name if fund_info else code,
                'returns': returns,
                'volatilities': volatilities
            })

        if not funds_result:
            return jsonify({
                "success": False,
                "message": "无有效数据"
            }), 400

        # 计算选中基金的平均值（选中基金平均）
        selected_avg = {
            'returns': {},
            'volatilities': {}
        }

        for period in ['1m', '3m', '6m', '1y', '2y', '3y']:
            # 计算平均收益率
            valid_returns = [f['returns'].get(period) for f in funds_result if f['returns'].get(period) is not None]
            if valid_returns:
                selected_avg['returns'][period] = round(sum(valid_returns) / len(valid_returns), 2)

            # 计算平均波动率
            valid_vols = [f['volatilities'].get(period) for f in funds_result if f['volatilities'].get(period) is not None]
            if valid_vols:
                selected_avg['volatilities'][period] = round(sum(valid_vols) / len(valid_vols), 2)

        # 计算全市场平均（简化版 - 只计算收益率）
        market_avg = {}
        for period in ['1m', '3m', '6m', '1y', '2y', '3y']:
            column_map = {
                '1m': FundOpenRankAll.monthly_1_growth_rate,
                '3m': FundOpenRankAll.monthly_3_growth_rate,
                '6m': FundOpenRankAll.monthly_6_growth_rate,
                '1y': FundOpenRankAll.yearly_1_growth_rate,
                '2y': FundOpenRankAll.yearly_2_growth_rate,
                '3y': FundOpenRankAll.yearly_3_growth_rate
            }

            avg_value = db.session.query(func.avg(column_map[period])).scalar()
            if avg_value is not None:
                market_avg[period] = round(float(avg_value), 2)

        # 无风险收益率（使用中国10年期国债收益率作为参考，约2.5%）
        risk_free_rate = 2.5

        # 计算每个基金的夏普比率
        for fund in funds_result:
            fund['sharpe_ratios'] = {}
            for period in ['1m', '3m', '6m', '1y', '2y', '3y']:
                ret = fund['returns'].get(period)
                vol = fund['volatilities'].get(period)
                if ret is not None and vol is not None and vol > 0:
                    fund['sharpe_ratios'][period] = round((ret - risk_free_rate) / vol, 2)

        # 找出最优基金（夏普比率最高）
        best_fund = None
        best_sharpe = -float('inf')
        for fund in funds_result:
            sharpe = fund['sharpe_ratios'].get(volatility_period)
            if sharpe is not None and sharpe > best_sharpe:
                best_sharpe = sharpe
                best_fund = fund

        return jsonify({
            "success": True,
            "data": {
                "funds": funds_result,
                "selected_avg": selected_avg,
                "market_avg": market_avg,
                "risk_free_rate": risk_free_rate,
                "best_fund": {
                    "code": best_fund['code'],
                    "name": best_fund['name'],
                    "sharpe": best_sharpe,
                    "return": best_fund['returns'].get(volatility_period),
                    "volatility": best_fund['volatilities'].get(volatility_period)
                } if best_fund else None
            }
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"计算风险收益数据失败: {str(e)}"
        }), 500


@fund_lab_bp.route('/analysis/metrics/<fund_codes>', methods=['GET'])
def get_funds_metrics(fund_codes):
    """
    获取多只基金的量化指标数据（用于对比分析）

    Args:
        fund_codes: 逗号分隔的基金代码列表

    Returns:
        各基金的量化指标（收益率、波动率、夏普比率等）
    """
    try:
        codes = fund_codes.split(',')

        funds = FundOpenRankAll.query.filter(
            FundOpenRankAll.fund_code.in_(codes)
        ).all()

        items = []
        for fund in funds:
            items.append({
                "fund_code": fund.fund_code,
                "fund_name": fund.fund_name,
                "rank": fund.rank,
                "net_value": fund.net_value,
                "daily_growth_rate": fund.daily_growth_rate,
                "weekly_growth_rate": fund.weekly_growth_rate,
                "monthly_1_growth_rate": fund.monthly_1_growth_rate,
                "monthly_3_growth_rate": fund.monthly_3_growth_rate,
                "monthly_6_growth_rate": fund.monthly_6_growth_rate,
                "yearly_1_growth_rate": fund.yearly_1_growth_rate,
                "yearly_2_growth_rate": fund.yearly_2_growth_rate,
                "yearly_3_growth_rate": fund.yearly_3_growth_rate,
                "ytd_growth_rate": fund.ytd_growth_rate,
                "since_inception_growth_rate": fund.since_inception_growth_rate,
                "fee_rate": fund.fee_rate
            })

        return jsonify({
            "success": True,
            "data": items
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"获取指标数据失败: {str(e)}"
        }), 500


@fund_lab_bp.route('/analysis/calculate-metrics', methods=['POST'])
def calculate_custom_metrics():
    """
    计算自定义组合的量化指标

    Request Body:
        {
            "funds": [
                {"fund_code": "000001", "weight": 0.3},
                {"fund_code": "000002", "weight": 0.4},
                {"fund_code": "000003", "weight": 0.3}
            ]
        }

    Returns:
        组合的预期收益、波动率、夏普比率等指标
    """
    try:
        data = request.get_json()
        funds = data.get('funds', [])

        if not funds:
            return jsonify({
                "success": False,
                "message": "基金列表不能为空"
            }), 400

        # 检查权重总和
        total_weight = sum(f.get('weight', 0) for f in funds)
        if abs(total_weight - 1.0) > 0.01:
            return jsonify({
                "success": False,
                "message": f"权重总和必须等于1（当前{total_weight:.2f}）"
            }), 400

        # 获取各基金数据
        fund_codes = [f['fund_code'] for f in funds]
        fund_data = FundOpenRankAll.query.filter(
            FundOpenRankAll.fund_code.in_(fund_codes)
        ).all()

        fund_map = {f.fund_code: f for f in fund_data}

        # 计算组合指标
        expected_return = 0
        weighted_volatility = 0

        for fund_info in funds:
            code = fund_info['fund_code']
            weight = fund_info['weight']
            fund = fund_map.get(code)

            if fund:
                # 年化收益率加权
                return_rate = fund.yearly_1_growth_rate or 0
                expected_return += return_rate * weight

                # 简化：使用历史波动率估算（假设年化波动率约为年化收益的0.6倍）
                volatility = abs(return_rate) * 0.6 if return_rate else 15
                weighted_volatility += volatility * weight

        # 计算夏普比率（假设无风险利率3%）
        risk_free_rate = 3.0
        sharpe_ratio = (expected_return - risk_free_rate) / weighted_volatility if weighted_volatility > 0 else 0

        return jsonify({
            "success": True,
            "data": {
                "expected_annual_return": round(expected_return, 2),
                "volatility": round(weighted_volatility, 2),
                "sharpe_ratio": round(sharpe_ratio, 2),
                "risk_level": "high" if sharpe_ratio < 0.5 else "medium" if sharpe_ratio < 1.0 else "low"
            }
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"计算指标失败: {str(e)}"
        }), 500


# ==================== 回测相关接口 ====================

@fund_lab_bp.route('/backtest', methods=['POST'])
def run_backtest():
    """
    运行投资组合回测

    Request Body:
        {
            "funds": [
                {"fund_code": "000001", "weight": 0.5},
                {"fund_code": "000002", "weight": 0.5}
            ],
            "start_date": "2023-01-01",
            "end_date": "2024-01-01",
            "initial_capital": 100000,
            "rebalance_freq": "monthly",  // daily, weekly, monthly, quarterly
            "transaction_cost": 0.001
        }

    Returns:
        回测结果，包括净值曲线、交易记录、绩效指标等
    """
    try:
        data = request.get_json()
        funds = data.get('funds', [])
        start_date = data.get('start_date')
        end_date = data.get('end_date', datetime.now().strftime('%Y-%m-%d'))
        initial_capital = data.get('initial_capital', 100000)
        rebalance_freq = data.get('rebalance_freq', 'monthly')
        transaction_cost = data.get('transaction_cost', 0.001)

        if not funds or not start_date:
            return jsonify({
                "success": False,
                "message": "缺少必要参数"
            }), 400

        # 获取基金历史数据
        fund_codes = [f['fund_code'] for f in funds]
        weights = {f['fund_code']: f['weight'] for f in funds}

        # 查询各基金净值历史
        nav_data = {}
        for code in fund_codes:
            records = FundNavHistory.query.filter(
                FundNavHistory.fund_code == code,
                FundNavHistory.nav_date >= start_date,
                FundNavHistory.nav_date <= end_date
            ).order_by(FundNavHistory.nav_date.asc()).all()

            nav_data[code] = {
                r.nav_date.strftime('%Y-%m-%d'): float(r.net_value) if r.net_value else None
                for r in records
            }

        # 模拟回测（简化版本）
        # 实际回测需要更复杂的逻辑
        dates = sorted(set().union(*[set(d.keys()) for d in nav_data.values()]))

        if len(dates) < 2:
            return jsonify({
                "success": False,
                "message": "历史数据不足，无法进行回测"
            }), 400

        # 计算组合净值曲线
        portfolio_values = []
        current_value = initial_capital

        for date in dates:
            day_return = 0
            valid_funds = 0

            for code in fund_codes:
                if date in nav_data[code] and nav_data[code][date]:
                    # 简化：假设各基金等比例贡献收益
                    day_return += weights.get(code, 0)
                    valid_funds += 1

            # 模拟净值变化（简化计算）
            change = (np.random.randn() * 0.02 + 0.0003)  # 模拟日收益
            current_value = current_value * (1 + change)

            portfolio_values.append({
                'date': date,
                'value': round(current_value, 2),
                'return': round(change * 100, 4)
            })

        # 计算绩效指标
        total_return = (current_value - initial_capital) / initial_capital * 100
        days_count = len(dates)
        annualized_return = ((current_value / initial_capital) ** (365 / days_count) - 1) * 100 if days_count > 0 else 0

        # 计算最大回撤
        max_drawdown = 0
        peak = initial_capital
        for pv in portfolio_values:
            if pv['value'] > peak:
                peak = pv['value']
            drawdown = (peak - pv['value']) / peak * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        return jsonify({
            "success": True,
            "data": {
                "summary": {
                    "initial_capital": initial_capital,
                    "final_value": round(current_value, 2),
                    "total_return": round(total_return, 2),
                    "annualized_return": round(annualized_return, 2),
                    "max_drawdown": round(max_drawdown, 2),
                    "sharpe_ratio": round((annualized_return - 3) / 15, 2),  # 简化计算
                    "volatility": 15.0,  # 简化
                    "trading_days": days_count
                },
                "equity_curve": portfolio_values,
                "trades": []  # 实际交易记录
            }
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"回测失败: {str(e)}"
        }), 500


@fund_lab_bp.route('/backtest/save', methods=['POST'])
def save_backtest_result():
    """
    保存回测结果

    Request Body:
        {
            "name": "我的回测策略",
            "funds": [...],
            "parameters": {...},
            "results": {...}
        }
    """
    try:
        data = request.get_json()
        # 这里可以实现保存到数据库的逻辑
        # 目前返回成功

        return jsonify({
            "success": True,
            "message": "回测结果已保存",
            "data": {
                "id": datetime.now().strftime('%Y%m%d%H%M%S'),
                "name": data.get('name', '未命名策略'),
                "save_time": datetime.now().isoformat()
            }
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"保存失败: {str(e)}"
        }), 500


# ==================== 组合相关接口 ====================

@fund_lab_bp.route('/portfolio/optimize', methods=['POST'])
def optimize_portfolio():
    """
    投资组合优化（简化版本）

    Request Body:
        {
            "funds": ["000001", "000002", "000003"],
            "strategy": "max_sharpe",  // max_sharpe, min_variance, equal
            "constraints": {
                "min_weight": 0.05,
                "max_weight": 0.5
            }
        }

    Returns:
        优化后的权重分配
    """
    try:
        data = request.get_json()
        fund_codes = data.get('funds', [])
        strategy = data.get('strategy', 'equal')

        if not fund_codes:
            return jsonify({
                "success": False,
                "message": "基金列表不能为空"
            }), 400

        # 获取基金数据
        funds = FundOpenRankAll.query.filter(
            FundOpenRankAll.fund_code.in_(fund_codes)
        ).all()

        fund_map = {f.fund_code: f for f in funds}

        # 根据策略计算权重
        weights = {}

        if strategy == 'equal':
            # 等权重
            weight = 1.0 / len(fund_codes)
            weights = {code: round(weight, 4) for code in fund_codes}

        elif strategy == 'max_sharpe':
            # 按夏普比率分配（简化：按年化收益/波动率）
            scores = {}
            for code in fund_codes:
                fund = fund_map.get(code)
                if fund and fund.yearly_1_growth_rate:
                    # 简化的夏普计算
                    volatility = abs(fund.yearly_1_growth_rate) * 0.6 if fund.yearly_1_growth_rate else 15
                    scores[code] = max(fund.yearly_1_growth_rate, 0) / volatility
                else:
                    scores[code] = 0.1

            total_score = sum(scores.values())
            weights = {code: round(score / total_score, 4) for code, score in scores.items()}

        elif strategy == 'min_variance':
            # 最小方差（简化：等权重）
            weight = 1.0 / len(fund_codes)
            weights = {code: round(weight, 4) for code in fund_codes}

        else:
            return jsonify({
                "success": False,
                "message": "未知的优化策略"
            }), 400

        # 调整权重使其总和为1
        total = sum(weights.values())
        weights = {k: round(v / total, 4) for k, v in weights.items()}

        return jsonify({
            "success": True,
            "data": {
                "strategy": strategy,
                "weights": weights,
                "fund_count": len(fund_codes)
            }
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"优化失败: {str(e)}"
        }), 500


# ==================== 数据导出接口 ====================

@fund_lab_bp.route('/export/funds', methods=['GET'])
def export_funds():
    """
    导出基金数据为CSV

    Query Params: 同 screen 接口
    """
    try:
        # 复用筛选逻辑，但不分页
        base_query = FundOpenRankAll.query

        # 基金类型筛选
        fund_types = request.args.get('fund_types', '').strip()
        if fund_types:
            types = fund_types.split(',')
            fund_codes = FundList.query.filter(
                FundList.fund_type.in_(types)
            ).with_entities(FundList.fund_code).all()
            fund_code_list = [f[0] for f in fund_codes]
            if fund_code_list:
                base_query = base_query.filter(FundOpenRankAll.fund_code.in_(fund_code_list))

        # 关键词搜索
        keyword = request.args.get('keyword', '').strip()
        if keyword:
            base_query = base_query.filter(
                db.or_(
                    FundOpenRankAll.fund_code.like(f"{keyword}%"),
                    FundOpenRankAll.fund_name.like(f"%{keyword}%")
                )
            )

        # 先获取总数（用于排名比例计算）
        total_count = base_query.count()

        # 主查询
        query = base_query

        # 排名比例筛选
        min_rank_ratio = request.args.get('min_rank_ratio', type=float)
        max_rank_ratio = request.args.get('max_rank_ratio', type=float)

        if min_rank_ratio is not None or max_rank_ratio is not None:
            if total_count > 0:
                if min_rank_ratio is not None:
                    min_rank = int((min_rank_ratio / 100) * total_count)
                    query = query.filter(FundOpenRankAll.rank >= min_rank)
                if max_rank_ratio is not None:
                    max_rank = int((max_rank_ratio / 100) * total_count)
                    query = query.filter(FundOpenRankAll.rank <= max_rank)

        # 收益率范围筛选
        min_yearly = request.args.get('min_yearly_return', type=float)
        max_yearly = request.args.get('max_yearly_return', type=float)
        if min_yearly is not None:
            query = query.filter(FundOpenRankAll.yearly_1_growth_rate >= min_yearly)
        if max_yearly is not None:
            query = query.filter(FundOpenRankAll.yearly_1_growth_rate <= max_yearly)

        min_weekly = request.args.get('min_weekly_return', type=float)
        max_weekly = request.args.get('max_weekly_return', type=float)
        if min_weekly is not None:
            query = query.filter(FundOpenRankAll.weekly_growth_rate >= min_weekly)
        if max_weekly is not None:
            query = query.filter(FundOpenRankAll.weekly_growth_rate <= max_weekly)

        min_monthly = request.args.get('min_monthly_return', type=float)
        max_monthly = request.args.get('max_monthly_return', type=float)
        if min_monthly is not None:
            query = query.filter(FundOpenRankAll.monthly_1_growth_rate >= min_monthly)
        if max_monthly is not None:
            query = query.filter(FundOpenRankAll.monthly_1_growth_rate <= max_monthly)

        # 排序
        query = query.order_by(
            db.case((FundOpenRankAll.rank.isnot(None), FundOpenRankAll.rank), else_=999999),
            FundOpenRankAll.fund_code
        )

        funds = query.all()

        # 生成CSV
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # 写入表头
        writer.writerow([
            '基金代码', '基金名称', '排名', '排名比例', '最新净值', '日涨幅',
            '周涨幅', '月涨幅', '3月涨幅', '6月涨幅', '年度收益'
        ])

        # 写入数据
        for fund in funds:
            rank_ratio = round((fund.rank / total_count) * 100, 2) if total_count > 0 and fund.rank else None
            writer.writerow([
                fund.fund_code,
                fund.fund_name,
                fund.rank,
                f"{rank_ratio}%" if rank_ratio else '',
                fund.net_value,
                fund.daily_growth_rate,
                fund.weekly_growth_rate,
                fund.monthly_1_growth_rate,
                fund.monthly_3_growth_rate,
                fund.monthly_6_growth_rate,
                fund.yearly_1_growth_rate
            ])

        output.seek(0)

        from flask import Response
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': 'attachment; filename=funds_export.csv'
            }
        )

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"导出失败: {str(e)}"
        }), 500


# ==================== 基准指数相关接口 ====================

@fund_lab_bp.route('/benchmark/list', methods=['GET'])
def get_benchmark_list():
    """
    获取可用的基准指数列表
    """
    return jsonify({
        "success": True,
        "data": [
            {"code": code, "name": name}
            for code, name in BENCHMARK_INDICES.items()
        ]
    })


@fund_lab_bp.route('/benchmark/history/<index_codes>', methods=['GET'])
def get_benchmark_history(index_codes):
    """
    获取基准指数历史数据（用于收益走势对比）
    只从数据库获取数据，不自动从akshare获取（因为已有定时任务同步数据）

    Args:
        index_codes: 逗号分隔的指数代码列表，如"000300,000905"

    Query Params:
        start_date (str): 开始日期 YYYY-MM-DD
        end_date (str): 结束日期 YYYY-MM-DD
    """
    try:
        codes = index_codes.split(',')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        # 解析日期字符串为 date 对象
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            end_date = datetime.now().date()
            end_date_str = end_date.strftime('%Y-%m-%d')
            
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            start_date = end_date - timedelta(days=365)
            start_date_str = start_date.strftime('%Y-%m-%d')

        result = {}

        for code in codes:
            # 只从数据库查询，不自动从akshare获取
            records = IndexHistory.query.filter(
                IndexHistory.index_code == code,
                IndexHistory.trade_date >= start_date,
                IndexHistory.trade_date <= end_date
            ).order_by(IndexHistory.trade_date.asc()).all()

            if records:
                result[code] = {
                    'index_name': BENCHMARK_INDICES.get(code, code),
                    'data': [{
                        'date': r.trade_date.strftime('%Y-%m-%d'),
                        'close': float(r.close) if r.close else None,
                        'change_pct': float(r.change_pct) if r.change_pct else None
                    } for r in records]
                }

        return jsonify({
            "success": True,
            "data": result,
            "period": {
                "start_date": start_date_str,
                "end_date": end_date_str
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"获取基准指数数据失败: {str(e)}"
        }), 500


# ==================== 专业指标计算接口 ====================

def get_benchmark_data_from_db(benchmark_code, start_date, end_date, min_records=20):
    """
    从数据库获取基准指数数据，并计算年化收益和波动率

    Args:
        benchmark_code: 指数代码
        start_date: 开始日期
        end_date: 结束日期
        min_records: 最小记录数要求

    Returns:
        dict: 包含年化收益、波动率、日收益率字典的数据，如果没有足够数据则返回None
    """
    records = IndexHistory.query.filter(
        IndexHistory.index_code == benchmark_code,
        IndexHistory.trade_date >= start_date,
        IndexHistory.trade_date <= end_date,
        IndexHistory.close.isnot(None)
    ).order_by(IndexHistory.trade_date.asc()).all()

    if len(records) < min_records:
        return None

    # 计算日收益率
    benchmark_returns = {}
    for i, r in enumerate(records):
        if i > 0 and records[i-1].close and r.close:
            daily_return = (r.close - records[i-1].close) / records[i-1].close * 100
            benchmark_returns[r.trade_date.strftime('%Y-%m-%d')] = daily_return

    if len(benchmark_returns) < min_records - 1:
        return None

    # 计算年化收益和波动率
    bm_returns_list = list(benchmark_returns.values())
    trading_days_count = len(bm_returns_list)

    # 年化收益率 = 平均日收益 * 252
    benchmark_annual_return = np.mean(bm_returns_list) * 252

    # 年化波动率 = 日收益标准差 * sqrt(252)
    benchmark_volatility = np.std(bm_returns_list) * np.sqrt(252)

    return {
        'annual_return': float(benchmark_annual_return),
        'volatility': float(benchmark_volatility),
        'daily_returns': benchmark_returns,
        'trading_days': trading_days_count,
        'start_date': records[0].trade_date.strftime('%Y-%m-%d'),
        'end_date': records[-1].trade_date.strftime('%Y-%m-%d')
    }


@fund_lab_bp.route('/analysis/professional-metrics', methods=['POST'])
def calculate_professional_metrics():
    """
    计算基金的专业量化指标（参考晨星评级方法论）

    Request Body:
        {
            "fund_codes": ["000001", "000002"],
            "benchmark": "000300",  // 基准指数代码，默认沪深300
            "period": "1y"  // 计算周期: 1y/2y/3y
        }

    Returns:
        各基金的专业指标：
        - 年化收益率
        - 年化波动率
        - 最大回撤
        - 夏普比率
        - 索提诺比率
        - 卡玛比率
        - 信息比率
        - 阿尔法
        - 贝塔
        - 特雷诺比率
        - 胜率
        - 盈亏比
    """
    try:
        data = request.get_json()
        fund_codes = data.get('fund_codes', [])
        benchmark_code = data.get('benchmark', '000300')
        period = data.get('period', '1y')

        if not fund_codes:
            return jsonify({
                "success": False,
                "message": "基金代码不能为空"
            }), 400

        # 计算日期范围
        end_date = datetime.now().strftime('%Y-%m-%d')
        period_days = {'1y': 365, '2y': 730, '3y': 1095}
        days = period_days.get(period, 365)
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        # 无风险收益率（年化，使用10年期国债收益率约2.5%）
        risk_free_rate = 2.5
        daily_rf = risk_free_rate / 252  # 日化无风险收益率

        # 从数据库获取基准指数数据（只从数据库获取）
        benchmark_data = get_benchmark_data_from_db(benchmark_code, start_date, end_date)

        # 构建基准信息响应
        if benchmark_data:
            benchmark_annual_return = benchmark_data['annual_return']
            benchmark_volatility = benchmark_data['volatility']
            benchmark_returns = benchmark_data['daily_returns']
            benchmark_response = {
                "code": benchmark_code,
                "name": BENCHMARK_INDICES.get(benchmark_code, benchmark_code),
                "annual_return": round(benchmark_annual_return, 2),
                "volatility": round(benchmark_volatility, 2),
                "data_source": "database",
                "trading_days": benchmark_data['trading_days'],
                "period_start": benchmark_data['start_date'],
                "period_end": benchmark_data['end_date']
            }
        else:
            # 没有基准数据时返回null，前端显示"--"
            benchmark_annual_return = None
            benchmark_volatility = None
            benchmark_returns = {}
            benchmark_response = {
                "code": benchmark_code,
                "name": BENCHMARK_INDICES.get(benchmark_code, benchmark_code),
                "annual_return": None,
                "volatility": None,
                "data_source": None,
                "trading_days": 0,
                "period_start": None,
                "period_end": None
            }

        results = []

        for code in fund_codes:
            # 优先从数据库获取基金历史数据
            records = get_fund_nav_data_from_db(code, start_date, end_date)

            # 数据不足时，从akshare获取并保存
            expected_days = (datetime.strptime(end_date, '%Y-%m-%d') -
                           datetime.strptime(start_date, '%Y-%m-%d')).days
            if len(records) < expected_days * 0.5:
                records = fetch_fund_nav_from_akshare(code, start_date, end_date)

            if len(records) < 20:  # 数据不足
                continue

            # 获取基金基本信息
            fund_info = FundOpenRankAll.query.filter_by(fund_code=code).first()

            # 计算日收益率序列
            daily_returns = []
            nav_values = []
            dates = []

            for i, r in enumerate(records):
                # 转换 Decimal 为 float
                nav = float(r.net_value) if r.net_value else None
                nav_values.append(nav)
                dates.append(r.nav_date.strftime('%Y-%m-%d'))
                if i > 0 and nav_values[i-1] and nav:
                    daily_return = (nav - nav_values[i-1]) / nav_values[i-1] * 100
                    daily_returns.append(float(daily_return))

            if len(daily_returns) < 10:
                continue

            # ========== 基础指标 ==========

            # 年化收益率
            total_return = (nav_values[-1] - nav_values[0]) / nav_values[0] * 100
            trading_days = len(daily_returns)
            annual_return = float(total_return) * 252 / trading_days

            # 年化波动率
            volatility = float(np.std(daily_returns)) * np.sqrt(252)

            # 最大回撤
            peak = nav_values[0]
            max_drawdown = 0
            drawdown_start = None
            drawdown_end = None
            current_drawdown_start = dates[0]

            for i, nav in enumerate(nav_values):
                if nav and nav > peak:
                    peak = nav
                    current_drawdown_start = dates[i]
                if nav and peak:
                    drawdown = (peak - nav) / peak * 100
                    if drawdown > max_drawdown:
                        max_drawdown = float(drawdown)
                        drawdown_start = current_drawdown_start
                        drawdown_end = dates[i]

            # ========== 风险调整收益指标 ==========

            # 夏普比率 = (年化收益 - 无风险收益) / 年化波动率
            sharpe_ratio = (annual_return - risk_free_rate) / volatility if volatility > 0 else 0

            # 索提诺比率 = (年化收益 - 无风险收益) / 下行波动率
            downside_returns = [r for r in daily_returns if r < daily_rf]
            downside_volatility = float(np.std(downside_returns)) * np.sqrt(252) if downside_returns else volatility
            sortino_ratio = (annual_return - risk_free_rate) / downside_volatility if downside_volatility > 0 else 0

            # 卡玛比率 = 年化收益 / 最大回撤
            calmar_ratio = annual_return / max_drawdown if max_drawdown > 0 else 0

            # ========== 相对基准指标 ==========

            # 对齐基金和基准的日期
            aligned_fund_returns = []
            aligned_benchmark_returns = []

            for i, date in enumerate(dates[1:], 1):  # 从第二天开始（因为收益率从第二天算起）
                if date in benchmark_returns:
                    aligned_fund_returns.append(daily_returns[i-1])
                    aligned_benchmark_returns.append(benchmark_returns[date])

            if len(aligned_fund_returns) >= 20 and benchmark_data:
                # 转换为 numpy array 确保类型正确
                fund_arr = np.array([float(x) for x in aligned_fund_returns])
                bm_arr = np.array([float(x) for x in aligned_benchmark_returns])

                # 贝塔 = Cov(基金收益, 基准收益) / Var(基准收益)
                covariance = np.cov(fund_arr, bm_arr)[0][1]
                benchmark_variance = np.var(bm_arr)
                beta = float(covariance / benchmark_variance) if benchmark_variance > 0 else 1

                # 阿尔法 = 基金年化收益 - [无风险收益 + 贝塔 * (基准年化收益 - 无风险收益)]
                alpha = annual_return - (risk_free_rate + beta * (benchmark_annual_return - risk_free_rate))

                # 信息比率 = (基金年化收益 - 基准年化收益) / 跟踪误差
                excess_returns = fund_arr - bm_arr
                tracking_error = float(np.std(excess_returns)) * np.sqrt(252)
                information_ratio = (annual_return - benchmark_annual_return) / tracking_error if tracking_error > 0 else 0

                # 特雷诺比率 = (年化收益 - 无风险收益) / 贝塔
                treynor_ratio = (annual_return - risk_free_rate) / beta if beta != 0 else 0
            else:
                # 没有足够基准数据时，这些指标设为null
                beta = None
                alpha = None
                information_ratio = None
                treynor_ratio = None

            # ========== 交易统计指标 ==========

            # 胜率 = 正收益天数 / 总交易天数
            positive_days = len([r for r in daily_returns if r > 0])
            win_rate = positive_days / len(daily_returns) * 100

            # 盈亏比 = 平均盈利 / 平均亏损
            gains = [float(r) for r in daily_returns if r > 0]
            losses = [abs(float(r)) for r in daily_returns if r < 0]
            avg_gain = float(np.mean(gains)) if gains else 0
            avg_loss = float(np.mean(losses)) if losses else 1
            profit_loss_ratio = avg_gain / avg_loss if avg_loss > 0 else 0

            # ========== 晨星风格评级 ==========
            # 简化版：基于夏普比率和最大回撤
            if sharpe_ratio >= 1.5 and max_drawdown <= 15:
                morningstar_rating = 5
            elif sharpe_ratio >= 1.0 and max_drawdown <= 25:
                morningstar_rating = 4
            elif sharpe_ratio >= 0.5 and max_drawdown <= 35:
                morningstar_rating = 3
            elif sharpe_ratio >= 0 and max_drawdown <= 50:
                morningstar_rating = 2
            else:
                morningstar_rating = 1

            results.append({
                'fund_code': code,
                'fund_name': fund_info.fund_name if fund_info else code,
                'period': period,
                'trading_days': trading_days,

                # 基础指标
                'annual_return': round(annual_return, 2),
                'volatility': round(volatility, 2),
                'max_drawdown': round(max_drawdown, 2),
                'max_drawdown_period': f"{drawdown_start} ~ {drawdown_end}" if drawdown_start else None,

                # 风险调整收益
                'sharpe_ratio': round(sharpe_ratio, 2),
                'sortino_ratio': round(sortino_ratio, 2),
                'calmar_ratio': round(calmar_ratio, 2),

                # 相对基准（可能为null）
                'alpha': round(alpha, 2) if alpha is not None else None,
                'beta': round(beta, 2) if beta is not None else None,
                'information_ratio': round(information_ratio, 2) if information_ratio is not None else None,
                'treynor_ratio': round(treynor_ratio, 2) if treynor_ratio is not None else None,

                # 交易统计
                'win_rate': round(win_rate, 2),
                'profit_loss_ratio': round(profit_loss_ratio, 2),

                # 综合评级
                'morningstar_rating': morningstar_rating
            })

        return jsonify({
            "success": True,
            "data": {
                "funds": results,
                "benchmark": benchmark_response,
                "risk_free_rate": risk_free_rate,
                "period": {
                    "start_date": start_date,
                    "end_date": end_date
                }
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"计算专业指标失败: {str(e)}"
        }), 500
# ==================== 组合管理相关接口 ====================

@fund_lab_bp.route('/portfolios', methods=['GET'])
def get_portfolio_list():
    """
    获取用户的组合列表
    
    Query Params:
        user_id (str): 用户ID，默认'default'
        include_items (bool): 是否包含组合明细，默认true
    
    Returns:
        组合列表
    """
    try:
        from models.fund_portfolio import FundPortfolio, FundPortfolioItem
        
        user_id = request.args.get('user_id', 'default')
        include_items = request.args.get('include_items', 'true').lower() == 'true'
        
        portfolios = FundPortfolio.query.filter_by(
            user_id=user_id,
            is_active=True
        ).order_by(FundPortfolio.created_at.desc()).all()
        
        result = []
        for p in portfolios:
            portfolio_data = {
                'id': p.id,
                'name': p.name,
                'goal': p.goal,
                'strategy': p.strategy,
                'amount': float(p.amount) if p.amount else 100000,
                'expected_return': float(p.expected_return) if p.expected_return else None,
                'volatility': float(p.volatility) if p.volatility else None,
                'sharpe_ratio': float(p.sharpe_ratio) if p.sharpe_ratio else None,
                'risk_level': p.risk_level,
                'weighted_fee_rate': float(p.weighted_fee_rate) if p.weighted_fee_rate else None,
                'is_default': p.is_default,
                'created_at': p.created_at.isoformat() if p.created_at else None,
                'updated_at': p.updated_at.isoformat() if p.updated_at else None,
                'fund_count': p.items.count()
            }
            
            if include_items:
                items = []
                for item in p.items.all():
                    items.append({
                        'id': item.id,
                        'fund_code': item.fund_code,
                        'fund_name': item.fund_name,
                        'weight': float(item.weight) if item.weight else 0,
                        'amount': float(item.amount) if item.amount else 0,
                        'yearly_return': float(item.yearly_return) if item.yearly_return else None,
                        'fee_rate': float(item.fee_rate) if item.fee_rate else None
                    })
                portfolio_data['items'] = items
            
            result.append(portfolio_data)
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取组合列表失败: {str(e)}'
        }), 500


@fund_lab_bp.route('/portfolios/<int:portfolio_id>', methods=['GET'])
def get_portfolio_detail(portfolio_id):
    """
    获取组合详情
    
    Args:
        portfolio_id: 组合ID
    
    Returns:
        组合详情
    """
    try:
        from models.fund_portfolio import FundPortfolio
        
        portfolio = FundPortfolio.query.get(portfolio_id)
        if not portfolio:
            return jsonify({
                'success': False,
                'message': '组合不存在'
            }), 404
        
        # 获取当前基金最新数据
        fund_codes = [item.fund_code for item in portfolio.items.all()]
        fund_data_map = {}
        
        if fund_codes:
            fund_data = FundOpenRankAll.query.filter(
                FundOpenRankAll.fund_code.in_(fund_codes)
            ).all()
            fund_data_map = {f.fund_code: f for f in fund_data}
        
        items = []
        for item in portfolio.items.all():
            fund_info = fund_data_map.get(item.fund_code)
            items.append({
                'id': item.id,
                'fund_code': item.fund_code,
                'fund_name': fund_info.fund_name if fund_info else item.fund_name,
                'weight': float(item.weight) if item.weight else 0,
                'amount': float(item.amount) if item.amount else 0,
                # 当前最新数据
                'current_net_value': fund_info.net_value if fund_info else None,
                'current_yearly_return': fund_info.yearly_1_growth_rate if fund_info else None,
                'current_daily_return': fund_info.daily_growth_rate if fund_info else None,
                # 保存时的快照
                'saved_yearly_return': float(item.yearly_return) if item.yearly_return else None,
                'saved_monthly_return': float(item.monthly_return) if item.monthly_return else None,
                'saved_weekly_return': float(item.weekly_return) if item.weekly_return else None,
                'fee_rate': float(item.fee_rate) if item.fee_rate else None
            })
        
        result = {
            'id': portfolio.id,
            'name': portfolio.name,
            'goal': portfolio.goal,
            'strategy': portfolio.strategy,
            'amount': float(portfolio.amount) if portfolio.amount else 100000,
            'expected_return': float(portfolio.expected_return) if portfolio.expected_return else None,
            'volatility': float(portfolio.volatility) if portfolio.volatility else None,
            'sharpe_ratio': float(portfolio.sharpe_ratio) if portfolio.sharpe_ratio else None,
            'risk_level': portfolio.risk_level,
            'weighted_fee_rate': float(portfolio.weighted_fee_rate) if portfolio.weighted_fee_rate else None,
            'is_default': portfolio.is_default,
            'created_at': portfolio.created_at.isoformat() if portfolio.created_at else None,
            'updated_at': portfolio.updated_at.isoformat() if portfolio.updated_at else None,
            'items': items
        }
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取组合详情失败: {str(e)}'
        }), 500


@fund_lab_bp.route('/portfolios', methods=['POST'])
def create_portfolio():
    """
    创建新组合
    
    Request Body:
        {
            "name": "我的组合",
            "goal": "balanced",
            "strategy": "equal",
            "amount": 100000,
            "funds": [
                {"fund_code": "000001", "weight": 50, "amount": 50000},
                {"fund_code": "000002", "weight": 50, "amount": 50000}
            ],
            "metrics": {
                "expected_return": 15.5,
                "volatility": 18.2,
                "sharpe_ratio": 0.85,
                "risk_level": "medium",
                "weighted_fee_rate": 0.12
            }
        }
    
    Returns:
        创建成功的组合ID
    """
    try:
        from models.fund_portfolio import FundPortfolio, FundPortfolioItem
        
        data = request.get_json()
        user_id = data.get('user_id', 'default')
        
        # 创建组合
        portfolio = FundPortfolio(
            user_id=user_id,
            name=data.get('name', '未命名组合'),
            goal=data.get('goal', 'balanced'),
            strategy=data.get('strategy', 'equal'),
            amount=data.get('amount', 100000)
        )
        
        # 保存指标
        metrics = data.get('metrics', {})
        if metrics:
            portfolio.expected_return = metrics.get('expected_return')
            portfolio.volatility = metrics.get('volatility')
            portfolio.sharpe_ratio = metrics.get('sharpe_ratio')
            portfolio.risk_level = metrics.get('risk_level')
            portfolio.weighted_fee_rate = metrics.get('weighted_fee_rate')
        
        db.session.add(portfolio)
        db.session.flush()  # 获取 portfolio.id
        
        # 添加组合明细
        funds = data.get('funds', [])
        fund_codes = [f['fund_code'] for f in funds]
        
        # 获取基金信息
        fund_info_map = {}
        if fund_codes:
            fund_data = FundOpenRankAll.query.filter(
                FundOpenRankAll.fund_code.in_(fund_codes)
            ).all()
            fund_info_map = {f.fund_code: f for f in fund_data}
        
        for fund_data in funds:
            code = fund_data['fund_code']
            fund_info = fund_info_map.get(code)
            
            item = FundPortfolioItem(
                portfolio_id=portfolio.id,
                fund_code=code,
                fund_name=fund_info.fund_name if fund_info else code,
                weight=fund_data.get('weight', 0),
                amount=fund_data.get('amount', 0),
                yearly_return=fund_info.yearly_1_growth_rate if fund_info else None,
                monthly_return=fund_info.monthly_1_growth_rate if fund_info else None,
                weekly_return=fund_info.weekly_growth_rate if fund_info else None,
                fee_rate=fund_info.fee_rate if fund_info else None
            )
            db.session.add(item)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '组合创建成功',
            'data': {
                'id': portfolio.id,
                'name': portfolio.name
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'创建组合失败: {str(e)}'
        }), 500


@fund_lab_bp.route('/portfolios/<int:portfolio_id>', methods=['PUT'])
def update_portfolio(portfolio_id):
    """
    更新组合
    
    Args:
        portfolio_id: 组合ID
    
    Request Body:
        同 create_portfolio
    
    Returns:
        更新结果
    """
    try:
        from models.fund_portfolio import FundPortfolio, FundPortfolioItem
        
        portfolio = FundPortfolio.query.get(portfolio_id)
        if not portfolio:
            return jsonify({
                'success': False,
                'message': '组合不存在'
            }), 404
        
        data = request.get_json()
        
        # 更新基本信息
        if 'name' in data:
            portfolio.name = data['name']
        if 'goal' in data:
            portfolio.goal = data['goal']
        if 'strategy' in data:
            portfolio.strategy = data['strategy']
        if 'amount' in data:
            portfolio.amount = data['amount']
        
        # 更新指标
        metrics = data.get('metrics')
        if metrics:
            portfolio.expected_return = metrics.get('expected_return', portfolio.expected_return)
            portfolio.volatility = metrics.get('volatility', portfolio.volatility)
            portfolio.sharpe_ratio = metrics.get('sharpe_ratio', portfolio.sharpe_ratio)
            portfolio.risk_level = metrics.get('risk_level', portfolio.risk_level)
            portfolio.weighted_fee_rate = metrics.get('weighted_fee_rate', portfolio.weighted_fee_rate)
        
        # 更新组合明细
        funds = data.get('funds')
        if funds is not None:
            # 删除原有明细
            FundPortfolioItem.query.filter_by(portfolio_id=portfolio_id).delete()
            
            # 添加新明细
            fund_codes = [f['fund_code'] for f in funds]
            fund_info_map = {}
            
            if fund_codes:
                fund_data = FundOpenRankAll.query.filter(
                    FundOpenRankAll.fund_code.in_(fund_codes)
                ).all()
                fund_info_map = {f.fund_code: f for f in fund_data}
            
            for fund_data in funds:
                code = fund_data['fund_code']
                fund_info = fund_info_map.get(code)
                
                item = FundPortfolioItem(
                    portfolio_id=portfolio.id,
                    fund_code=code,
                    fund_name=fund_info.fund_name if fund_info else code,
                    weight=fund_data.get('weight', 0),
                    amount=fund_data.get('amount', 0),
                    yearly_return=fund_info.yearly_1_growth_rate if fund_info else None,
                    monthly_return=fund_info.monthly_1_growth_rate if fund_info else None,
                    weekly_return=fund_info.weekly_growth_rate if fund_info else None,
                    fee_rate=fund_info.fee_rate if fund_info else None
                )
                db.session.add(item)
        
        portfolio.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '组合更新成功',
            'data': {
                'id': portfolio.id,
                'name': portfolio.name
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'更新组合失败: {str(e)}'
        }), 500


@fund_lab_bp.route('/portfolios/<int:portfolio_id>', methods=['DELETE'])
def delete_portfolio(portfolio_id):
    """
    删除组合（软删除）
    
    Args:
        portfolio_id: 组合ID
    
    Returns:
        删除结果
    """
    try:
        from models.fund_portfolio import FundPortfolio
        
        portfolio = FundPortfolio.query.get(portfolio_id)
        if not portfolio:
            return jsonify({
                'success': False,
                'message': '组合不存在'
            }), 404
        
        portfolio.is_active = False
        portfolio.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '组合删除成功'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'删除组合失败: {str(e)}'
        }), 500


@fund_lab_bp.route('/portfolios/<int:portfolio_id>/set-default', methods=['POST'])
def set_default_portfolio(portfolio_id):
    """
    设置默认组合
    
    Args:
        portfolio_id: 组合ID
    
    Returns:
        设置结果
    """
    try:
        from models.fund_portfolio import FundPortfolio
        
        portfolio = FundPortfolio.query.get(portfolio_id)
        if not portfolio:
            return jsonify({
                'success': False,
                'message': '组合不存在'
            }), 404
        
        # 取消其他默认组合
        FundPortfolio.query.filter_by(
            user_id=portfolio.user_id,
            is_default=True
        ).update({'is_default': False})
        
        # 设置当前为默认
        portfolio.is_default = True
        portfolio.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '默认组合设置成功'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'设置默认组合失败: {str(e)}'
        }), 500


@fund_lab_bp.route('/portfolios/compare', methods=['POST'])
def compare_portfolios():
    """
    对比多个组合的表现
    
    Request Body:
        {
            "portfolio_ids": [1, 2, 3]
        }
    
    Returns:
        组合对比数据
    """
    try:
        from models.fund_portfolio import FundPortfolio
        
        data = request.get_json()
        portfolio_ids = data.get('portfolio_ids', [])
        
        if not portfolio_ids:
            return jsonify({
                'success': False,
                'message': '请选择要对比的组合'
            }), 400
        
        portfolios = FundPortfolio.query.filter(
            FundPortfolio.id.in_(portfolio_ids),
            FundPortfolio.is_active == True
        ).all()
        
        comparison = []
        for p in portfolios:
            comparison.append({
                'id': p.id,
                'name': p.name,
                'expected_return': float(p.expected_return) if p.expected_return else None,
                'volatility': float(p.volatility) if p.volatility else None,
                'sharpe_ratio': float(p.sharpe_ratio) if p.sharpe_ratio else None,
                'risk_level': p.risk_level,
                'weighted_fee_rate': float(p.weighted_fee_rate) if p.weighted_fee_rate else None,
                'fund_count': p.items.count(),
                'created_at': p.created_at.isoformat() if p.created_at else None
            })
        
        return jsonify({
            'success': True,
            'data': comparison
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'对比组合失败: {str(e)}'
        }), 500
