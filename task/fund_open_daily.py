import akshare as ak
import pandas as pd
from sqlalchemy import create_engine
import sys
from config.mysql_config import *
from config.logging_config import logger


def fund_open_synchronization():
    # ========================
    # 配置参数
    # ========================
    SYMBOL = "全部"  # 可选: "全部", "股票型", "混合型", "债券型", "指数型", "QDII", "FOF"
    DB_URI = f"mysql+pymysql://{MYSQL_CONFIG['user']}:{MYSQL_CONFIG['password']}@" \
             f"{MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}/{MYSQL_CONFIG['database']}?charset=utf8mb4"

    TABLE_NAME = "fund_open_rank_all"

    # ========================
    # 1. 获取数据
    # ========================
    try:
        logger.info(f"正在获取 {SYMBOL} 开放式基金排行数据...")
        df = ak.fund_open_fund_rank_em(symbol=SYMBOL)
        logger.info(f"成功获取 {len(df)} 条记录。")
    except Exception as e:
        logger.error(f"❌ 获取数据失败: {e}")
        sys.exit(1)

    if df.empty:
        logger.warning("⚠️ 未返回任何数据，程序退出。")
        sys.exit(0)

    # ========================
    # 2. 列名映射为英文（snake_case）
    # ========================
    column_mapping = {
        '序号': 'rank',
        '基金代码': 'fund_code',
        '基金简称': 'fund_name',
        '单位净值': 'net_value',
        '累计净值': 'accumulated_net_value',
        '日增长率': 'daily_growth_rate',
        '近1周': 'weekly_growth_rate',
        '近1月': 'monthly_1_growth_rate',
        '近3月': 'monthly_3_growth_rate',
        '近6月': 'monthly_6_growth_rate',
        '近1年': 'yearly_1_growth_rate',
        '近2年': 'yearly_2_growth_rate',
        '近3年': 'yearly_3_growth_rate',
        '今年来': 'ytd_growth_rate',
        '成立来': 'since_inception_growth_rate',
        '自定义': 'custom_growth_rate',
        '手续费': 'fee_rate'
    }

    # 检查所有预期列是否存在
    missing_cols = [col for col in column_mapping.keys() if col not in df.columns]
    if missing_cols:
        logger.error(f"缺失列: {missing_cols}")
        sys.exit(1)

    # 重命名列
    df = df.rename(columns=column_mapping)

    # ========================
    # 3. 数据清洗与标准化
    # ========================
    # 百分比字段列表（需去除 '%' 并转为 float）
    pct_columns = [
        'daily_growth_rate', 'weekly_growth_rate', 'monthly_1_growth_rate',
        'monthly_3_growth_rate', 'monthly_6_growth_rate', 'yearly_1_growth_rate',
        'yearly_2_growth_rate', 'yearly_3_growth_rate', 'ytd_growth_rate',
        'since_inception_growth_rate', 'custom_growth_rate'
    ]

    for col in pct_columns:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace('%', '', regex=False)
                .str.strip()
                .replace(['---', '', 'None', 'nan'], pd.NA)
                .astype(float, errors='ignore')  # 保留无法转换的为 NaN
            )

    # 手续费处理（如 "0.15%" -> 0.15）
    if 'fee_rate' in df.columns:
        df['fee_rate'] = (
            df['fee_rate']
            .astype(str)
            .str.replace('%', '', regex=False)
            .str.strip()
            .replace(['', 'None', 'nan'], pd.NA)
            .astype(float, errors='ignore')
        )

    # 添加抓取时间（用于标识数据批次）
    df['update_time'] = pd.Timestamp.now()

    # ✅ 新增：添加 is_checked 列，默认 False
    df['is_checked'] = False

    # 确保关键列为字符串类型（避免科学计数法）
    df['fund_code'] = df['fund_code'].astype(str)
    df['fund_name'] = df['fund_name'].astype(str)

    # ========================
    # 4. 写入 MySQL
    # ========================
    try:
        engine = create_engine(DB_URI, echo=False)
        df.to_sql(
            name=TABLE_NAME,
            con=engine,
            if_exists='replace',  # 或 'append'，根据需求调整
            index=False,
            method='multi',
            chunksize=1000
        )
        logger.info(f"✅ 成功将 {len(df)} 条记录写入 MySQL 表 `{TABLE_NAME}`。")
    except Exception as e:
        logger.error(f"❌ 写入数据库失败: {e}")
        sys.exit(1)





if __name__ == "__main__":
    fund_open_synchronization()