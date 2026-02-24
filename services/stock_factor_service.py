# services/stock_factor_service.py
# 股票因子服务 - 多因子选股

from models import db
from models.factor_definition import ScreeningStrategy
from models.stock_screening import StockScreeningData
from services.factor_library import FACTOR_CATEGORIES, QUICK_FILTERS
from sqlalchemy import or_, and_, func, cast
from sqlalchemy.types import Float
from datetime import datetime
import pandas as pd
import numpy as np


class StockFactorService:
    """股票因子服务"""
    
    @classmethod
    def get_factor_definitions(cls):
        """获取所有因子定义"""
        result = {}
        for category_key, category in FACTOR_CATEGORIES.items():
            result[category_key] = {}
            for factor in category['factors']:
                result[category_key][factor['key']] = {
                    'min': factor['min'],
                    'max': factor['max'],
                    'default': [factor['defaultMin'], factor['defaultMax']]
                }
        return result
    
    @classmethod
    def get_quick_filters(cls):
        """获取快捷筛选预设"""
        result = []
        for key, filter_data in QUICK_FILTERS.items():
            result.append({
                'key': key,
                'name': filter_data['name'],
                'icon': filter_data['icon'],
                'description': filter_data['description'],
                'factors': filter_data['factors']
            })
        return result
    
    @classmethod
    def screen_stocks(cls, filters, sort_by='change_20d', sort_order='desc', 
                      page=1, page_size=20):
        """多因子选股筛选"""
        try:
            # 获取最新交易日
            latest_record = StockScreeningData.query.order_by(
                StockScreeningData.trade_date.desc()
            ).first()
            
            if not latest_record:
                return {'success': False, 'message': '暂无股票数据', 'data': [], 'total': 0}
            
            trade_date = latest_record.trade_date
            
            # 基础查询
            query = StockScreeningData.query.filter(
                StockScreeningData.trade_date == trade_date
            )
            
            # 应用筛选条件
            for factor_key, range_vals in filters.items():
                column = getattr(StockScreeningData, factor_key, None)
                if column is None:
                    print(f"DEBUG: Column {factor_key} not found in model")
                    continue
                
                min_val, max_val = float(range_vals[0]), float(range_vals[1])
                print(f"DEBUG: Filtering {factor_key}: {min_val} <= x <= {max_val}")
                # 筛选: 字段值在指定范围内 (过滤掉NULL值，确保筛选有效)
                query = query.filter(
                    column.isnot(None),
                    column >= min_val,
                    column <= max_val
                )
            
            # 排序 (MySQL不支持NULLS LAST，使用IFNULL处理)
            sort_column = getattr(StockScreeningData, sort_by, StockScreeningData.change_20d)
            from sqlalchemy import case
            if sort_order == 'desc':
                # null值排最后: 如果为null则放在最前面，然后按倒序排
                query = query.order_by(
                    case((sort_column.is_(None), 1), else_=0),
                    sort_column.desc()
                )
            else:
                query = query.order_by(
                    case((sort_column.is_(None), 1), else_=0),
                    sort_column.asc()
                )
            
            # 分页
            offset = (page - 1) * page_size
            results = query.offset(offset).limit(page_size).all()
            
            # 计算总数 (重新查询，不影响上面的结果)
            total = query.count()
            
            # 转换为字典
            stocks_data = [stock.to_dict() for stock in results]
            
            return {
                'success': True,
                'data': stocks_data,
                'total': total,
                'page': page,
                'pageSize': page_size,
                'tradeDate': trade_date.isoformat() if trade_date else None
            }
            
        except Exception as e:
            return {'success': False, 'message': str(e), 'data': [], 'total': 0}
    
    @classmethod
    def save_strategy(cls, user_id, name, description, factor_config, 
                      sort_by='change_20d', sort_order='desc', limit=50):
        """保存筛选策略"""
        try:
            strategy = ScreeningStrategy(
                user_id=user_id,
                strategy_name=name,
                strategy_desc=description,
                factor_config=factor_config,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=limit
            )
            db.session.add(strategy)
            db.session.commit()
            return {'success': True, 'data': strategy.to_dict()}
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'message': str(e)}
    
    @classmethod
    def get_strategies(cls, user_id='default'):
        """获取用户的筛选策略"""
        strategies = ScreeningStrategy.query.filter_by(
            user_id=user_id
        ).order_by(ScreeningStrategy.create_time.desc()).all()
        
        return [s.to_dict() for s in strategies]
    
    @classmethod
    def delete_strategy(cls, strategy_id, user_id='default'):
        """删除策略"""
        try:
            strategy = ScreeningStrategy.query.filter_by(
                id=strategy_id, user_id=user_id
            ).first()
            
            if not strategy:
                return {'success': False, 'message': '策略不存在'}
            
            db.session.delete(strategy)
            db.session.commit()
            return {'success': True}
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'message': str(e)}
