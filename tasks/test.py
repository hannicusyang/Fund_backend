# 导入tushare
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.tushare_api import get_pro

import akshare as ak

stock_zh_kcb_spot_df = ak.stock_zh_kcb_spot()
print(stock_zh_kcb_spot_df)