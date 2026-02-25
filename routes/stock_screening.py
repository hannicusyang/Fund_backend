# routes/stock_screening.py
# 多因子选股API接口 - 完整版
# 从数据库读取预同步的数据，支持全部因子筛选

from flask import Blueprint, request, jsonify
from models import db
from models.stock_screening import StockScreeningData
from sqlalchemy import or_, and_
from datetime import datetime
import time

stock_screening_bp = Blueprint('stock_screening', __name__)


def get_timestamp():
    return int(time.time())


def parse_range(value_str, default='0,100'):
    """解析区间字符串"""
    try:
        parts = str(value_str).split(',')
        if len(parts) == 2:
            return [float(parts[0]), float(parts[1])]
        return list(map(float, default.split(',')))
    except:
        return [0, 100]


@stock_screening_bp.route('/api/stock/screen', methods=['POST', 'GET'])
def screen_stocks():
    """多因子选股接口 - 支持所有因子"""
    try:
        if request.method == 'POST':
            params = request.json or {}
        else:
            params = request.args.to_dict()
        
        # 支持前端嵌套的filters格式: {filters: {valuation_pe: [0,10], ...}}
        print(f"[DEBUG] 原始params keys: {list(params.keys())}")
        if 'filters' in params and isinstance(params.get('filters'), dict):
            print("[DEBUG] Found filters, processing...")
            # 将filters中的数组转换为逗号分隔的字符串
            for key, value in params['filters'].items():
                if isinstance(value, (list, tuple)) and len(value) == 2:
                    params[key] = f"{value[0]},{value[1]}"
                else:
                    params[key] = value
            # 移除filters键
            params.pop('filters', None)
        
        # 处理sortBy -> sort_by
        if 'sortBy' in params:
            params['sort_by'] = params.pop('sortBy')
        
        print(f"[多因子选股] 收到请求: {params}")
        
        # 获取最新日期的数据
        latest_record = StockScreeningData.query.order_by(
            StockScreeningData.trade_date.desc()
        ).first()
        
        if not latest_record:
            return jsonify({
                "success": False,
                "message": "数据库中暂无股票数据，请等待数据同步任务执行",
                "data": [],
                "total": 0
            }), 500
        
        trade_date = latest_record.trade_date
        query = StockScreeningData.query.filter(
            StockScreeningData.trade_date == trade_date
        )
        
        # ===== 估值因子筛选 =====
        pe_range = parse_range(params.get('valuation_pe', '0,200'))
        if pe_range[0] > 0 or pe_range[1] < 200:
            query = query.filter(
                or_(StockScreeningData.pe == None,
                    StockScreeningData.pe.between(pe_range[0], pe_range[1]))
            )
        
        pb_range = parse_range(params.get('valuation_pb', '0,50'))
        if pb_range[0] > 0 or pb_range[1] < 50:
            query = query.filter(
                or_(StockScreeningData.pb == None,
                    StockScreeningData.pb.between(pb_range[0], pb_range[1]))
            )
        
        ps_range = parse_range(params.get('valuation_ps', '0,100'))
        if ps_range[0] > 0 or ps_range[1] < 100:
            query = query.filter(
                or_(StockScreeningData.ps == None,
                    StockScreeningData.ps.between(ps_range[0], ps_range[1]))
            )
        
        # ===== 动量因子筛选 =====
        change_range = parse_range(params.get('momentum_change_percent', '-50,50'))
        if change_range[0] > -50 or change_range[1] < 50:
            query = query.filter(
                or_(StockScreeningData.change_percent == None,
                    StockScreeningData.change_percent.between(change_range[0], change_range[1]))
            )
        
        change5d_range = parse_range(params.get('momentum_change5d', '-50,50'))
        if change5d_range[0] > -50 or change5d_range[1] < 50:
            query = query.filter(
                or_(StockScreeningData.change_5d == None,
                    StockScreeningData.change_5d.between(change5d_range[0], change5d_range[1]))
            )
        
        change10d_range = parse_range(params.get('momentum_change10d', '-80,80'))
        if change10d_range[0] > -80 or change10d_range[1] < 80:
            query = query.filter(
                or_(StockScreeningData.change_10d == None,
                    StockScreeningData.change_10d.between(change10d_range[0], change10d_range[1]))
            )
        
        change20d_range = parse_range(params.get('momentum_change20d', '-80,80'))
        if change20d_range[0] > -80 or change20d_range[1] < 80:
            query = query.filter(
                or_(StockScreeningData.change_20d == None,
                    StockScreeningData.change_20d.between(change20d_range[0], change20d_range[1]))
            )
        
        change60d_range = parse_range(params.get('momentum_change60d', '-100,100'))
        if change60d_range[0] > -100 or change60d_range[1] < 100:
            query = query.filter(
                or_(StockScreeningData.change_60d == None,
                    StockScreeningData.change_60d.between(change60d_range[0], change60d_range[1]))
            )
        
        turnover_range = parse_range(params.get('momentum_turnover_rate', '0,100'))
        if turnover_range[0] > 0 or turnover_range[1] < 100:
            query = query.filter(
                StockScreeningData.turnover_rate.between(turnover_range[0], turnover_range[1])
            )
        
        # ===== 规模因子筛选 =====
        market_cap_range = parse_range(params.get('scale_market_cap', '0,5000'))
        if market_cap_range[0] > 0 or market_cap_range[1] < 5000:
            query = query.filter(
                or_(StockScreeningData.market_cap == None,
                    StockScreeningData.market_cap.between(market_cap_range[0], market_cap_range[1]))
            )
        
        circ_cap_range = parse_range(params.get('scale_circulating_cap', '0,3000'))
        if circ_cap_range[0] > 0 or circ_cap_range[1] < 3000:
            query = query.filter(
                or_(StockScreeningData.circulating_cap == None,
                    StockScreeningData.circulating_cap.between(circ_cap_range[0], circ_cap_range[1]))
            )
        
        # 排序
        sort_by = params.get('sort_by', 'change_percent')
        sort_order = params.get('sort_order', 'desc')
        sort_columns = ['change_percent', 'pe', 'pb', 'turnover_rate', 'roe', 'market_cap']
        if sort_by in sort_columns:
            sort_col = getattr(StockScreeningData, sort_by)
            if sort_order == 'asc':
                query = query.order_by(sort_col.asc())
            else:
                query = query.order_by(sort_col.desc())
        
        # 执行查询
        stocks = query.all()
        
        # 转换为JSON格式
        result = []
        for stock in stocks:
            result.append({
                # 基础信息
                "stock_code": stock.stock_code,
                "stock_name": stock.stock_name,
                # 价格
                "latest_price": round(float(stock.latest_price), 2) if stock.latest_price else None,
                "open": round(float(stock.open_price), 2) if stock.open_price else None,
                "high": round(float(stock.high), 2) if stock.high else None,
                "low": round(float(stock.low), 2) if stock.low else None,
                # 涨跌幅
                "change_percent": round(float(stock.change_percent), 2) if stock.change_percent else 0,
                "change_amount": round(float(stock.change_amount), 2) if stock.change_amount else 0,
                # 成交量
                "volume": round(float(stock.volume), 2) if stock.volume else 0,
                "turnover": round(float(stock.turnover), 2) if stock.turnover else 0,
                "turnover_rate": round(float(stock.turnover_rate), 2) if stock.turnover_rate else 0,
                # 估值因子
                "pe": round(float(stock.pe), 2) if stock.pe else None,
                "pb": round(float(stock.pb), 2) if stock.pb else None,
                "ps": round(float(stock.ps), 2) if stock.ps else None,
                # 动量因子
                "change_5d": round(float(stock.change_5d), 2) if stock.change_5d else None,
                "change_10d": round(float(stock.change_10d), 2) if stock.change_10d else None,
                "change_20d": round(float(stock.change_20d), 2) if stock.change_20d else None,
                "change_60d": round(float(stock.change_60d), 2) if stock.change_60d else None,
                # 质量因子
                "roe": round(float(stock.roe), 2) if stock.roe else None,
                "gross_margin": round(float(stock.gross_margin), 2) if stock.gross_margin else None,
                "net_profit_margin": round(float(stock.net_profit_margin), 2) if stock.net_profit_margin else None,
                "revenue_growth": round(float(stock.revenue_growth), 2) if stock.revenue_growth else None,
                "profit_growth": round(float(stock.profit_growth), 2) if stock.profit_growth else None,
                # 规模因子
                "market_cap": round(float(stock.market_cap), 2) if stock.market_cap else None,
                "circulating_cap": round(float(stock.circulating_cap), 2) if stock.circulating_cap else None,
            })
        
        print(f"[多因子选股] 筛选完成: {len(result)} 只股票")
        
        return jsonify({
            "success": True,
            "message": "筛选成功",
            "data": result,
            "total": len(result),
            "trade_date": str(trade_date),
            "timestamp": get_timestamp()
        })
        
    except Exception as e:
        print(f"[多因子选股] 筛选失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"筛选失败: {str(e)}",
            "data": [],
            "total": 0
        }), 500


