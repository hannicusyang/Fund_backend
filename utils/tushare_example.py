# utils/tushare_example.py
# Tushare 绕过积分限制的示例（使用第三方代理）

import tushare as ts

# 初始化 pro_api（token可以随意填写，会被下面覆盖）
pro = ts.pro_api('此处不用改')

# ⬇️⬇️找到 pro_api 所在行，添加两行代码 ⬇️⬇️
pro._DataApi__token = '4502105893002009438'
pro._DataApi__http_url = 'http://5k1a.xiximiao.com/dataapi'
# ⬆️⬆️添加两行代码⬆️⬆️

# 【❗💡💡 同理，在你已有代码中，搜索 pro_api 所在行，随后在pro_api添加以上两行】

# ---- daily 日线接口 ----
df = pro.daily(trade_date='20180810', limit=20)
print(df)

# --- 交易日历 ---
df_cal = pro.trade_cal(exchange='', start_date='20250101', end_date='20251231', limit=5, offset=0)
print(df_cal)

# ------ 5000积分接口验证 ------
# dfkpl_concept_cons = pro.kpl_concept_cons(trade_date='20241014')
# print(dfkpl_concept_cons)

# ------ 10000积分接口验证 ------
# dflimit_list_ths = pro.limit_list_ths(trade_date='20241125', limit_type='涨停池', fields='ts_code,trade_date,tag,status,lu_desc')
# print(dflimit_list_ths)

# df_stock_basic = pro.stock_basic(limit=6000, offset=0)
# {集合竞价接口.与积分无关,需stk_mins独立权限}
# df = pro.stk_auction_o(trade_date='20251204')
