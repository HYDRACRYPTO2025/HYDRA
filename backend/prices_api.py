# backend/prices_api.py
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from .price_logic import (
    get_mexc_price,
    get_matcha_price_usdt,
    get_pancake_price_usdt,
)

router = APIRouter()


class PriceRequest(BaseModel):
    base: str
    base_decimals: Optional[int] = 9

    mexc_price_scale: Optional[int] = 0

    matcha_addr: Optional[str] = None
    matcha_decimals: Optional[int] = None

    pancake_addr: Optional[str] = None


@router.post("/prices")
async def prices(data: PriceRequest):

    base = data.base.upper()

    # MEXC
    mexc_bid, mexc_ask = get_mexc_price(base, "USDT", data.mexc_price_scale)

    # Matcha
    matcha_price = None
    if data.matcha_addr:
        matcha_price = get_matcha_price_usdt(
            data.matcha_addr,
            data.matcha_decimals or 18,
        )

    # Pancake
    pancake_price = None
    if data.pancake_addr:
        pancake_price = await get_pancake_price_usdt(data.pancake_addr)

    return {
        "mexc_bid": mexc_bid,
        "mexc_ask": mexc_ask,
        "matcha_price": matcha_price,
        "pancake_price": pancake_price,
    }
