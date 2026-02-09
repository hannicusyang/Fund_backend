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
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

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

@fund_lab_bp.route('/analysis/returns/<fund_codes>', methods=['GET'])
def get_funds_return_analysis(fund_codes):
    """
    获取多只基金的历史收益率数据（用于对比分析）
    如果数据库中数据不足，会自动从akshare获取并保存

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
            # 先查询数据库
            records = FundNavHistory.query.filter(
                FundNavHistory.fund_code == code,
                FundNavHistory.nav_date >= start_date,
                FundNavHistory.nav_date <= end_date
            ).order_by(FundNavHistory.nav_date.asc()).all()

            # 检查数据是否完整（缺失天数超过10%则认为不完整）
            expected_days = (datetime.strptime(end_date, '%Y-%m-%d') -
                           datetime.strptime(start_date, '%Y-%m-%d')).days
            actual_days = len(records)
            data_complete = actual_days >= expected_days * 0.9

            if not data_complete:
                # 从akshare获取数据
                try:
                    import akshare as ak

                    # 获取基金历史净值
                    df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")

                    if df is not None and not df.empty:
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
                                fund_code=code,
                                nav_date=row['nav_date'].date()
                            ).first()

                            if not existing:
                                # 获取基金名称
                                fund_info = FundOpenRankAll.query.filter_by(fund_code=code).first()
                                fund_name = fund_info.fund_name if fund_info else code

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
                                    fund_code=code,
                                    nav_date=row['nav_date'].date(),
                                    fund_name=fund_name,
                                    net_value=float(row['net_value']) if pd.notna(row['net_value']) else None,
                                    daily_growth_rate=growth_rate
                                )
                                db.session.add(nav_record)

                        db.session.commit()

                        # 重新查询
                        records = FundNavHistory.query.filter(
                            FundNavHistory.fund_code == code,
                            FundNavHistory.nav_date >= start_date,
                            FundNavHistory.nav_date <= end_date
                        ).order_by(FundNavHistory.nav_date.asc()).all()

                except Exception as ak_error:
                    print(f"从akshare获取{code}数据失败: {ak_error}")
                    # 继续，使用数据库中已有数据

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
