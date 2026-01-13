import akshare as ak
import pandas as pd
from sqlalchemy import create_engine, text
import logging
from config.mysql_config import *
from config.logging_config import logger

# 构建数据库连接 URL
DB_URI = f"mysql+pymysql://{MYSQL_CONFIG['user']}:{MYSQL_CONFIG['password']}@" \
         f"{MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}/{MYSQL_CONFIG['database']}?charset=utf8mb4"

TABLE_NAME = "fund_basic_info"

engine = create_engine(DB_URI, echo=False)

# ====== 创建表结构 ======
def create_table_if_not_exists():
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS fund_basic (
        fund_code VARCHAR(20) PRIMARY KEY COMMENT '基金代码',
        pinyin_abbr VARCHAR(100) COMMENT '拼音缩写',
        fund_name VARCHAR(255) COMMENT '基金简称',
        fund_type VARCHAR(100) COMMENT '基金类型',
        pinyin_full VARCHAR(255) COMMENT '拼音全称',
        update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    with engine.connect() as conn:
        conn.execute(text(create_table_sql))
        conn.commit()
    logger.info(f"数据表 {TABLE_NAME} 已确保存在。")

# ====== 获取并清洗数据 ======
def fetch_fund_data():
    logger.info("正在从东方财富网获取基金基本信息...")
    try:
        df = ak.fund_name_em()
    except Exception as e:
        logger.error(f"获取基金数据失败: {e}")
        raise

    # 检查必要列
    required_columns = ['基金代码', '拼音缩写', '基金简称', '基金类型', '拼音全称']
    if not all(col in df.columns for col in required_columns):
        raise ValueError("返回数据缺少必要字段")

    # 重命名列以匹配数据库
    df = df[required_columns].rename(columns={
        '基金代码': 'fund_code',
        '拼音缩写': 'pinyin_abbr',
        '基金简称': 'fund_name',
        '基金类型': 'fund_type',
        '拼音全称': 'pinyin_full'
    })

    # 去除空值（可选）
    df = df.dropna(subset=['fund_code']).reset_index(drop=True)
    df['update_time'] = pd.Timestamp.now()
    logger.info(f"成功获取 {len(df)} 条基金数据。")
    return df

# ====== 写入数据库 ======
def write_to_mysql(df):
    logger.info("正在写入 MySQL 数据库...")
    try:
        # 使用 ON DUPLICATE KEY UPDATE 实现“存在则更新，否则插入”
        # 注意：fund_code 是主键
        df.to_sql(
            name=TABLE_NAME,
            con=engine,
            if_exists='replace',
            index=False,
            method='multi'  # 批量插入
        )
        logger.info(f"数据成功写入 MySQL 表 {TABLE_NAME}。")
    except Exception as e:
        logger.error(f"写入 MySQL 表 `{TABLE_NAME}失败: {e}")
        raise

# ====== 主函数 ======
def fund_basic_info_synchronization():
    try:
        create_table_if_not_exists()
        df = fetch_fund_data()
        write_to_mysql(df)
    except Exception as e:
        logger.error(f"程序运行出错: {e}")
        exit(1)




if __name__ == "__main__":
    fund_basic_info_synchronization()