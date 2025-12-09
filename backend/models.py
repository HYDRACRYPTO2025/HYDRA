from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey
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
    url = Column(String(256 ), unique=True, nullable=False)
    protocol = Column(String(16), nullable=False, default="socks5")  # http, https, socks5
    is_active = Column(Boolean, default=True )
    note = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AccessToken(Base):
    """
    Таблица токенов доступа для десктоп-приложений.
    Каждый токен дает доступ к API.
    """
    __tablename__ = "access_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(256), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=True)  # описание токена
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)


class AdminUser(Base):
    """
    Таблица администраторов для админ-панели.
    """
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PriceHistory(Base):
    """
    Таблица истории цен для каждой пары токенов.
    Сохраняет исторические данные цен, чтобы показывать графики.
    Данные сохраняются при каждом запросе цены из приложения.
    """
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    token_id = Column(Integer, nullable=False, index=True)  # ссылка на tokens.id
    
    # Цены с разных источников
    mexc_bid = Column(Float, nullable=True)
    mexc_ask = Column(Float, nullable=True)
    matcha_price = Column(Float, nullable=True)
    pancake_price = Column(Float, nullable=True)
    
    # Дополнительные данные
    spread = Column(Float, nullable=True)  # спред между bid и ask
    
    # Время создания записи
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
