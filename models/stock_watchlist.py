from sqlalchemy import Column, BigInteger, String, DateTime, text
from sqlalchemy.dialects.mysql import VARCHAR
from models import db

class StockWatchlist(db.Model):
    __tablename__ = 'stock_watchlist'

    # 表选项（comment）和约束、索引统一放在 __table_args__ 中
    __table_args__ = (
        db.UniqueConstraint('user_id', 'stock_code', name='uk_user_stock'),
        db.Index('idx_added_at', 'added_at'),
        db.Index('idx_stock_code', 'stock_code'),
        db.Index('idx_user_id', 'user_id'),
        {'comment': '用户股票自选清单'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        VARCHAR(36),
        nullable=False,
        default='default',
        comment="用户ID，单用户系统可设为 default"
    )
    stock_code = Column(
        VARCHAR(10),
        nullable=False,
        comment="股票代码，如 000001"
    )
    stock_name = Column(
        VARCHAR(50),
        nullable=True,
        comment="股票名称，如 平安银行"
    )
    added_at = Column(
        DateTime,
        nullable=True,
        default=text('CURRENT_TIMESTAMP'),
        comment="加入时间"
    )
