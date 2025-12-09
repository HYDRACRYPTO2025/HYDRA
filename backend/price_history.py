# backend/price_history.py
"""
Модуль для сохранения и получения истории цен.
"""

from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .models import PriceHistory, Token
from .logic import log


def save_price_history(
    db: Session,
    token_id: int,
    mexc_bid: Optional[float] = None,
    mexc_ask: Optional[float] = None,
    matcha_price: Optional[float] = None,
    pancake_price: Optional[float] = None,
) -> Optional[PriceHistory]:
    """
    Сохранить цены в историю.
    
    Args:
        db: Сессия БД
        token_id: ID токена из таблицы tokens
        mexc_bid: Цена bid на MEXC
        mexc_ask: Цена ask на MEXC
        matcha_price: Цена на Matcha
        pancake_price: Цена на PancakeSwap
    
    Returns:
        Созданная запись PriceHistory или None при ошибке
    """
    try:
        # Вычисляем спред если есть bid и ask
        spread = None
        if mexc_bid is not None and mexc_ask is not None and mexc_bid > 0:
            spread = ((mexc_ask - mexc_bid) / mexc_bid) * 100
        
        history = PriceHistory(
            token_id=token_id,
            mexc_bid=mexc_bid,
            mexc_ask=mexc_ask,
            matcha_price=matcha_price,
            pancake_price=pancake_price,
            spread=spread
        )
        
        db.add(history)
        db.commit()
        db.refresh(history)
        
        return history
    
    except Exception as e:
        log(f"Error saving price history: {e}")
        db.rollback()
        return None


def get_price_history(
    db: Session,
    token_id: int,
    hours: int = 24
) -> List[PriceHistory]:
    """
    Получить историю цен за последние N часов.
    
    Args:
        db: Сессия БД
        token_id: ID токена
        hours: Количество часов истории (по умолчанию 24)
    
    Returns:
        Список записей PriceHistory, отсортированный по времени
    """
    try:
        since = datetime.utcnow() - timedelta(hours=hours)
        
        history = db.query(PriceHistory).filter(
            PriceHistory.token_id == token_id,
            PriceHistory.created_at >= since
        ).order_by(PriceHistory.created_at.asc()).all()
        
        return history
    
    except Exception as e:
        log(f"Error getting price history: {e}")
        return []


def get_price_history_all(
    db: Session,
    token_id: int
) -> List[PriceHistory]:
    """
    Получить всю историю цен для токена.
    
    Args:
        db: Сессия БД
        token_id: ID токена
    
    Returns:
        Список всех записей PriceHistory, отсортированный по времени
    """
    try:
        history = db.query(PriceHistory).filter(
            PriceHistory.token_id == token_id
        ).order_by(PriceHistory.created_at.asc()).all()
        
        return history
    
    except Exception as e:
        log(f"Error getting all price history: {e}")
        return []


def get_token_by_name(db: Session, token_name: str) -> Optional[Token]:
    """
    Получить токен по имени (например "SOL-USDT").
    
    Args:
        db: Сессия БД
        token_name: Имя токена
    
    Returns:
        Объект Token или None если не найден
    """
    try:
        token = db.query(Token).filter(Token.name == token_name).first()
        return token
    
    except Exception as e:
        log(f"Error getting token by name: {e}")
        return None


def create_or_get_token(
    db: Session,
    name: str,
    base: str,
    quote: str = "USDT",
    **kwargs
) -> Optional[Token]:
    """
    Получить существующий токен или создать новый.
    
    Args:
        db: Сессия БД
        name: Имя пары (например "SOL-USDT")
        base: Базовая монета (например "SOL")
        quote: Котируемая монета (по умолчанию "USDT")
        **kwargs: Дополнительные параметры (cg_id, mexc_price_scale и т.д.)
    
    Returns:
        Объект Token
    """
    try:
        # Проверяем, существует ли уже
        token = db.query(Token).filter(Token.name == name).first()
        if token:
            return token
        
        # Создаем новый
        token = Token(
            name=name,
            base=base,
            quote=quote,
            **kwargs
        )
        
        db.add(token)
        db.commit()
        db.refresh(token)
        
        log(f"Created new token: {name}")
        
        return token
    
    except Exception as e:
        log(f"Error creating/getting token: {e}")
        db.rollback()
        return None
