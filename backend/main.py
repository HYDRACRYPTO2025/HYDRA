from decimal import Decimal
import httpx
from fastapi import Query, HTTPException

MATCHA_PRICE_URL = "https://matcha.xyz/api/gasless/price"
MATCHA_USDT = "0xfde4c96c8593536e31f229ea8f37b2ada2699bb2"
MATCHA_CHAIN_ID = 8453
MATCHA_USDT_AMOUNT = Decimal("100")
MATCHA_USDT_DECIMALS = 6
MATCHA_DEFAULT_SELL_DECIMALS = 18

MATCHA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://matcha.xyz",
    "Referer": "https://matcha.xyz/",
}


@app.get("/price/matcha_by_address")
def price_matcha_by_address(
    address: str = Query(..., description="Token address"),
    token_decimals: int = Query(MATCHA_DEFAULT_SELL_DECIMALS, ge=0),
    chain_id: int = Query(MATCHA_CHAIN_ID),
    usdt_token: str = Query(MATCHA_USDT),
    usdt_decimals: int = Query(MATCHA_USDT_DECIMALS, ge=0),
):
    addr = address.strip()
    if not addr:
        raise HTTPException(status_code=400, detail="empty_address")

    # 100 USDT в raw
    try:
        sell_amount_raw = int(
            MATCHA_USDT_AMOUNT * (Decimal(10) ** int(usdt_decimals))
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"sell_amount_error: {e}")

    try:
        resp = httpx.get(
            MATCHA_PRICE_URL,
            params={
                "chainId": chain_id,
                "sellToken": usdt_token,
                "buyToken": addr,
                "sellAmount": str(sell_amount_raw),
                "useIntents": "true",
            },
            headers=MATCHA_HEADERS,
            timeout=6.0,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"matcha_request_error: {e}")

    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"matcha_http_{resp.status_code}: {resp.text[:200]}",
        )

    data = resp.json()
    s_raw = data.get("sellAmount")
    b_raw = data.get("buyAmount")
    if not s_raw or not b_raw:
        raise HTTPException(status_code=502, detail=f"no_sell_or_buy_amount: {data}")

    try:
        s_amt = Decimal(str(s_raw))
        b_amt = Decimal(str(b_raw))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"decimal_error: {e}")

    if s_amt <= 0 or b_amt <= 0:
        raise HTTPException(status_code=502, detail="non_positive_amounts")

    token_amount = b_amt / (Decimal(10) ** token_decimals)
    if token_amount <= 0:
        raise HTTPException(status_code=502, detail="non_positive_token_amount")

    price = MATCHA_USDT_AMOUNT / token_amount

    return {
        "status": "ok",
        "price": float(price),
        "usdt_amount": float(MATCHA_USDT_AMOUNT),
        "raw": data,
    }
