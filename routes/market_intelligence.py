# routes/market_intelligence.py
# 市场资讯看板API - 整合多维度市场数据

from flask import Blueprint, jsonify, request
from datetime import datetime, date, timedelta
from typing import List, Dict
import pandas as pd
from config.logging_config import logger
from models import db

# 导入tushare
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.tushare_api import (
    get_pro, get_daily_basic, get_trade_cal, get_moneyflow_hsgt,
    get_margin, get_kpl_concept_cons, get_index_daily, get_stock_list,
    get_top_inst, get_moneyflow, get_block_trade,
    get_news, get_fund_news, get_stock_news, get_macro_news
)

# 导入新闻服务
from services.news_service import (
    fetch_news, get_news_sources, clear_news_cache
)

market_intelligence_bp = Blueprint('market_intelligence', __name__)


def get_latest_trade_date():
    """获取最新交易日"""
    today = date.today()
    df_cal = get_trade_cal(
        start_date=(today - timedelta(days=30)).strftime('%Y%m%d'),
        end_date=today.strftime('%Y%m%d')
    )
    if df_cal is not None and not df_cal.empty:
        df_cal = df_cal[df_cal['is_open'] == 1]
        if not df_cal.empty:
            return df_cal['cal_date'].max()
    return today.strftime('%Y%m%d')


