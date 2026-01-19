from sqlalchemy import Column, VARCHAR, BigInteger, DateTime, DECIMAL, text
from models import db  # 确保路径正确


class MyFundHolding(db.Model):
    __tablename__ = 'my_fund_holding'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'fund_code', name='uk_user_fund_holding'),
        db.Index('idx_user_id', 'user_id'),
        db.Index('idx_fund_code', 'fund_code'),
        {'comment': '用户基金持仓明细'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        VARCHAR(36),
        nullable=False,
        default='default',
        comment="用户ID"
    )
    fund_code = Column(
        VARCHAR(10),
        nullable=False,
        comment="基金代码"
    )

    # 持仓核心字段：默认为 0，且不允许 NULL
    cost_price = Column(
        DECIMAL(18, 4),
        nullable=False,
        default=0,
        comment="持仓成本单价"
    )
    shares = Column(
        DECIMAL(18, 4),
        nullable=False,
        default=0,
        comment="持仓份额"
    )
    total_cost = Column(
        DECIMAL(18, 4),
        nullable=False,
        default=0,
        comment="持仓总成本（= cost_price * shares）"
    )

    purchased_at = Column(
        DateTime,
        nullable=False,
        comment="首次买入时间"
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=text('CURRENT_TIMESTAMP'),
        onupdate=text('CURRENT_TIMESTAMP'),
        comment="最后更新时间"
    )