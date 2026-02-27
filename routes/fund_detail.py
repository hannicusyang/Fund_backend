# routes/fund_rank.py
# 导入tushare
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.tushare_api import get_pro

from datetime import datetime
from config import logger
from flask import Blueprint, request, jsonify
from models import db, FundHolding,FundNavHistory
from models.fund_open_rank import FundOpenRankAll
import  akshare as ak
import pandas as pd
fund_detail_bp = Blueprint('fund_detail', __name__)


@fund_detail_bp.route('/detail/<fund_code>', methods=['GET'])
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


def get_latest_quarter_for_date(target_date=None):
    """
    根据当前日期确定应该查询哪个季度的持仓数据

    Args:
        target_date (datetime): 目标日期，默认为当前日期

    Returns:
        tuple: (year_str, quarter_str) 例如 ("2024", "2024年1季度股票投资明细")
    """
    if target_date is None:
        target_date = datetime.now()

    current_year = target_date.year
    current_month = target_date.month

    if current_month in [1, 2, 3]:
        # 1-3月：查询上一年Q4
        query_year = current_year - 1
        quarter_display = f"{query_year}年4季度股票投资明细"
    elif current_month in [4, 5, 6]:
        # 4-6月：查询当年Q1
        query_year = current_year
        quarter_display = f"{query_year}年1季度股票投资明细"
    elif current_month in [7, 8, 9]:
        # 7-9月：查询当年Q2
        query_year = current_year
        quarter_display = f"{query_year}年2季度股票投资明细"
    else:  # 10, 11, 12
        # 10-12月：查询当年Q3
        query_year = current_year
        quarter_display = f"{query_year}年3季度股票投资明细"

    return str(query_year), quarter_display


