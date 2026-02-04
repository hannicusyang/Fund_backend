import akshare as ak

stock_szse_sector_summary_df = ak.stock_szse_sector_summary(symbol="当月", date="202601")
print(stock_szse_sector_summary_df)