from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func

from .db import Base


class Token(Base):
    """
    Таблица токенов.
    Храним здесь всё, что нужно для запросов к биржам/DEX'ам.
    """
    __tablename__ = "tokens"

    id = Column(Integer, primary_key=True, index=True)
    # Отображаемое имя/пара, например "SOL-USDT"
    name = Column(String(64), unique=True, index=True, nullable=False)

    base = Column(String(32), nullable=False)
    quote = Column(String(32), nullable=False, default="USDT")

    # Параметры для MEXC / Jupiter / Pancake / Matcha
    mexc_price_scale = Column(Integer, nullable=True)

    jupiter_mint = Column(String(128), nullable=True)
    jupiter_decimals = Column(Integer, nullable=True)

    bsc_address = Column(String(128), nullable=True)

    matcha_address = Column(String(128), nullable=True)
    matcha_decimals = Column(Integer, nullable=True)

    cg_id = Column(String(128), nullable=True)  # CoinGecko id для капитализации M

    dexes = Column(String(256), nullable=True)  # пока просто строка с перечислением

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Proxy(Base):
    """
    Таблица прокси. Позже добавим эндпоинты,
    чтобы админ мог добавлять/удалять прокси.
    """
    __tablename__ = "proxies"

    id = Column(Integer, primary_key=True, index=True)
    # Формат: socks5://user:pass@ip:port или http://ip:port
    url = Column(String(256), unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    note = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
