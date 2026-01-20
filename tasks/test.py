import akshare as ak

# 获取所有可估算的基金（约 5000+ 只）
df = ak.fund_value_estimation_em(symbol="全部")


fund_code = "022364"

# 筛选
result = df[df["基金代码"] == fund_code]

if not result.empty:
    estimation = result.iloc[0]
    print(f"基金 {fund_code} 有估值数据:")
    print(f"  估算净值: {estimation['2026-01-20-估算数据-估算值']}")
    print(f"  估算增长率: {estimation['2026-01-20-估算数据-估算增长率']}")
else:
    print(f"基金 {fund_code} 当前无估值数据（可能不支持估算或未更新）")