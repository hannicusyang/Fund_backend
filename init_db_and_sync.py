#!/usr/bin/env python3
# init_db_and_sync.py
# 初始化数据库并同步多因子选股数据

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db
from models.stock_screening import StockScreeningData
from tasks.sync_stock_screening import sync_stock_screening_data


def init_database():
    """初始化数据库表"""
    print("=" * 50)
    print("初始化数据库")
    print("=" * 50)
    
    with app.app_context():
        # 创建表
        db.create_all()
        print("✅ 数据库表创建完成")
        
        # 检查StockScreeningData表
        try:
            count = StockScreeningData.query.count()
            print(f"StockScreeningData 表已有数据: {count} 条")
        except Exception as e:
            print(f"查询失败: {e}")


def run_sync():
    """执行数据同步"""
    print("\n" + "=" * 50)
    print("执行多因子选股数据同步")
    print("=" * 50)
    
    result = sync_stock_screening_data()
    print(f"\n同步结果: {result}")
    return result


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='多因子选股数据管理工具')
    parser.add_argument('--init', action='store_true', help='初始化数据库')
    parser.add_argument('--sync', action='store_true', help='执行数据同步')
    parser.add_argument('--all', action='store_true', help='初始化并同步')
    
    args = parser.parse_args()
    
    if args.all or (not args.init and not args.sync):
        # 默认执行全部
        init_database()
        run_sync()
    else:
        if args.init:
            init_database()
        if args.sync:
            run_sync()
