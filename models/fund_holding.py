# models/fund_holding.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class FundHolding(db.Model):
    __tablename__ = 'fund_holdings'
    id = db.Column(db.BigInteger, primary_key=True)
    fund_code = db.Column(db.String(10), nullable=False)
    stock_code = db.Column(db.String(10), nullable=False)
    stock_name = db.Column(db.String(50), nullable=False)
    proportion_of_nav = db.Column(db.DECIMAL(5, 2))
    shares_held = db.Column(db.DECIMAL(12, 2))
    market_value = db.Column(db.DECIMAL(14, 2))
    quarter = db.Column(db.String(20), nullable=False)
    report_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('fund_code', 'stock_code', 'quarter', name='uk_fund_stock_quarter'),
    )

    def to_dict(self):
        return {
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'proportion_of_nav': float(self.proportion_of_nav) if self.proportion_of_nav else None,
            'shares_held': float(self.shares_held) if self.shares_held else None,
            'market_value': float(self.market_value) if self.market_value else None,
            'quarter': self.quarter
        }