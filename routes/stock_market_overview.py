# routes/stock_market_models_overview.py
from flask import Blueprint, request, jsonify
from models import db
from models.stock_market_models_overview import (
    StockSSESummary, StockSZSESummary, StockSZSEAreaSummary, StockSZSESectorSummary, StockSSEDealDaily
)
from sqlalchemy import desc
import akshare as ak
from datetime import datetime, date
from config.logging_config import logger

stock_overview_bp = Blueprint('stock_overview', __name__)


def safe_attr(obj, attr_name):
    return getattr(obj, attr_name, None) if obj else None


# --- Helper Functions ---
def parse_date_string(date_str):
    """Parse date string like '202412' or '2024-12-31' into date object or string."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y%m%d').date()
    except ValueError:
        try:
            return datetime.strptime(date_str, '%Y%m').date()
        except ValueError:
            try:
                return datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return None


def serialize_date(obj):
    if isinstance(obj, date):
        return obj.isoformat()
    return obj


def find_latest_record_up_to_date(query_base, date_column, target_date_obj):
    if target_date_obj is None:
        return None
    latest_record = query_base.filter(date_column <= target_date_obj).order_by(desc(date_column)).first()
    return latest_record


@stock_overview_bp.route('/sse-summary', methods=['GET'])
def get_sse_summary():
    date_param = request.args.get('date')
    parsed_date = parse_date_string(date_param)
    try:
        # Step 1: 获取 StockSSESummary（用于卡片）
        summary_record = None
        if parsed_date:
            summary_record = StockSSESummary.query.filter_by(trade_date=parsed_date).first()
            if not summary_record:
                summary_record = find_latest_record_up_to_date(
                    StockSSESummary.query, StockSSESummary.trade_date, parsed_date
                )
        else:
            summary_record = StockSSESummary.query.order_by(desc(StockSSESummary.trade_date)).first()

        if not summary_record:
            return jsonify({"success": False, "message": "SSE Summary data not found."}), 404

        # Step 2: 获取 StockSSEDealDaily（用于表格）
        deal_record = None
        deal_date = summary_record.trade_date
        deal_record = StockSSEDealDaily.query.filter_by(trade_date=deal_date).first()

        # Step 3: 构建 Deal Daily 嵌套数据结构
        empty_category = {"stock": None, "main_a": None, "main_b": None, "star": None, "repo": None}

        if deal_record:
            deal_daily_data = {
                "listed_count": {
                    "stock": safe_attr(deal_record, "listed_count_stock"),
                    "main_a": safe_attr(deal_record, "listed_count_main_a"),
                    "main_b": safe_attr(deal_record, "listed_count_main_b"),
                    "star": safe_attr(deal_record, "listed_count_star"),
                    "repo": safe_attr(deal_record, "listed_count_repo"),
                },
                "total_mv": {
                    "stock": safe_attr(deal_record, "total_mv_stock"),
                    "main_a": safe_attr(deal_record, "total_mv_main_a"),
                    "main_b": safe_attr(deal_record, "total_mv_main_b"),
                    "star": safe_attr(deal_record, "total_mv_star"),
                    "repo": safe_attr(deal_record, "total_mv_repo"),
                },
                "circulating_mv": {
                    "stock": safe_attr(deal_record, "circulating_mv_stock"),
                    "main_a": safe_attr(deal_record, "circulating_mv_main_a"),
                    "main_b": safe_attr(deal_record, "circulating_mv_main_b"),
                    "star": safe_attr(deal_record, "circulating_mv_star"),
                    "repo": safe_attr(deal_record, "circulating_mv_repo"),
                },
                "turnover_amount": {
                    "stock": safe_attr(deal_record, "turnover_amount_stock"),
                    "main_a": safe_attr(deal_record, "turnover_amount_main_a"),
                    "main_b": safe_attr(deal_record, "turnover_amount_main_b"),
                    "star": safe_attr(deal_record, "turnover_amount_star"),
                    "repo": safe_attr(deal_record, "turnover_amount_repo"),
                },
                "volume": {
                    "stock": safe_attr(deal_record, "volume_stock"),
                    "main_a": safe_attr(deal_record, "volume_main_a"),
                    "main_b": safe_attr(deal_record, "volume_main_b"),
                    "star": safe_attr(deal_record, "volume_star"),
                    "repo": safe_attr(deal_record, "volume_repo"),
                },
                "avg_pe": {
                    "stock": safe_attr(deal_record, "avg_pe_stock"),
                    "main_a": safe_attr(deal_record, "avg_pe_main_a"),
                    "main_b": safe_attr(deal_record, "avg_pe_main_b"),
                    "star": safe_attr(deal_record, "avg_pe_star"),
                    "repo": safe_attr(deal_record, "avg_pe_repo"),
                },
                "turnover_rate": {
                    "stock": safe_attr(deal_record, "turnover_rate_stock"),
                    "main_a": safe_attr(deal_record, "turnover_rate_main_a"),
                    "main_b": safe_attr(deal_record, "turnover_rate_main_b"),
                    "star": safe_attr(deal_record, "turnover_rate_star"),
                    "repo": safe_attr(deal_record, "turnover_rate_repo"),
                },
                "circulating_turnover_rate": {
                    "stock": safe_attr(deal_record, "circulating_turnover_rate_stock"),
                    "main_a": safe_attr(deal_record, "circulating_turnover_rate_main_a"),
                    "main_b": safe_attr(deal_record, "circulating_turnover_rate_main_b"),
                    "star": safe_attr(deal_record, "circulating_turnover_rate_star"),
                    "repo": safe_attr(deal_record, "circulating_turnover_rate_repo"),
                },
            }
        else:
            # 如果没有 DealDaily 记录，返回空结构
            deal_daily_data = {
                "listed_count": empty_category.copy(),
                "total_mv": empty_category.copy(),
                "circulating_mv": empty_category.copy(),
                "turnover_amount": empty_category.copy(),
                "volume": empty_category.copy(),
                "avg_pe": empty_category.copy(),
                "turnover_rate": empty_category.copy(),
                "circulating_turnover_rate": empty_category.copy(),
            }

        # Step 4: 合并响应数据
        summary_dict = summary_record.to_dict()
        response_data = {
            "trade_date": summary_dict["trade_date"],
            "update_time": summary_dict["update_time"],
            "star_board": summary_dict["star_board"],
            "main_board": summary_dict["main_board"],
            # 新增：Deal Daily 细分数据（用于表格）
            "deal_daily": deal_daily_data["listed_count"],
            "deal_daily_mv": deal_daily_data["total_mv"],
            "deal_daily_circ_mv": deal_daily_data["circulating_mv"],
            "deal_daily_turnover": deal_daily_data["turnover_amount"],
            "deal_daily_volume": deal_daily_data["volume"],
            "deal_daily_pe": deal_daily_data["avg_pe"],
            "deal_daily_turnover_rate": deal_daily_data["turnover_rate"],
            "deal_daily_circ_turnover_rate": deal_daily_data["circulating_turnover_rate"],
        }

        return jsonify({
            "success": True,
            "data": response_data,
            "returned_date": summary_record.trade_date.isoformat()
        })

    except Exception as e:
        logger.error(f"Error fetching SSE Summary: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Internal server error"}), 500

@stock_overview_bp.route('/sse-summary/history', methods=['GET'])
def get_sse_summary_history():
    """Get paginated history of SSE Summary data."""
    page = request.args.get('page', 1, type=int)
    page_size = min(max(request.args.get('page_size', 20, type=int), 1), 100)
    try:
        query = StockSSESummary.query.order_by(desc(StockSSESummary.trade_date))
        paginated = query.paginate(page=page, per_page=page_size, error_out=False)
        items = [item.to_dict() for item in paginated.items]
        return jsonify({
            "success": True,
            "data": {
                "items": items,
                "total": paginated.total,
                "page": paginated.page,
                "page_size": paginated.per_page,
                "pages": paginated.pages
            }
        })
    except Exception as e:
        logger.error(f"Error fetching SSE Summary history: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500


# --- SZSE Summary ---
@stock_overview_bp.route('/szse-summary', methods=['GET'])
def get_szse_summary():
    """Get SZSE Summary data (latest or by date)."""
    date_param = request.args.get('date')
    parsed_date = parse_date_string(date_param)
    try:
        records = []
        if parsed_date:
            # First, try to find records for the exact date
            records = StockSZSESummary.query.filter_by(trade_date=parsed_date).all()
            # If not found, find the latest records up to the parsed_date
            if not records:
                logger.info(f"SZSE Summary for exact date {parsed_date} not found in DB, looking for latest available.")
                latest_date = db.session.query(db.func.max(StockSZSESummary.trade_date)) \
                                        .filter(StockSZSESummary.trade_date <= parsed_date).scalar()
                if latest_date:
                    records = StockSZSESummary.query.filter_by(trade_date=latest_date).all()
        else:
            # If no date provided, get records for the absolute latest date
            latest_date = db.session.query(db.func.max(StockSZSESummary.trade_date)).scalar()
            if latest_date:
                records = StockSZSESummary.query.filter_by(trade_date=latest_date).all()

        if not records:
            logger.info(f"SZSE Summary for date {parsed_date or 'latest'} not found in DB after checking latest available.")
            return jsonify({"success": False, "message": "Data not found in database."}), 404

        # Log which date's data is being returned (useful for debugging)
        actual_returned_date = records[0].trade_date if records else None
        if parsed_date and actual_returned_date and actual_returned_date != parsed_date:
             logger.info(f"Requested SZSE Summary for {parsed_date}, returning latest available for {actual_returned_date}.")

        return jsonify({
            "success": True,
            "data": [r.to_dict() for r in records],
            "source": "database",
            "returned_date": actual_returned_date.isoformat() if actual_returned_date else None
        })

    except Exception as e:
        logger.error(f"Error fetching SZSE Summary: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

@stock_overview_bp.route('/szse-summary/history', methods=['GET'])
def get_szse_summary_history():
    """Get paginated history of SZSE Summary data."""
    page = request.args.get('page', 1, type=int)
    page_size = min(max(request.args.get('page_size', 20, type=int), 1), 100)
    date_filter = request.args.get('date') # Filter by specific date
    parsed_date_filter = parse_date_string(date_filter)
    try:
        query = StockSZSESummary.query
        if parsed_date_filter:
            query = query.filter(StockSZSESummary.trade_date == parsed_date_filter)
        query = query.order_by(StockSZSESummary.trade_date.asc(), StockSZSESummary.security_type.asc())
        paginated = query.paginate(page=page, per_page=page_size, error_out=False)
        items = [item.to_dict() for item in paginated.items]
        return jsonify({
            "success": True,
            "data": {
                "items": items,
                "total": paginated.total,
                "page": paginated.page,
                "page_size": paginated.per_page,
                "pages": paginated.pages
            }
        })
    except Exception as e:
        logger.error(f"Error fetching SZSE Summary history: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500


# --- SZSE Area Summary ---
@stock_overview_bp.route('/szse-area-summary', methods=['GET'])
def get_szse_area_summary():
    """Get SZSE Area Summary data (latest or by period)."""
    period_param = request.args.get('date') # Frontend passes 'date' for month YYYY-MM, backend expects YYYYMM
    # Convert YYYY-MM to YYYYMM for internal use and DB query
    if period_param and '-' in period_param:
         period_param_internal = period_param.replace('-', '')
    else:
         period_param_internal = period_param

    try:
        records = []
        if period_param_internal:
            # First, try to find records for the exact period
            records = StockSZSEAreaSummary.query.filter_by(report_period=period_param_internal).all()
            # If not found, find the latest records up to the parsed_period
            if not records:
                logger.info(f"SZSE Area Summary for exact period {period_param_internal} not found in DB, looking for latest available.")
                # Find the max report_period that is <= the requested one
                latest_period = db.session.query(db.func.max(StockSZSEAreaSummary.report_period)) \
                                          .filter(StockSZSEAreaSummary.report_period <= period_param_internal).scalar()
                if latest_period:
                    records = StockSZSEAreaSummary.query.filter_by(report_period=latest_period).all()
        else:
            # If no period provided, get records for the absolute latest period
            latest_period = db.session.query(db.func.max(StockSZSEAreaSummary.report_period)).scalar()
            if latest_period:
                records = StockSZSEAreaSummary.query.filter_by(report_period=latest_period).all()

        if not records:
            logger.info(f"SZSE Area Summary for period {period_param_internal or 'latest'} not found in DB after checking latest available.")
            return jsonify({"success": False, "message": "Data not found in database."}), 404

        # Log which period's data is being returned (useful for debugging)
        actual_returned_period = records[0].report_period if records else None
        if period_param_internal and actual_returned_period and actual_returned_period != period_param_internal:
             logger.info(f"Requested SZSE Area Summary for {period_param_internal}, returning latest available for {actual_returned_period}.")

        return jsonify({
            "success": True,
            "data": [r.to_dict() for r in records],
            "source": "database",
            "returned_period": actual_returned_period
        })

    except Exception as e:
        logger.error(f"Error fetching SZSE Area Summary: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

@stock_overview_bp.route('/szse-area-summary/history', methods=['GET'])
def get_szse_area_summary_history():
    """Get paginated history of SZSE Area Summary data."""
    page = request.args.get('page', 1, type=int)
    page_size = min(max(request.args.get('page_size', 20, type=int), 1), 100)
    period_filter = request.args.get('period') # Filter by specific period
    try:
        query = StockSZSEAreaSummary.query
        if period_filter:
            query = query.filter(StockSZSEAreaSummary.report_period == period_filter)
        query = query.order_by(StockSZSEAreaSummary.report_period.desc(), StockSZSEAreaSummary.area.asc())
        paginated = query.paginate(page=page, per_page=page_size, error_out=False)
        items = [item.to_dict() for item in paginated.items]
        return jsonify({
            "success": True,
            "data": {
                "items": items,
                "total": paginated.total,
                "page": paginated.page,
                "page_size": paginated.per_page,
                "pages": paginated.pages
            }
        })
    except Exception as e:
        logger.error(f"Error fetching SZSE Area Summary history: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500


# --- SZSE Sector Summary ---
@stock_overview_bp.route('/szse-sector-summary', methods=['GET'])
def get_szse_sector_summary():
    """Get SZSE Sector Summary data (latest or by period and symbol)."""
    period_param = request.args.get('date') # Frontend passes 'date' for month YYYY-MM, backend expects YYYYMM
    symbol_param = request.args.get('symbol', '当月') # Default to '当月'

    # Convert YYYY-MM to YYYYMM for internal use and DB query
    if period_param and '-' in period_param:
         period_param_internal = period_param.replace('-', '')
    else:
         period_param_internal = period_param

    try:
        records = []
        if period_param_internal:
            # First, try to find records for the exact period and symbol
            records = StockSZSESectorSummary.query.filter_by(
                report_period=period_param_internal,
                symbol=symbol_param
            ).all()
            # If not found, find the latest records up to the parsed_period for the symbol
            if not records:
                logger.info(f"SZSE Sector Summary for exact period {period_param_internal} and symbol {symbol_param} not found in DB, looking for latest available.")
                # Find the max report_period that is <= the requested one for the given symbol
                latest_period = db.session.query(db.func.max(StockSZSESectorSummary.report_period)) \
                                           .filter(
                                               StockSZSESectorSummary.report_period <= period_param_internal,
                                               StockSZSESectorSummary.symbol == symbol_param
                                           ).scalar()
                if latest_period:
                    records = StockSZSESectorSummary.query.filter_by(
                        report_period=latest_period,
                        symbol=symbol_param
                    ).all()
        else:
            # If no period provided, get records for the absolute latest period for the symbol
            latest_period = db.session.query(db.func.max(StockSZSESectorSummary.report_period)) \
                                      .filter_by(symbol=symbol_param).scalar()
            if latest_period:
                records = StockSZSESectorSummary.query.filter_by(
                    report_period=latest_period,
                    symbol=symbol_param
                ).all()

        if not records:
            logger.info(f"SZSE Sector Summary for period {period_param_internal or 'latest'} and symbol {symbol_param} not found in DB after checking latest available.")
            return jsonify({"success": False, "message": "Data not found in database."}), 404

        # Log which period's data is being returned (useful for debugging)
        actual_returned_period = records[0].report_period if records else None
        if period_param_internal and actual_returned_period and actual_returned_period != period_param_internal:
             logger.info(f"Requested SZSE Sector Summary for {period_param_internal}, returning latest available for {actual_returned_period} (symbol: {symbol_param}).")

        return jsonify({
            "success": True,
            "data": [r.to_dict() for r in records],
            "source": "database",
            "returned_period": actual_returned_period
        })

    except Exception as e:
        logger.error(f"Error fetching SZSE Sector Summary: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

@stock_overview_bp.route('/szse-sector-summary/history', methods=['GET'])
def get_szse_sector_summary_history():
    """Get paginated history of SZSE Sector Summary data."""
    page = request.args.get('page', 1, type=int)
    page_size = min(max(request.args.get('page_size', 20, type=int), 1), 100)
    period_filter = request.args.get('period')
    symbol_filter = request.args.get('symbol')
    try:
        query = StockSZSESectorSummary.query
        if period_filter:
            query = query.filter(StockSZSESectorSummary.report_period == period_filter)
        if symbol_filter:
            query = query.filter(StockSZSESectorSummary.symbol == symbol_filter)
        query = query.order_by(StockSZSESectorSummary.report_period.desc(), StockSZSESectorSummary.sector_chinese.asc())
        paginated = query.paginate(page=page, per_page=page_size, error_out=False)
        items = [item.to_dict() for item in paginated.items]
        return jsonify({
            "success": True,
            "data": {
                "items": items,
                "total": paginated.total,
                "page": paginated.page,
                "page_size": paginated.per_page,
                "pages": paginated.pages
            }
        })
    except Exception as e:
        logger.error(f"Error fetching SZSE Sector Summary history: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500


# --- SSE Deal Daily ---
@stock_overview_bp.route('/sse-deal-daily', methods=['GET'])
def get_sse_deal_daily():
    """Get SSE Deal Daily data (latest or by date)."""
    date_param = request.args.get('date')
    parsed_date = parse_date_string(date_param)
    try:
        record = None
        if parsed_date:
            # First, try to find the exact date
            record = StockSSEDealDaily.query.filter_by(trade_date=parsed_date).first()
            # If not found, find the latest record up to the parsed_date
            if not record:
                logger.info(f"SSE Deal Daily for exact date {parsed_date} not found in DB, looking for latest available.")
                record = find_latest_record_up_to_date(
                    StockSSEDealDaily.query, StockSSEDealDaily.trade_date, parsed_date
                )
        else:
            # If no date provided, get the absolute latest
            record = StockSSEDealDaily.query.order_by(desc(StockSSEDealDaily.trade_date)).first()

        if not record:
            logger.info(f"SSE Deal Daily for date {parsed_date} not found in DB after checking latest available.")
            return jsonify({"success": False, "message": "Data not found in database."}), 404

        # Log which date's data is being returned (useful for debugging)
        actual_returned_date = record.trade_date
        if parsed_date and actual_returned_date != parsed_date:
             logger.info(f"Requested SSE Deal Daily for {parsed_date}, returning latest available for {actual_returned_date}.")

        return jsonify({
            "success": True,
            "data": record.to_dict(), # Assumes your model has a to_dict method
            "source": "database",
            "returned_date": actual_returned_date.isoformat() # Include the actual date returned
        })

    except Exception as e:
        logger.error(f"Error fetching SSE Deal Daily: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

@stock_overview_bp.route('/sse-deal-daily/history', methods=['GET'])
def get_sse_deal_daily_history():
    """Get paginated history of SSE Deal Daily data."""
    page = request.args.get('page', 1, type=int)
    page_size = min(max(request.args.get('page_size', 20, type=int), 1), 100)
    try:
        query = StockSSEDealDaily.query.order_by(desc(StockSSEDealDaily.trade_date))
        paginated = query.paginate(page=page, per_page=page_size, error_out=False)
        items = [item.to_dict() for item in paginated.items]
        return jsonify({
            "success": True,
            "data": {
                "items": items,
                "total": paginated.total,
                "page": paginated.page,
                "page_size": paginated.per_page,
                "pages": paginated.pages
            }
        })
    except Exception as e:
        logger.error(f"Error fetching SSE Deal Daily history: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500