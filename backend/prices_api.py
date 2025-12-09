# backend/prices_api.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from datetime import datetime

from .db import get_db
from .auth import verify_access_token
from .price_logic import (
    get_mexc_price,
    get_matcha_price_usdt,
    get_pancake_price_usdt,
)
from .price_history import (
    save_price_history,
    get_price_history,
    get_price_history_all,
    create_or_get_token,
)

router = APIRouter()


class PriceRequest(BaseModel):
    base: str
    base_decimals: Optional[int] = 9

    mexc_price_scale: Optional[int] = 0

    matcha_addr: Optional[str] = None
    matcha_decimals: Optional[int] = None

    pancake_addr: Optional[str] = None


class PriceResponse(BaseModel):
    mexc_bid: Optional[float]
    mexc_ask: Optional[float]
    matcha_price: Optional[float]
    pancake_price: Optional[float]


class PriceHistoryItem(BaseModel):
    timestamp: datetime
    mexc_bid: Optional[float]
    mexc_ask: Optional[float]
    matcha_price: Optional[float]
    pancake_price: Optional[float]
    spread: Optional[float]

    class Config:
        from_attributes = True


@router.post("/prices", response_model=PriceResponse)
async def prices(
    data: PriceRequest,
    db: Session = Depends(get_db),
    token = Depends(verify_access_token)
):
    """
    Получить цены через прокси и сохранить в историю.
    Требует валидный токен доступа в заголовке Authorization: Bearer {token}
    """

    base = data.base.upper()

    # MEXC
    mexc_bid, mexc_ask = get_mexc_price(base, "USDT", data.mexc_price_scale, db=db)

    # Matcha
    matcha_price = None
    if data.matcha_addr:
        matcha_price = get_matcha_price_usdt(
            data.matcha_addr,
            data.matcha_decimals or 18,
            db=db
        )

    # Pancake
    pancake_price = None
    if data.pancake_addr:
        pancake_price = await get_pancake_price_usdt(data.pancake_addr, db=db)

    # Сохраняем в историю
    # Сначала создаем или получаем токен
    token_obj = create_or_get_token(
        db,
        name=f"{base}-USDT",
        base=base,
        quote="USDT",
        mexc_price_scale=data.mexc_price_scale,
        matcha_address=data.matcha_addr,
        matcha_decimals=data.matcha_decimals,
        bsc_address=data.pancake_addr
    )
    
    # Сохраняем цены в историю
    if token_obj:
        save_price_history(
            db,
            token_id=token_obj.id,
            mexc_bid=mexc_bid,
            mexc_ask=mexc_ask,
            matcha_price=matcha_price,
            pancake_price=pancake_price
        )

    return {
        "mexc_bid": mexc_bid,
        "mexc_ask": mexc_ask,
        "matcha_price": matcha_price,
        "pancake_price": pancake_price,
    }


@router.get("/prices/{token_name}/history", response_model=List[PriceHistoryItem])
def get_prices_history(
    token_name: str,
    hours: int = 24,
    db: Session = Depends(get_db),
    token = Depends(verify_access_token)
):
    """
    Получить историю цен за последние N часов.
    
    Параметры:
        token_name: Имя пары (например "SOL-USDT")
        hours: Количество часов истории (по умолчанию 24)
    
    Требует валидный токен доступа.
    """
    from .price_history import get_token_by_name
    
    # Получаем токен по имени
    token_obj = get_token_by_name(db, token_name)
    if not token_obj:
        return []
    
    # Получаем историю
    history = get_price_history(db, token_obj.id, hours=hours)
    
    return [
        {
            "timestamp": item.created_at,
            "mexc_bid": item.mexc_bid,
            "mexc_ask": item.mexc_ask,
            "matcha_price": item.matcha_price,
            "pancake_price": item.pancake_price,
            "spread": item.spread
        }
        for item in history
    ]


@router.get("/prices/{token_name}/history/all", response_model=List[PriceHistoryItem])
def get_all_prices_history(
    token_name: str,
    db: Session = Depends(get_db),
    token = Depends(verify_access_token)
):
    """
    Получить всю историю цен для токена.
    
    Параметры:
        token_name: Имя пары (например "SOL-USDT")
    
    Требует валидный токен доступа.
    """
    from .price_history import get_token_by_name
    
    # Получаем токен по имени
    token_obj = get_token_by_name(db, token_name)
    if not token_obj:
        return []
    
    # Получаем всю историю
    history = get_price_history_all(db, token_obj.id)
    
    return [
        {
            "timestamp": item.created_at,
            "mexc_bid": item.mexc_bid,
            "mexc_ask": item.mexc_ask,
            "matcha_price": item.matcha_price,
            "pancake_price": item.pancake_price,
            "spread": item.spread
        }
        for item in history
    ]