@stock_screening_bp.route('/api/stock/list', methods=['GET'])
def get_stock_list():
    """获取股票列表"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 50))
        search = request.args.get('search', '').strip()
        
        latest = StockScreeningData.query.order_by(
            StockScreeningData.trade_date.desc()
        ).first()
        
        if not latest:
            return jsonify({"success": False, "message": "暂无数据", "data": [], "total": 0}), 500
        
        query = StockScreeningData.query.filter(
            StockScreeningData.trade_date == latest.trade_date
        )
        
        if search:
            query = query.filter(
                or_(
                    StockScreeningData.stock_code.contains(search),
                    StockScreeningData.stock_name.contains(search)
                )
            )
        
        total = query.count()
        stocks = query.offset((page - 1) * page_size).limit(page_size).all()
        
        result = [s.to_dict() for s in stocks]
        
        return jsonify({
            "success": True,
            "data": result,
            "total": total,
            "page": page,
            "page_size": page_size,
            "timestamp": get_timestamp()
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e), "data": [], "total": 0}), 500


@stock_screening_bp.route('/api/stock/factors', methods=['GET'])
def get_factor_ranges():
    """获取因子范围配置"""
    return jsonify({
        "success": True,
        "data": {
            "valuation": {
                "pe": {"min": 0, "max": 200, "default": [0, 50]},
                "pb": {"min": 0, "max": 50, "default": [0, 5]},
                "ps": {"min": 0, "max": 100, "default": [0, 10]}
            },
            "momentum": {
                "change_percent": {"min": -50, "max": 50, "default": [-10, 10]},
                "change_5d": {"min": -50, "max": 50, "default": [-20, 20]},
                "change_20d": {"min": -80, "max": 80, "default": [-40, 40]},
                "change_60d": {"min": -100, "max": 100, "default": [-60, 60]},
                "turnover_rate": {"min": 0, "max": 100, "default": [1, 15]}
            },
            "quality": {
                "roe": {"min": 0, "max": 100, "default": [10, 50]},
                "gross_margin": {"min": 0, "max": 100, "default": [20, 80]},
                "net_profit_margin": {"min": -50, "max": 100, "default": [5, 50]},
                "revenue_growth": {"min": -100, "max": 200, "default": [0, 50]},
                "profit_growth": {"min": -200, "max": 300, "default": [0, 100]}
            },
            "scale": {
                "market_cap": {"min": 0, "max": 5000, "default": [100, 5000]},
                "circulating_cap": {"min": 0, "max": 3000, "default": [50, 3000]}
            }
        },
        "timestamp": get_timestamp()
    })


@stock_screening_bp.route('/api/stock/stats', methods=['GET'])
def get_market_stats():
    """获取市场统计数据"""
    try:
        latest = StockScreeningData.query.order_by(
            StockScreeningData.trade_date.desc()
        ).first()
        
        if not latest:
            return jsonify({"success": False, "message": "暂无数据"}), 500
        
        trade_date = latest.trade_date
        stocks = StockScreeningData.query.filter_by(trade_date=trade_date).all()
        
        up_count = sum(1 for s in stocks if s.change_percent and s.change_percent > 0)
        down_count = sum(1 for s in stocks if s.change_percent and s.change_percent < 0)
        
        return jsonify({
            "success": True,
            "data": {
                "total_stocks": len(stocks),
                "up_count": up_count,
                "down_count": down_count,
                "涨停数量": sum(1 for s in stocks if s.change_percent and s.change_percent >= 9.9),
                "跌停数量": sum(1 for s in stocks if s.change_percent and s.change_percent <= -9.9),
            },
            "trade_date": str(trade_date),
            "timestamp": get_timestamp()
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@stock_screening_bp.route('/api/stock/sync', methods=['POST'])
def trigger_sync():
    """手动触发数据同步"""
    try:
        from tasks.sync_stock_screening import sync_stock_screening_data
        result = sync_stock_screening_data(force=True)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@stock_screening_bp.route('/api/stock/by_codes', methods=['POST'])
def get_stocks_by_codes():
    """根据股票代码列表获取数据"""
    try:
        data = request.get_json() or {}
        codes = data.get('codes', [])
        
        if not codes:
            return jsonify({"success": True, "data": []})
        
        # 去掉 sh. sz. 前缀
        clean_codes = []
        for c in codes:
            if isinstance(c, str):
                c = c.replace('sh.', '').replace('sz.', '').replace('SH.', '').replace('SZ.', '')
                if c:
                    clean_codes.append(c)
        
        if not clean_codes:
            return jsonify({"success": True, "data": []})
        
        # 获取最新日期
        latest = StockScreeningData.query.order_by(
            StockScreeningData.trade_date.desc()
        ).first()
        
        if not latest:
            return jsonify({"success": False, "message": "暂无数据"})
        
        # 查询指定股票
        stocks = StockScreeningData.query.filter(
            StockScreeningData.trade_date == latest.trade_date,
            StockScreeningData.stock_code.in_(clean_codes)
        ).all()
        
        # 如果最新日期没有这些股票的数据，回退到前一天
        if len(stocks) < len(clean_codes):
            missing_codes = set(clean_codes) - {s.stock_code for s in stocks}
            dates = db.session.query(StockScreeningData.trade_date).distinct().order_by(StockScreeningData.trade_date.desc()).limit(5).all()
            for date_row in dates:
                date_val = date_row[0]
                if date_val == latest.trade_date:
                    continue
                more_stocks = StockScreeningData.query.filter(
                    StockScreeningData.trade_date == date_val,
                    StockScreeningData.stock_code.in_(missing_codes)
                ).all()
                if more_stocks:
                    stocks.extend(more_stocks)
                    missing_codes = missing_codes - {s.stock_code for s in more_stocks}
                    if not missing_codes:
                        break
        
        result = [s.to_dict() for s in stocks]
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
