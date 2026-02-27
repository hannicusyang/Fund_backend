# config/tushare_config.py
# Tushare API 配置

# Tushare Token - 用户提供
TUSHARE_TOKEN = '05c7d22cd91b035422630b2f289e9ad6f5ad1e8aba604e8b4648baa9'

# 积分级别（需要120积分才能用日线，2000积分才能用每日指标）
# 当前用户权限不足，无法获取股票行情数据
TUSHARE_AVAILABLE = False  # 当积分足够时设为 True
