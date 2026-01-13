import akshare as ak

fund_value_estimation_em_df = ak.fund_value_estimation_em(symbol="全部")

fund_value_estimation_em_df.to_csv('test.csv', index=False)
print(fund_value_estimation_em_df)