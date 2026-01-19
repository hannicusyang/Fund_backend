# models/trading_day.py
from datetime import date
from . import db

class TradingDay(db.Model):
    __tablename__ = 'trading_day'

    trade_date = db.Column(db.Date, primary_key=True, nullable=False)

    def __repr__(self):
        return f"<TradingDay {self.trade_date}>"