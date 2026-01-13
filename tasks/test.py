from exchange_calendars import get_calendar
cal = get_calendar("XSHG")
print(cal.schedule.index[-5:])  # 查看最后几个交易日