@fund_detail_bp.route('/detail/holdings/<fund_code>/', methods=['GET'])
def get_fund_holdings(fund_code):
    """
    获取基金最新持仓信息（根据当前时间自动选择正确的季度）
    先从数据库查询，查不到则调用akshare接口获取并保存

    Query Parameters:
        year (str, optional): 指定年份，如果不提供则使用最新季度逻辑
        force_refresh (bool, optional): 是否强制刷新数据，默认False

    Returns:
        JSON: 基金持仓数据列表
    """
    try:
        # 检查是否强制刷新
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'

        # 如果提供了year参数，则使用指定年份的最新季度逻辑
        if 'year' in request.args:
            try:
                specified_year = int(request.args.get('year'))
                current_month = datetime.now().month

                if current_month in [1, 2, 3] and specified_year == datetime.now().year:
                    # 若是在1-3月且请求年份于当年相同，则自动请求上一年4季度
                    query_year = specified_year -1
                    quarter_display = f"{query_year}年4季度股票投资明细"
                elif current_month in [1, 2, 3] and specified_year != datetime.now().year:
                    # 1-3月：查询指定年份的Q4
                    query_year = specified_year
                    quarter_display = f"{specified_year}年4季度股票投资明细"
                else:
                    # 其他月份：查询指定年份的上一季度
                    current_month = datetime.now().month
                    if current_month in [4, 5, 6]:
                        quarter_num = 1
                    elif current_month in [7, 8, 9]:
                        quarter_num = 2
                    else:  # 10, 11, 12
                        quarter_num = 3
                    query_year = specified_year
                    quarter_display = f"{specified_year}年{quarter_num}季度股票投资明细"

            except ValueError:
                return jsonify({
                    'success': False,
                    'message': '年份参数必须为数字'
                }), 400
        else:
            # 使用当前时间的最新季度逻辑
            query_year, quarter_display = get_latest_quarter_for_date()

        # 如果不是强制刷新，先从数据库查询
        if not force_refresh:
            existing_holdings = FundHolding.query.filter_by(
                fund_code=fund_code,
                quarter=quarter_display
            ).all()

            if existing_holdings:
                result = [holding.to_dict() for holding in existing_holdings]
                return jsonify({
                    'success': True,
                    'data': result,
                    'source': 'database',
                    'quarter': quarter_display
                })

        # 数据库中没有数据或强制刷新，调用akshare接口
        try:
            logger.info(f"从akshare获取基金 {fund_code} {query_year} 年持仓数据")
            df = ak.fund_portfolio_hold_em(symbol=fund_code, date=query_year)

            # 从返回的数据中找到匹配的季度
            matching_quarter_data = df[df['季度'] == quarter_display] if '季度' in df.columns else pd.DataFrame()

            if matching_quarter_data.empty:
                # 如果指定季度没有数据，尝试找该年份最新的季度数据
                available_quarters = df['季度'].unique() if '季度' in df.columns else []
                if len(available_quarters) > 0:
                    # 取最新的季度（按字符串排序，通常能正确排序）
                    latest_quarter = sorted(available_quarters, reverse=True)[0]
                    matching_quarter_data = df[df['季度'] == latest_quarter]
                    quarter_display = latest_quarter
                    logger.info(f"未找到指定季度数据，使用最新季度: {latest_quarter}")
                else:
                    return jsonify({
                        'success': True,
                        'data': [],
                        'message': f'未找到 {quarter_display} 的持仓数据',
                        'source': 'akshare',
                        'quarter': quarter_display
                    })

            # 处理数据并保存到数据库
            holdings_to_save = []
            current_date = datetime.now().date()

            for _, row in matching_quarter_data.iterrows():
                proportion_of_nav = float(row['占净值比例']) if pd.notna(row['占净值比例']) else None
                shares_held = float(row['持股数']) if pd.notna(row['持股数']) else None
                market_value = float(row['持仓市值']) if pd.notna(row['持仓市值']) else None

                holding = FundHolding(
                    fund_code=fund_code,
                    stock_code=str(row['股票代码']),
                    stock_name=str(row['股票名称']),
                    proportion_of_nav=proportion_of_nav,
                    shares_held=shares_held,
                    market_value=market_value,
                    quarter=str(row['季度']),
                    report_date=current_date
                )
                holdings_to_save.append(holding)

            # 删除该基金该季度的旧数据（避免重复）
            FundHolding.query.filter_by(
                fund_code=fund_code,
                quarter=quarter_display
            ).delete()

            # 批量保存新数据
            db.session.add_all(holdings_to_save)
            db.session.commit()

            # 返回数据
            result = [holding.to_dict() for holding in holdings_to_save]
            return jsonify({
                'success': True,
                'data': result,
                'source': 'akshare',
                'quarter': quarter_display,
                'message': f'成功获取{len(result)}条持仓记录'
            })

        except Exception as ak_error:
            logger.error(f"调用akshare接口失败: {str(ak_error)}")
            db.session.rollback()
            return jsonify({
                'success': False,
                'message': f'获取基金持仓数据失败: {str(ak_error)}'
            }), 500

    except Exception as e:
        logger.error(f"获取基金持仓数据发生错误: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': '服务器内部错误'
        }), 500


@fund_detail_bp.route('/detail/holdings/<fund_code>/holdings/quarterlist', methods=['GET'])
def get_fund_available_quarters(fund_code):
    """获取基金可用的季度列表"""
    try:
        quarters = db.session.query(FundHolding.quarter) \
            .filter(FundHolding.fund_code == fund_code) \
            .distinct() \
            .order_by(FundHolding.quarter.desc()) \
            .all()

        quarter_list = [q[0] for q in quarters]
        return jsonify({
            'success': True,
            'data': quarter_list
        })
    except Exception as e:
        logger.error(f"获取基金季度列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取季度列表失败'
        }), 500


