import pandas as pd
import re
import akshare as ak
from sqlalchemy import create_engine, text
from datetime import datetime, date

# === 配置 ===
from config.mysql_config import *
from config.logging_config import *


TABLE_NAME = "fund_estimation"
engine = create_engine(DB_URL, pool_pre_ping=True)

def init_fund_estimation_table():
    """初始化基金估值表"""
    create_sql = f"""
    CREATE TABLE IF NOT EXISTS `{TABLE_NAME}` (
        `fund_code` VARCHAR(20) NOT NULL,
        `fund_name` VARCHAR(255) NOT NULL,
        `estimation_date` DATE NOT NULL COMMENT '估算所针对的日期 (T日)',
        `last_nav_date` DATE COMMENT '上一交易日净值日期 (T-1日)',
        `estimated_nav` DECIMAL(18,6),
        `estimated_growth_rate` DECIMAL(10,4),
        `published_nav` DECIMAL(18,6),
        `published_growth_rate` DECIMAL(10,4),
        `estimation_bias` DECIMAL(10,4),
        `last_nav` DECIMAL(18,6) COMMENT 'T-1日单位净值',
        `fetch_time` DATETIME NOT NULL,
        INDEX idx_fund_code (`fund_code`),
        INDEX idx_estimation_date (`estimation_date`),
        INDEX idx_fetch_time (`fetch_time`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    with engine.connect() as conn:
        conn.execute(text(create_sql))
        conn.commit()
    logger.info("✅ 基金估值表初始化完成")

def is_a_stock_trading_time():
    """判断当前是否为 A 股交易时间（9:30-15:00 且为交易日）"""
    try:
        import exchange_calendars as tc
        calendar = tc.get_calendar("XSHG")
    except ImportError:
        logger.warning("未安装 exchange-calendars，跳过交易日检查")
        return True  # 默认允许抓取

    now = datetime.now()
    today = now.date()
    current_time = now.time()

    if not calendar.is_session(today):
        return False

    market_open = datetime.strptime("09:30", "%H:%M").time()
    market_close = datetime.strptime("15:00", "%H:%M").time()
    return market_open <= current_time <= market_close

def save_estimation_to_mysql(df: pd.DataFrame):
    """清洗并保存数据到 MySQL"""
    if df.empty:
        logger.info("无估值数据，跳过写入")
        return

    df.columns = df.columns.astype(str)
    date_columns = {}
    for col in df.columns:
        match = re.search(r'(\d{4}-\d{2}-\d{2})', col)
        if match:
            d = match.group(1)
            date_columns.setdefault(d, []).append(col)

    if not date_columns:
        logger.error("无法从列名中提取日期")
        return

    t_date = None
    t_minus_1_date = None
    for d, cols in date_columns.items():
        if any('估算数据' in c for c in cols):
            t_date = d
            break
    for d, cols in date_columns.items():
        if any('单位净值' in c and '公布数据' not in c for c in cols):
            t_minus_1_date = d
            break
    if t_minus_1_date is None and len(date_columns) > 1:
        sorted_dates = sorted(date_columns.keys())
        t_minus_1_date = sorted_dates[0]

    new_data = {
        'fund_code': df['基金代码'],
        'fund_name': df['基金名称'],
        'estimation_date': t_date,
        'last_nav_date': t_minus_1_date,
        'estimation_bias': df.get('估算偏差', pd.NA),
        'fetch_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    if t_date:
        new_data['estimated_nav'] = df.get(f'{t_date}-估算数据-估算值', pd.NA)
        new_data['estimated_growth_rate'] = df.get(f'{t_date}-估算数据-估算增长率', pd.NA)
        new_data['published_nav'] = df.get(f'{t_date}-公布数据-单位净值', pd.NA)
        new_data['published_growth_rate'] = df.get(f'{t_date}-公布数据-日增长率', pd.NA)

    if t_minus_1_date:
        last_nav_col = f'{t_minus_1_date}-单位净值'
        if last_nav_col in df.columns:
            new_data['last_nav'] = df[last_nav_col]
        else:
            for col in df.columns:
                if '单位净值' in col and '公布数据' not in col and col not in ['基金代码', '基金名称', '估算偏差']:
                    new_data['last_nav'] = df[col]
                    break

    df_clean = pd.DataFrame(new_data)

    for col in ['estimated_growth_rate', 'published_growth_rate', 'estimation_bias']:
        if col in df_clean.columns:
            df_clean[col] = (
                df_clean[col].astype(str)
                .str.replace('%', '')
                .replace(['---', 'nan', '', 'None'], pd.NA)
            )
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')

    for col in ['estimated_nav', 'published_nav', 'last_nav']:
        if col in df_clean.columns:
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')

    df_clean['fund_code'] = df_clean['fund_code'].astype(str)

    try:
        df_clean.to_sql(TABLE_NAME, con=engine, if_exists='append', index=False, method='multi', chunksize=500)
        logger.info(f"✅ 写入 {len(df_clean)} 条数据 | 估算日: {t_date}")
    except Exception as e:
        logger.error(f"❌ 写入失败: {e}")

def clear_old_estimation_data():
    """清空 fund_estimation 表中非今天的数据"""
    today = date.today().isoformat()  # 格式: '2026-01-12'
    delete_sql = f"DELETE FROM {TABLE_NAME} WHERE estimation_date != :today"
    try:
        with engine.connect() as conn:
            result = conn.execute(text(delete_sql), {"today": today})
            conn.commit()
            if result.rowcount > 0:
                logger.info(f"🧹 已清理 {result.rowcount} 条非今日的旧数据")
            else:
                logger.debug("✅ 无旧数据需要清理")
    except Exception as e:
        logger.error(f"❌ 清理旧数据失败: {e}")

def fetch_and_save_fund_estimation(is_debug=False):
    """主抓取函数"""
    if not is_debug and not is_a_stock_trading_time():
        logger.debug("非交易时间，跳过")
        return

    try:
        # === 关键步骤：先清理非今日的数据 ===
        clear_old_estimation_data()
        logger.info("📡 开始抓取基金估值...")
        df = ak.fund_value_estimation_em(symbol="全部")  # 注意：无 timeout 参数
        save_estimation_to_mysql(df)
    except Exception as e:
        logger.error(f"💥 抓取失败: {e}", exc_info=True)