@market_intelligence_bp.route('/api/market/intelligence/overview', methods=['GET'])
def get_market_overview():
    """市场概览 - 核心指标"""
    try:
        trade_date = request.args.get('date', get_latest_trade_date())
        
        # 1. 获取每日指标统计
        df_basic = get_daily_basic(trade_date, limit=5000)
        
        overview = {
            "trade_date": trade_date,
            "total_stocks": len(df_basic) if not df_basic.empty else 0,
            "up_count": 0,
            "down_count": 0,
            "limit_up_count": 0,
            "limit_down_count": 0,
            "avg_pe": None,
            "avg_pb": None,
            "avg_turnover": None
        }
        
        if not df_basic.empty:
            # 上涨下跌统计 - 添加字段检查
            if 'pct_chg' in df_basic.columns:
                overview['up_count'] = int((df_basic['pct_chg'] > 0).sum())
                overview['down_count'] = int((df_basic['pct_chg'] < 0).sum())
            overview['avg_pe'] = float(df_basic['pe'].mean()) if 'pe' in df_basic.columns and df_basic['pe'].notna().any() else None
            overview['avg_pb'] = float(df_basic['pb'].mean()) if 'pb' in df_basic.columns and df_basic['pb'].notna().any() else None
            overview['avg_turnover'] = float(df_basic['turnover_rate'].mean()) if 'turnover_rate' in df_basic.columns and df_basic['turnover_rate'].notna().any() else None
        
        # 2. 北向资金流向
        try:
            df_hsgt = get_moneyflow_hsgt(trade_date)
            if not df_hsgt.empty:
                overview['northbound'] = {
                    'net_buy': float(df_hsgt['net_mf'].iloc[0]) if 'net_mf' in df_hsgt.columns else None,
                    'buy_amount': float(df_hsgt['buy_amount'].iloc[0]) if 'buy_amount' in df_hsgt.columns else None,
                    'sell_amount': float(df_hsgt['sell_amount'].iloc[0]) if 'sell_amount' in df_hsgt.columns else None
                }
        except:
            pass
        
        # 3. 融资融券
        try:
            df_margin = get_margin(trade_date)
            if not df_margin.empty:
                overview['margin'] = {
                    'total_balance': float(df_margin['margin_balance'].sum()) if 'margin_balance' in df_margin.columns else None,
                    'buy_amount': float(df_margin['buy_amount'].sum()) if 'buy_amount' in df_margin.columns else None,
                    'sell_amount': float(df_margin['sell_amount'].sum()) if 'sell_amount' in df_margin.columns else None
                }
        except:
            pass
        
        return jsonify({
            "success": True,
            "data": overview
        })
        
    except Exception as e:
        logger.error(f"获取市场概览失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@market_intelligence_bp.route('/api/market/intelligence/heatmap', methods=['GET'])
def get_sector_heatmap():
    """板块热力图"""
    try:
        trade_date = request.args.get('date', get_latest_trade_date())
        
        # 使用kpl概念股数据
        try:
            df_concept = get_kpl_concept_cons(trade_date)
            if not df_concept.empty:
                # 按概念分组统计
                sectors = df_concept.groupby('concept_name').agg({
                    'ts_code': 'count',
                    'hot_num': 'mean'
                }).reset_index()
                sectors.columns = ['name', 'stock_count', 'heat']
                sectors = sectors.sort_values('heat', ascending=False).head(20)
                
                return jsonify({
                    "success": True,
                    "data": sectors.to_dict('records')
                })
        except Exception as e:
            logger.warning(f"获取板块热力图失败: {e}")
        
        return jsonify({"success": True, "data": []})
        
    except Exception as e:
        logger.error(f"获取板块热力图失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@market_intelligence_bp.route('/api/market/intelligence/top-stocks', methods=['GET'])
def get_top_stocks():
    """涨跌排行榜"""
    try:
        trade_date = request.args.get('date', get_latest_trade_date())
        limit = int(request.args.get('limit', 20))
        
        df_basic = get_daily_basic(trade_date, limit=5000)
        
        if df_basic.empty:
            return jsonify({"success": True, "data": {"up": [], "down": []}})
        
        # 获取股票名称
        stock_list = get_stock_list()
        name_map = dict(zip(stock_list['ts_code'], stock_list['name'])) if not stock_list.empty else {}
        
        df_basic['name'] = df_basic['ts_code'].map(name_map)
        df_basic['code'] = df_basic['ts_code'].str.split('.').str[0]
        
        # 涨停榜
        limit_up = df_basic[df_basic['pct_chg'] >= 9.9].sort_values('pct_chg', ascending=False).head(limit)
        
        # 跌停榜
        limit_down = df_basic[df_basic['pct_chg'] <= -9.9].sort_values('pct_chg').head(limit)
        
        # 涨幅榜
        top_gainers = df_basic.nlargest(limit, 'pct_chg')
        
        # 跌幅榜
        top_losers = df_basic.nsmallest(limit, 'pct_chg')
        
        return jsonify({
            "success": True,
            "data": {
                "limit_up": limit_up[['code', 'name', 'close', 'pct_chg', 'turnover_rate']].to_dict('records'),
                "limit_down": limit_down[['code', 'name', 'close', 'pct_chg', 'turnover_rate']].to_dict('records'),
                "top_gainers": top_gainers[['code', 'name', 'close', 'pct_chg', 'turnover_rate']].to_dict('records'),
                "top_losers": top_losers[['code', 'name', 'close', 'pct_chg', 'turnover_rate']].to_dict('records')
            }
        })
        
    except Exception as e:
        logger.error(f"获取涨跌榜失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@market_intelligence_bp.route('/api/market/intelligence/analysis', methods=['POST'])
def get_ai_analysis():
    """AI市场分析"""
    try:
        data = request.json or {}
        market_data = data.get('market_data', {})
        
        # 构建分析提示词
        prompt = f"""
基于以下市场数据进行分析：

【市场概览】
- 交易日: {market_data.get('trade_date', 'N/A')}
- 上涨股票: {market_data.get('up_count', 0)} 只
- 下跌股票: {market_data.get('down_count', 0)} 只
- 涨停: {market_data.get('limit_up_count', 0)} 只
- 跌停: {market_data.get('limit_down_count', 0)} 只
- 平均PE: {market_data.get('avg_pe', 'N/A')}
- 平均PB: {market_data.get('avg_pb', 'N/A')}

【资金流向】
- 北向资金: {market_data.get('northbound', {})}
- 融资融券: {market_data.get('margin', {})}

请提供：
1. 市场情绪分析（乐观/中性/悲观）
2. 主要风险提示
3. 投资建议
"""
        
        # 这里可以调用AI模型进行分析
        # 暂时返回模拟分析结果
        analysis = {
            "sentiment": "中性偏乐观",
            "sentiment_score": 0.6,
            "summary": "市场整体表现平稳，上涨股票多于下跌股票，北向资金持续流入，市场情绪偏向积极。",
            "risks": [
                "部分板块估值偏高，注意回调风险",
                "外围市场波动可能影响A股"
            ],
            "opportunities": [
                "低估值蓝筹股具备配置价值",
                "科技成长股值得关注"
            ],
            "suggestion": "建议保持适度仓位，关注业绩确定性强的优质标的。",
            "prompt": prompt  # 返回prompt供调试
        }
        
        return jsonify({
            "success": True,
            "data": analysis
        })
        
    except Exception as e:
        logger.error(f"AI分析失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ==================== 新增API接口 ====================

@market_intelligence_bp.route('/api/market/intelligence/top-list', methods=['GET'])
def get_top_list():
    """龙虎榜数据"""
    try:
        trade_date = request.args.get('date', get_latest_trade_date())
        
        # 获取龙虎榜数据
        try:
            df_top = get_top_inst(trade_date)
        except Exception as e:
            logger.warning(f"获取龙虎榜失败: {e}")
            df_top = pd.DataFrame()
        
        # 获取股票名称映射
        stock_list = get_stock_list()
        name_map = dict(zip(stock_list['ts_code'], stock_list['name'])) if not stock_list.empty else {}
        
        # 处理数据
        if not df_top.empty:
            df_top['name'] = df_top['ts_code'].map(name_map)
            
            # 按股票分组汇总
            grouped = df_top.groupby('ts_code').agg({
                'name': 'first',
                'buy': 'sum',
                'sell': 'sum',
                'net_buy': 'sum',
                'buy_inst': lambda x: ','.join(x.unique()[:3]),
                'sell_inst': lambda x: ','.join(x.unique()[:3])
            }).reset_index()
            
            # 获取涨跌幅
            df_basic = get_daily_basic(trade_date)
            if not df_basic.empty:
                pct_map = dict(zip(df_basic['ts_code'], df_basic['pct_chg']))
                amount_map = dict(zip(df_basic['ts_code'], df_basic['amount']))
                grouped['pct_change'] = grouped['ts_code'].map(pct_map)
                grouped['amount'] = grouped['ts_code'].map(amount_map)
            else:
                grouped['pct_change'] = 0
                grouped['amount'] = 0
            
            # 排序并返回
            grouped = grouped.sort_values('amount', ascending=False).head(20)
            
            result = {
                'date': trade_date,
                'count': len(grouped),
                'list': grouped[['ts_code', 'name', 'pct_change', 'amount', 'buy_inst', 'sell_inst']].to_dict('records')
            }
        else:
            result = {
                'date': trade_date,
                'count': 0,
                'list': []
            }
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"获取龙虎榜失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@market_intelligence_bp.route('/api/market/intelligence/moneyflow', methods=['GET'])
def get_moneyflow():
    """个股资金流向"""
    try:
        trade_date = request.args.get('date', get_latest_trade_date())
        
        # 获取资金流向数据
        try:
            df_mf = get_moneyflow(trade_date)
        except Exception as e:
            logger.warning(f"获取资金流向失败: {e}")
            df_mf = pd.DataFrame()
        
        # 获取股票名称映射
        stock_list = get_stock_list()
        name_map = dict(zip(stock_list['ts_code'], stock_list['name'])) if not stock_list.empty else {}
        
        if not df_mf.empty:
            df_mf['name'] = df_mf['ts_code'].map(name_map)
            
            # 选择关键字段
            cols = ['ts_code', 'name', 'net_mf_amount', 'main_net_in_amount', 'retail_net_in_amount']
            available_cols = [c for c in cols if c in df_mf.columns]
            df_mf = df_mf[available_cols]
            
            # 重命名列
            rename_map = {
                'net_mf_amount': 'net_mf_amount',
                'main_net_in_amount': 'main_net',
                'retail_net_in_amount': 'retail_net'
            }
            df_mf = df_mf.rename(columns=rename_map)
            
            # 排序
            df_mf = df_mf.sort_values('net_mf_amount', ascending=False).head(20)
            
            result = {
                'date': trade_date,
                'net': float(df_mf['net_mf_amount'].sum()) if 'net_mf_amount' in df_mf.columns else 0,
                'list': df_mf.to_dict('records')
            }
        else:
            result = {
                'date': trade_date,
                'net': 0,
                'list': []
            }
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"获取资金流向失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@market_intelligence_bp.route('/api/market/intelligence/moneyflow-hsgt', methods=['GET'])
def get_moneyflow_hsgt_data():
    """沪深港通资金流向"""
    try:
        trade_date = request.args.get('date', get_latest_trade_date())
        
        df_hsgt = get_moneyflow_hsgt(trade_date)
        
        if not df_hsgt.empty:
            # 沪股通
            sh_data = df_hsgt[df_hsgt['hs_type'] == 'SH'] if 'hs_type' in df_hsgt.columns else pd.DataFrame()
            # 深股通
            sz_data = df_hsgt[df_hsgt['hs_type'] == 'SZ'] if 'hs_type' in df_hsgt.columns else pd.DataFrame()
            
            result = {
                'date': trade_date,
                'sh_net': float(sh_data['net_mf'].iloc[0]) if not sh_data.empty and 'net_mf' in sh_data.columns else 0,
                'sz_net': float(sz_data['net_mf'].iloc[0]) if not sz_data.empty and 'net_mf' in sz_data.columns else 0,
                'net_buy': float(df_hsgt['net_mf'].sum()) if 'net_mf' in df_hsgt.columns else 0
            }
        else:
            result = {
                'date': trade_date,
                'sh_net': 0,
                'sz_net': 0,
                'net_buy': 0
            }
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"获取沪深港通资金流向失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@market_intelligence_bp.route('/api/market/intelligence/block-trade', methods=['GET'])
def get_block_trade_data():
    """大宗交易数据"""
    try:
        trade_date = request.args.get('date', get_latest_trade_date())
        
        # 获取大宗交易数据
        try:
            # 尝试获取近5天的大宗交易
            start_date = (datetime.strptime(trade_date, '%Y%m%d') - timedelta(days=5)).strftime('%Y%m%d')
            df_block = get_block_trade(start_date, trade_date)
        except Exception as e:
            logger.warning(f"获取大宗交易失败: {e}")
            df_block = pd.DataFrame()
        
        # 获取股票名称映射
        stock_list = get_stock_list()
        name_map = dict(zip(stock_list['ts_code'], stock_list['name'])) if not stock_list.empty else {}
        
        if not df_block.empty:
            df_block['name'] = df_block['ts_code'].map(name_map)
            
            # 计算折价率
            if 'price' in df_block.columns and 'pre_close' in df_block.columns:
                df_block['discount'] = ((df_block['price'] - df_block['pre_close']) / df_block['pre_close'] * 100).round(2)
            else:
                df_block['discount'] = 0
            
            # 选择字段
            cols = ['ts_code', 'name', 'price', 'vol', 'amount', 'buyer', 'seller', 'discount']
            available_cols = [c for c in cols if c in df_block.columns]
            df_block = df_block[available_cols]
            
            # 排序
            df_block = df_block.sort_values('amount', ascending=False).head(20)
            
            result = {
                'date': trade_date,
                'count': len(df_block),
                'list': df_block.to_dict('records')
            }
        else:
            result = {
                'date': trade_date,
                'count': 0,
                'list': []
            }
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"获取大宗交易失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@market_intelligence_bp.route('/api/market/intelligence/margin', methods=['GET'])
def get_margin_data():
    """融资融券数据"""
    try:
        trade_date = request.args.get('date', get_latest_trade_date())
        
        df_margin = get_margin(trade_date)
        
        # 获取股票名称映射
        stock_list = get_stock_list()
        name_map = dict(zip(stock_list['ts_code'], stock_list['name'])) if not stock_list.empty else {}
        
        if not df_margin.empty:
            df_margin['name'] = df_margin['ts_code'].map(name_map)
            
            # 计算融资融券余额
            if 'rzye' in df_margin.columns and 'rqye' in df_margin.columns:
                df_margin['rzrqye'] = df_margin['rzye'] + df_margin['rqye']
            
            # 计算余额变化
            if 'rzye' in df_margin.columns:
                # 简化处理，假设有昨日数据
                df_margin['change'] = 0
            
            # 选择字段
            cols = ['ts_code', 'name', 'rzye', 'rqye', 'rzrqye', 'change']
            available_cols = [c for c in cols if c in df_margin.columns]
            df_margin = df_margin[available_cols]
            
            # 排序
            df_margin = df_margin.sort_values('rzrqye', ascending=False).head(20)
            
            # 计算总额
            total_balance = float(df_margin['rzrqye'].sum()) if 'rzrqye' in df_margin.columns else 0
            
            result = {
                'date': trade_date,
                'balance': total_balance,
                'list': df_margin.to_dict('records')
            }
        else:
            result = {
                'date': trade_date,
                'balance': 0,
                'list': []
            }
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"获取融资融券失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ==================== 新闻资讯 API ====================

@market_intelligence_bp.route('/api/market/intelligence/news', methods=['GET'])
def get_news_list():
    """获取财经新闻列表（新版 - 整合多源）"""
    try:
        # 获取请求参数
        sources = request.args.get('sources', '')  # 逗号分隔的新闻源
        limit = int(request.args.get('limit', 50))
        keyword = request.args.get('keyword', '')
        category = request.args.get('category', '')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        
        # 解析新闻源
        sources_list = [s.strip() for s in sources.split(',') if s.strip()] if sources else []
        
        # 调用新闻服务
        result = fetch_news(
            sources=sources_list,
            limit=limit,
            keyword=keyword,
            category=category,
            start_date=start_date,
            end_date=end_date
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"获取新闻失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@market_intelligence_bp.route('/api/market/intelligence/news/sources', methods=['GET'])
def get_news_sources_info():
    """获取支持的新闻源列表"""
    try:
        sources = get_news_sources()
        return jsonify({
            "success": True,
            "data": sources
        })
    except Exception as e:
        logger.error(f"获取新闻源列表失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@market_intelligence_bp.route('/api/market/intelligence/news/refresh', methods=['POST'])
def refresh_news_cache():
    """刷新新闻缓存"""
    try:
        result = clear_news_cache()
        return jsonify(result)
    except Exception as e:
        logger.error(f"刷新缓存失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# 保留旧版API以兼容
@market_intelligence_bp.route('/api/market/intelligence/news/legacy', methods=['GET'])
def get_news_list_legacy():
    """获取财经新闻列表（旧版 - 兼容）"""
    try:
        channel = request.args.get('channel', 'all')  # all, fund, stock, macro
        limit = int(request.args.get('limit', 50))
        
        # 根据频道获取新闻
        if channel == 'fund':
            df_news = get_fund_news()
        elif channel == 'stock':
            df_news = get_stock_news()
        elif channel == 'macro':
            df_news = get_macro_news()
        else:
            df_news = get_news()
        
        # 如果API返回空数据，使用模拟数据
        if df_news.empty or len(df_news) == 0:
            df_news = get_mock_news(channel, limit)
        
        if not df_news.empty:
            # 选择关键字段并排序
            cols = ['datetime', 'title', 'content', 'source', 'url']
            available_cols = [c for c in cols if c in df_news.columns]
            df_news = df_news[available_cols]
            
            # 限制数量
            df_news = df_news.head(limit)
            
            result = {
                'channel': channel,
                'count': len(df_news),
                'list': df_news.to_dict('records')
            }
        else:
            result = {
                'channel': channel,
                'count': 0,
                'list': []
            }
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"获取新闻失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


def get_mock_news(channel, limit):
    """获取模拟新闻数据（当API不可用时）"""
    import random
    from datetime import datetime, timedelta
    
    # 财经新闻模板
    news_templates = {
        'all': [
            ("A股三大指数今日涨跌不一，成交量明显放大", "证券时报", "https://example.com/1"),
            ("央行：继续保持流动性合理充裕", "第一财经", "https://example.com/2"),
            ("新能源板块持续活跃，多只个股涨停", "上海证券报", "https://example.com/3"),
            ("半导体行业复苏信号明显，机构看好", "中国证券报", "https://example.com/4"),
            ("外资持续流入A股市场", "华尔街日报", "https://example.com/5"),
            ("科创板上市公司业绩普遍预增", "证券日报", "https://example.com/6"),
            ("消费复苏带动零售业增长", "经济参考报", "https://example.com/7"),
            ("人工智能应用加速落地", "科技日报", "https://example.com/8"),
        ],
        'stock': [
            ("年报披露季来临，绩优股受关注", "证券时报", "https://example.com/s1"),
            ("龙虎榜：机构买入这些股", "第一财经", "https://example.com/s2"),
            ("上市公司回购股份热情高涨", "上海证券报", "https://example.com/s3"),
            ("科创板股票持续走强", "中国证券报", "https://example.com/s4"),
            ("ST股票风险警示", "证券日报", "https://example.com/s5"),
        ],
        'fund': [
            ("公募基金规模突破30万亿", "中国基金报", "https://example.com/f1"),
            ("权益类基金发行回暖", "上海证券报", "https://example.com/f2"),
            ("ETF基金持续净流入", "证券时报", "https://example.com/f3"),
            ("私募基金仓位有所提升", "第一财经", "https://example.com/f4"),
        ],
        'macro': [
            ("GDP增速符合预期", "统计局", "https://example.com/m1"),
            ("CPI温和上涨", "中国证券报", "https://example.com/m2"),
            ("进出口数据表现亮眼", "海关总署", "https://example.com/m3"),
            ("制造业PMI保持在扩张区间", "统计局", "https://example.com/m4"),
        ]
    }
    
    templates = news_templates.get(channel, news_templates['all'])
    
    # 随机选择新闻
    selected = random.sample(templates, min(limit, len(templates)))
    
    # 生成数据
    data = []
    base_time = datetime.now()
    for i, (title, source, url) in enumerate(selected):
        data.append({
            'datetime': (base_time - timedelta(hours=i*2)).strftime('%Y-%m-%d %H:%M:%S'),
            'title': title,
            'content': '',
            'source': source,
            'url': url
        })
    
    return pd.DataFrame(data)


@market_intelligence_bp.route('/api/market/intelligence/news/ai-analysis', methods=['POST'])
def get_news_ai_analysis():
    """AI新闻分析"""
    try:
        data = request.json or {}
        news_list = data.get('news', [])
        
        if not news_list:
            return jsonify({
                "success": False,
                "message": "没有新闻数据可供分析"
            }), 400
        
        # 提取新闻标题和摘要
        news_titles = [news.get('title', '') for news in news_list[:20]]
        news_text = "\n".join([f"{i+1}. {title}" for i, title in enumerate(news_titles)])
        
        # 构建分析提示词
        prompt = f"""
请分析以下财经新闻标题，总结当前市场关注的主要热点和趋势：

【新闻标题】
{news_text}

请提供：
1. **市场热点分析** - 当前市场最关注的3-5个话题
2. **板块机会** - 可能受益的相关板块
3. **风险提示** - 需要注意的风险点
4. **投资建议** - 短期操作建议

请用简洁的中文回答。
"""
        
        # 这里可以接入AI模型进行分析
        # 暂时返回基于规则的简单分析
        analysis = {
            "hot_topics": [
                "新能源板块持续受关注",
                "半导体行业复苏预期",
                "消费复苏趋势明显"
            ],
            "opportunity_sectors": [
                "新能源汽车",
                "人工智能",
                "医药生物"
            ],
            "risks": [
                "外围市场波动",
                "政策不确定性"
            ],
            "suggestion": "建议关注业绩确定性强的优质标的，保持谨慎乐观",
            "ai_analysis": prompt  # 可用于调用AI模型
        }
        
        return jsonify({
            "success": True,
            "data": analysis
        })
        
    except Exception as e:
        logger.error(f"AI新闻分析失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ==================== 增强版AI分析 API ====================

@market_intelligence_bp.route('/api/market/intelligence/news/ai-analysis/enhanced', methods=['POST'])
def get_news_ai_analysis_enhanced():
    """增强版AI新闻分析 - 支持更多分析维度"""
    try:
        data = request.json or {}
        news_list = data.get('news', [])
        analysis_type = data.get('type', 'comprehensive')  # comprehensive, sentiment, sectors, risk
        
        if not news_list:
            return jsonify({
                "success": False,
                "message": "没有新闻数据可供分析"
            }), 400
        
        # 提取新闻信息
        news_titles = [news.get('title', '') for news in news_list[:30]]
        news_text = "\n".join([f"{i+1}. {title}" for i, title in enumerate(news_titles)])
        
        # 构建分析提示词
        prompt = f"""
请作为专业的财经分析师，分析以下新闻标题：

【新闻标题】
{news_text}

请提供{f'【{analysis_type}】' if analysis_type != 'comprehensive' else ''}分析：
"""
        
        # 基于规则的分析（可替换为真实的AI调用）
        analysis = _generate_analysis(news_list, analysis_type)
        
        return jsonify({
            "success": True,
            "data": analysis
        })
        
    except Exception as e:
        logger.error(f"增强版AI分析失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


def _generate_analysis(news_list: List[Dict], analysis_type: str = 'comprehensive') -> Dict:
    """基于规则生成分析结果"""
    
    # 提取关键词
    all_text = ' '.join([news.get('title', '') for news in news_list])
    
    # 定义关键词映射
    sector_keywords = {
        '新能源': ['新能源', '光伏', '风电', '锂电池', '电动车', '比亚迪', '宁德'],
        '科技': ['科技', '半导体', '芯片', '人工智能', 'AI', '5G', '软件'],
        '医药': ['医药', '医疗', '生物', '疫苗', '创新药', '中药'],
        '消费': ['消费', '食品', '饮料', '白酒', '家电', '零售', '旅游'],
        '金融': ['银行', '保险', '证券', '金融', '券商', '信托'],
        '地产': ['房地产', '地产', '房产', '建筑', '建材', '万科', '恒大'],
        '军工': ['军工', '航天', '航空', '国防', '船舶'],
        '基建': ['基建', '工程', '机械', '水泥', '钢铁', '煤炭']
    }
    
    sentiment_keywords = {
        'positive': ['上涨', '增长', '利好', '突破', '创新高', '业绩增长', '盈利', '增长', '看好', '加仓'],
        'negative': ['下跌', '风险', '亏损', '利空', '减持', '爆雷', '违约', '调查', '质疑'],
        'neutral': ['持平', '平稳', '震荡', '观望', '中性']
    }
    
    # 统计板块热度
    sector_scores = {}
    for sector, keywords in sector_keywords.items():
        score = sum(1 for kw in keywords if kw in all_text)
        if score > 0:
            sector_scores[sector] = score
    
    # 统计情感
    sentiment_scores = {'positive': 0, 'negative': 0, 'neutral': 0}
    for news in news_list:
        title = news.get('title', '')
        for sent, s_keywords in sentiment_keywords.items():
            if any(kw in title for kw in s_keywords):
                sentiment_scores[sent] += 1
    
    total = sum(sentiment_scores.values()) or 1
    sentiment_result = {
        'positive': round(sentiment_scores['positive'] / total * 100, 1),
        'negative': round(sentiment_scores['negative'] / total * 100, 1),
        'neutral': round(sentiment_scores['neutral'] / total * 100, 1)
    }
    
    # 判断整体情绪
    if sentiment_result['positive'] > 40:
        overall = '乐观'
    elif sentiment_result['negative'] > 30:
        overall = '谨慎'
    else:
        overall = '中性'
    
    # 构建分析结果
    if analysis_type == 'sentiment':
        return {
            'sentiment': overall,
            'scores': sentiment_result,
            'summary': _get_sentiment_summary(sentiment_result)
        }
    
    elif analysis_type == 'sectors':
        top_sectors = sorted(sector_scores.items(), key=lambda x: x[1], reverse=True)[:5]
        return {
            'hot_sectors': [{'name': s[0], 'score': s[1]} for s in top_sectors],
            'summary': _get_sector_summary(top_sectors)
        }
    
    elif analysis_type == 'risk':
        risks = _extract_risks(news_list)
        return {
            'risks': risks,
            'risk_level': '高' if len(risks) > 3 else '中' if len(risks) > 1 else '低'
        }
    
    else:  # comprehensive
        return {
            'sentiment': overall,
            'sentiment_scores': sentiment_result,
            'hot_sectors': [{'name': s[0], 'score': s[1]} for s in sorted(sector_scores.items(), key=lambda x: x[1], reverse=True)[:5]],
            'hot_topics': _extract_hot_topics(news_list),
            'risks': _extract_risks(news_list),
            'opportunities': _extract_opportunities(sector_scores),
            'suggestion': _get_suggestion(overall, sector_scores),
            'summary': _generate_summary(overall, sector_scores, sentiment_result)
        }


def _get_sentiment_summary(scores: Dict) -> str:
    """生成情感摘要"""
    if scores['positive'] > 40:
        return "市场情绪偏向积极正面，利多消息较多。"
    elif scores['negative'] > 30:
        return "市场情绪相对谨慎，利空消息需要关注。"
    else:
        return "市场情绪中性，多空力量相对平衡。"


def _get_sector_summary(sectors: List) -> str:
    """生成板块摘要"""
    if not sectors:
        return "暂无明显热点板块"
    top = ', '.join([s[0] for s in sectors[:3]])
    return f"当前市场热点集中在：{top}等板块"


def _extract_hot_topics(news_list: List[Dict]) -> List[str]:
    """提取热点话题"""
    topics = []
    keywords = ['新能源', '半导体', 'AI', '人工智能', '医药', '消费', '银行', '地产', '军工', '5G']
    for news in news_list:
        title = news.get('title', '')
        for kw in keywords:
            if kw in title and kw not in topics:
                topics.append(kw)
                if len(topics) >= 5:
                    break
    return topics


def _extract_risks(news_list: List[Dict]) -> List[Dict]:
    """提取风险提示"""
    risk_keywords = ['风险', '利空', '下跌', '亏损', '减持', '调查', '爆雷', '违约', '退市']
    risks = []
    for news in news_list[:10]:
        title = news.get('title', '')
        for kw in risk_keywords:
            if kw in title:
                risks.append({
                    'title': title,
                    'type': kw
                })
                break
    return risks[:5]


def _extract_opportunities(sector_scores: Dict) -> List[str]:
    """提取机会板块"""
    return [s[0] for s in sorted(sector_scores.items(), key=lambda x: x[1], reverse=True)[:3]]


def _get_suggestion(sentiment: str, sectors: Dict) -> str:
    """生成投资建议"""
    if sentiment == '乐观':
        base = "市场情绪积极，可适度参与。"
    elif sentiment == '谨慎':
        base = "建议保持谨慎，控制仓位。"
    else:
        base = "建议观望为主，等待方向明确。"
    
    if sectors:
        top_sector = max(sectors.items(), key=lambda x: x[1])[0]
        base += f"可关注{top_sector}板块。"
    
    return base


def _generate_summary(sentiment: str, sectors: Dict, sentiment_scores: Dict) -> str:
    """生成综合摘要"""
    parts = []
    
    # 情绪
    if sentiment == '乐观':
        parts.append("市场情绪偏暖")
    elif sentiment == '谨慎':
        parts.append("市场情绪谨慎")
    else:
        parts.append("市场情绪中性")
    
    # 板块
    if sectors:
        top = max(sectors.items(), key=lambda x: x[1])[0]
        parts.append(f"{top}板块热度最高")
    
    # 资金
    if sentiment_scores['positive'] > sentiment_scores['negative']:
        parts.append("整体氛围偏多")
    else:
        parts.append("注意风险防控")
    
    return "，".join(parts) + "。"


@market_intelligence_bp.route('/api/market/intelligence/news/ai-analysis/chat', methods=['POST'])
def news_ai_chat():
    """AI新闻智能问答"""
    try:
        data = request.json or {}
        question = data.get('question', '')
        news_list = data.get('news', [])
        
        if not question:
            return jsonify({
                "success": False,
                "message": "请输入问题"
            }), 400
        
        # 提取新闻信息
        news_text = '\n'.join([f"- {news.get('title', '')}" for news in news_list[:20]])
        
        # 生成回答（这里可以接入真实的AI模型）
        answer = _generate_chat_answer(question, news_list)
        
        return jsonify({
            "success": True,
            "data": {
                "question": question,
                "answer": answer,
                "sources": [news.get('title', '')[:50] for news in news_list[:3]]
            }
        })
        
    except Exception as e:
        logger.error(f"AI问答失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


def _generate_chat_answer(question: str, news_list: List[Dict]) -> str:
    """生成问答回答"""
    question = question.lower()
    
    if any(k in question for k in ['热点', '热点话题', '最关注', '热门']):
        topics = _extract_hot_topics(news_list)
        return f"当前市场热点话题主要集中在：{', '.join(topics)}等。建议关注相关板块的持续表现。"
    
    elif any(k in question for k in ['板块', '行业', '机会']):
        sectors = {}
        sector_keywords = {
            '新能源': ['新能源', '光伏', '风电', '电动车'],
            '科技': ['科技', '半导体', '芯片', 'AI', '人工智能'],
            '医药': ['医药', '医疗', '生物'],
            '消费': ['消费', '食品', '饮料', '白酒']
        }
        all_text = ' '.join([n.get('title', '') for n in news_list])
        for sector, keywords in sector_keywords.items():
            sectors[sector] = sum(1 for kw in keywords if kw in all_text)
        
        top = max(sectors.items(), key=lambda x: x[1])[0] if sectors else "暂无明确"
        return f"从近期新闻来看，{top}板块是市场关注的重点。建议关注行业龙头和业绩确定性强的标的。"
    
    elif any(k in question for k in ['风险', '注意', '谨慎']):
        risks = _extract_risks(news_list)
        if risks:
            return f"需要关注的风险点包括：{'；'.join([r['title'] for r in risks[:3]])}。建议控制仓位，谨慎操作。"
        return "当前新闻中未发现明显风险提示，但仍建议保持谨慎。"
    
    elif any(k in question for k in ['建议', '操作', '投资']):
        return "基于当前新闻分析，建议关注业绩确定性强的优质标的，保持适度仓位。注意分散投资风险。"
    
    else:
        return "您可以问我关于市场热点、板块机会、风险提示、投资建议等方面的问题。"