@fund_detail_bp.route('/detail/holdings/<fund_code>/holdings/<quarter>', methods=['GET'])
def get_fund_holdings_by_quarter(fund_code, quarter):
    """根据指定季度获取基金持仓信息"""
    try:
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'

        if not force_refresh:
            existing_holdings = FundHolding.query.filter_by(
                fund_code=fund_code,
                quarter=quarter
            ).all()

            if existing_holdings:
                result = [holding.to_dict() for holding in existing_holdings]
                return jsonify({
                    'success': True,
                    'data': result,
                    'source': 'database'
                })

        # 解析季度中的年份
        try:
            year = quarter.split('年')[0]
            int(year)

            df = ak.fund_portfolio_hold_em(symbol=fund_code, date=year)
            matching_data = df[df['季度'] == quarter] if '季度' in df.columns else pd.DataFrame()

            if matching_data.empty:
                return jsonify({
                    'success': True,
                    'data': [],
                    'message': '未找到指定季度的持仓数据'
                })

            # 保存数据
            holdings_to_save = []
            current_date = datetime.now().date()

            for _, row in matching_data.iterrows():
                proportion_of_nav = float(row['占净值比例']) if pd.notna(row['占净值比例']) else None
                shares_held = float(row['持股数']) if pd.notna(row['持股数']) else None
                market_value = float(row['持仓市值']) if pd.notna(row['持仓市值']) else None

                holding = FundHolding(
                    fund_code=fund_code,
                    stock_code=str(row['股票代码']),
                    stock_name=str(row['股票名称']),
                    proportion_of_nav=proportion_of_nav,
                    shares_held=shares_held,
                    market_value=market_value,
                    quarter=str(row['季度']),
                    report_date=current_date
                )
                holdings_to_save.append(holding)

            # 删除旧数据并保存新数据
            FundHolding.query.filter_by(fund_code=fund_code, quarter=quarter).delete()
            db.session.add_all(holdings_to_save)
            db.session.commit()

            result = [holding.to_dict() for holding in holdings_to_save]
            return jsonify({
                'success': True,
                'data': result,
                'source': 'akshare'
            })

        except (ValueError, IndexError):
            return jsonify({
                'success': False,
                'message': '季度格式无效'
            }), 400

    except Exception as e:
        logger.error(f"获取指定季度基金持仓数据失败: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': '服务器内部错误'
        }), 500


@fund_detail_bp.route('/detail/holdings/latest-quarter-info', methods=['GET'])
def get_latest_quarter_info():
    """
    获取当前应该显示的最新季度信息（用于前端显示）
    """
    try:
        _, quarter_display = get_latest_quarter_for_date()
        current_date = datetime.now()

        return jsonify({
            'success': True,
            'data': {
                'quarter': quarter_display,
                'current_date': current_date.strftime('%Y-%m-%d'),
                'current_month': current_date.month
            }
        })
    except Exception as e:
        logger.error(f"获取最新季度信息失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取季度信息失败'
        }), 500


@fund_detail_bp.route('/detail/moving-averages/<fund_code>', methods=['GET'])
def get_fund_moving_averages(fund_code):
    """
    获取基金的历史净值和移动平均线数据（5日、10日、30日）

    Args:
        fund_code (str): 基金代码

    Query Parameters:
        start_date (str, optional): 开始日期，格式 YYYY-MM-DD
        end_date (str, optional): 结束日期，格式 YYYY-MM-DD
        include_latest_only (bool, optional): 是否只返回最新一条记录，默认False

    Returns:
        JSON: 包含基金名称、基金代码、当前均线值和所有历史数据
    """
    try:
        # 获取查询参数
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        include_latest_only = request.args.get('include_latest_only', 'false').lower() == 'true'

        # 验证基金代码
        if not fund_code or not fund_code.strip():
            return jsonify({
                'success': False,
                'message': '基金代码不能为空'
            }), 400

        fund_code = fund_code.strip()

        # 查询基金基本信息和净值数据
        query = db.session.query(
            FundNavHistory.nav_date,
            FundNavHistory.net_value,
            FundNavHistory.fund_name,
            FundNavHistory.daily_growth_rate
        ).filter(
            FundNavHistory.fund_code == fund_code,
            FundNavHistory.net_value.isnot(None)
        ).order_by(FundNavHistory.nav_date.asc())

        # 应用日期过滤
        if start_date:
            query = query.filter(FundNavHistory.nav_date >= start_date)
        if end_date:
            query = query.filter(FundNavHistory.nav_date <= end_date)

        results = query.all()

        if not results:
            return jsonify({
                'success': True,
                'message': '未找到该基金的净值数据',
                'fund_code': fund_code,
                'fund_name': '',
                'current_ma5': None,
                'current_ma10': None,
                'current_ma30': None,
                'data': []
            })

        # 转换为DataFrame进行计算
        df = pd.DataFrame([
            {
                'nav_date': r.nav_date.strftime('%Y-%m-%d'),
                'net_value': float(r.net_value),
                'daily_growth_rate': float(r.daily_growth_rate) if r.daily_growth_rate else None,
                'fund_name': r.fund_name
            }
            for r in results
        ])

        # 按日期排序确保正确性
        df = df.sort_values('nav_date').reset_index(drop=True)

        # 计算移动平均线
        df['ma5'] = df['net_value'].rolling(window=5, min_periods=1).mean()
        df['ma10'] = df['net_value'].rolling(window=10, min_periods=1).mean()
        df['ma30'] = df['net_value'].rolling(window=30, min_periods=1).mean()

        # 获取最新的均线值
        latest_record = df.iloc[-1]
        current_ma5 = float(latest_record['ma5']) if pd.notna(latest_record['ma5']) else None
        current_ma10 = float(latest_record['ma10']) if pd.notna(latest_record['ma10']) else None
        current_ma30 = float(latest_record['ma30']) if pd.notna(latest_record['ma30']) else None

        # 准备返回的数据
        if include_latest_only:
            # 只返回最新一条记录
            data_list = [df.iloc[-1].to_dict()]
        else:
            # 返回所有历史数据
            data_list = df.to_dict('records')

        # 清理NaN值
        for record in data_list:
            for key in ['ma5', 'ma10', 'ma30', 'daily_growth_rate']:
                if pd.isna(record[key]):
                    record[key] = None

        return jsonify({
            'success': True,
            'message': '获取成功',
            'fund_code': fund_code,
            'fund_name': results[0].fund_name,
            'current_ma5': current_ma5,
            'current_ma10': current_ma10,
            'current_ma30': current_ma30,
            'data': data_list
        })

    except Exception as e:
        logger.error(f"获取基金均线数据失败 {fund_code}: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'服务器内部错误: {str(e)}'
        }), 500


