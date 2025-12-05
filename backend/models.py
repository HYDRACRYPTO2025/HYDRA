from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from .db import Base


class Token(Base):
    __tablename__ = "tokens"

    id = Column(Integer, primary_key=True, index=True)
    chain = Column(String(50), index=True, nullable=False)   # сеть: BSC, ETH, SOL и т.д.
    address = Column(String(100), index=True, nullable=False)
    symbol = Column(String(50), nullable=True)
    name = Column(String(100), nullable=True)

    is_deleted = Column(Boolean, default=False)              # админ может пометить как удалённый
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