@fund_detail_bp.route('/detail/current-moving-averages/<fund_code>', methods=['GET'])
def get_fund_current_moving_averages(fund_code):
    """
    获取基金当前的移动平均线值（仅返回最新值，不包含历史数据）

    Args:
        fund_code (str): 基金代码

    Returns:
        JSON: 包含基金名称、基金代码和当前三种均线值
    """
    try:
        if not fund_code or not fund_code.strip():
            return jsonify({
                'success': False,
                'message': '基金代码不能为空'
            }), 400

        fund_code = fund_code.strip()

        # 查询最近30天的数据（足够计算所有均线）
        query = db.session.query(
            FundNavHistory.nav_date,
            FundNavHistory.net_value,
            FundNavHistory.fund_name
        ).filter(
            FundNavHistory.fund_code == fund_code,
            FundNavHistory.net_value.isnot(None)
        ).order_by(FundNavHistory.nav_date.desc()).limit(60)  # 获取60天确保有足够数据

        results = query.all()

        if not results:
            return jsonify({
                'success': True,
                'message': '未找到该基金的净值数据',
                'fund_code': fund_code,
                'fund_name': '',
                'current_ma5': None,
                'current_ma10': None,
                'current_ma30': None
            })

        # 转换为DataFrame并按日期排序
        df = pd.DataFrame([
            {
                'nav_date': r.nav_date,
                'net_value': float(r.net_value),
                'fund_name': r.fund_name
            }
            for r in results
        ])
        df = df.sort_values('nav_date').reset_index(drop=True)

        # 计算移动平均线
        ma5 = df['net_value'].tail(5).mean() if len(df) >= 5 else df['net_value'].mean()
        ma10 = df['net_value'].tail(10).mean() if len(df) >= 10 else df['net_value'].mean()
        ma30 = df['net_value'].tail(30).mean() if len(df) >= 30 else df['net_value'].mean()

        return jsonify({
            'success': True,
            'message': '获取成功',
            'fund_code': fund_code,
            'fund_name': results[0].fund_name,
            'current_ma5': float(ma5),
            'current_ma10': float(ma10),
            'current_ma30': float(ma30)
        })

    except Exception as e:
        logger.error(f"获取基金当前均线值失败 {fund_code}: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'服务器内部错误: {str(e)}'
        }), 500


