# backend/main.py
import os
from typing import List, Optional
from decimal import Decimal

import httpx
from fastapi import FastAPI, HTTPException, Depends, Header, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import SessionLocal, Base, engine
from . import models


app = FastAPI()

# ==== CONFIG ====

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")
if not ADMIN_TOKEN:
    raise RuntimeError("ADMIN_TOKEN is not set")

DEXSCREENER_TOKENS_URL = "https://api.dexscreener.com/latest/dex/tokens"
DEXSCREENER_TIMEOUT = 10.0

# MEXC (spot) depth endpoint
MEXC_DEPTH_URL = "https://api.mexc.com/api/v3/depth"

# Jupiter price config
JUPITER_QUOTE_URL = "https://ultra-api.jup.ag/order"
JUPITER_USDT_MINT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
JUPITER_USDT_DECIMALS = 6
JUPITER_USDT_AMOUNT = Decimal("100")

# Matcha price config
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


# ==== DB UTILS ====


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_admin(x_admin_token: str = Header(...)) -> None:
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="invalid_admin_token")


# ==== Pydantic-схемы ====


class TokenCreate(BaseModel):
    chain: str
    address: str
    symbol: Optional[str] = None
    name: Optional[str] = None


class TokenOut(BaseModel):
    id: int
    chain: str
    address: str
    symbol: Optional[str] = None
    name: Optional[str] = None
    is_deleted: bool

    class Config:
        orm_mode = True


# ==== LIFECYCLE ====


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


# ==== ТЕСТОВЫЕ ЭНДПОИНТЫ ====


@app.get("/")
def read_root():
    return {"status": "ok"}


@app.get("/cg_ping")
def cg_ping():
    try:
        r = httpx.get("https://api.coingecko.com/api/v3/ping", timeout=10.0)
        return {"status": "ok", "coingecko_raw": r.json()}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"coingecko_error: {e}")


@app.get("/db_ping")
def db_ping():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"db_error: {e}")


# ==== ПУБЛИЧНАЯ ЧАСТЬ ДЛЯ КЛИЕНТОВ ====


@app.post("/tokens", response_model=TokenOut)
def client_add_token(token: TokenCreate, db: Session = Depends(get_db)):
    existing = (
        db.query(models.Token)
        .filter(
            models.Token.chain == token.chain,
            models.Token.address == token.address,
        )
        .first()
    )

    if existing:
        if existing.is_deleted:
            raise HTTPException(status_code=403, detail="token_disabled_by_admin")
        return existing

    new_token = models.Token(
        chain=token.chain,
        address=token.address,
        symbol=token.symbol,
        name=token.name,
    )
    db.add(new_token)
    db.commit()
    db.refresh(new_token)
    return new_token


@app.get("/tokens", response_model=List[TokenOut])
def client_list_tokens(
    chain: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Token).filter(models.Token.is_deleted == False)  # noqa: E712
    if chain:
        q = q.filter(models.Token.chain == chain)

    tokens = q.order_by(models.Token.created_at.desc()).all()
    return tokens


# ==== АДМИНКА: РАБОТА С ТОКЕНАМИ ====


@app.post("/admin/tokens", response_model=TokenOut)
def admin_add_token(
    token: TokenCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    existing = (
        db.query(models.Token)
        .filter(
            models.Token.chain == token.chain,
            models.Token.address == token.address,
        )
        .first()
    )

    if existing:
        if existing.is_deleted:
            existing.is_deleted = False
            if token.symbol:
                existing.symbol = token.symbol
            if token.name:
                existing.name = token.name
            db.commit()
            db.refresh(existing)
        return existing

    new_token = models.Token(
        chain=token.chain,
        address=token.address,
        symbol=token.symbol,
        name=token.name,
    )
    db.add(new_token)
    db.commit()
    db.refresh(new_token)
    return new_token


@app.get("/admin/tokens", response_model=List[TokenOut])
def admin_list_tokens(
    skip: int = 0,
    limit: int = 100,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    q = db.query(models.Token)
    if not include_deleted:
        q = q.filter(models.Token.is_deleted == False)  # noqa: E712

    tokens = q.order_by(models.Token.created_at.desc()).offset(skip).limit(limit).all()
    return tokens


@app.delete("/admin/tokens/{token_id}")
def admin_delete_token(
    token_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    token = db.query(models.Token).filter(models.Token.id == token_id).first()
    if not token:
        raise HTTPException(status_code=404, detail="token_not_found")

    token.is_deleted = True
    db.commit()
    return {"status": "ok", "token_id": token_id}


# ==== PRICE: DexScreener (Pancake и др.) ====


@app.get("/price/dex_by_address")
def price_dex_by_address(
    address: str = Query(..., description="Token address (chain-specific)"),
):
    addr = address.strip()
    if not addr:
        raise HTTPException(status_code=400, detail="empty_address")

    url = f"{DEXSCREENER_TOKENS_URL}/{addr}"

    try:
        resp = httpx.get(url, timeout=DEXSCREENER_TIMEOUT)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"dexscreener_request_error: {e}")

    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"dexscreener_http_{resp.status_code}: {resp.text[:200]}",
        )

    data = resp.json()
    return {
        "status": "ok",
        "source": "dexscreener",
        "address": addr,
        "raw": data,
    }


# ==== PRICE: MEXC spot ====


@app.get("/cex/mexc_price")
def mexc_price(
    symbol: str = Query(..., description="Trading pair, e.g. GOAT_USDT"),
):
    s = symbol.strip().upper()
    if not s:
        raise HTTPException(status_code=400, detail="empty_symbol")

    params = {"symbol": s, "limit": 5}
    try:
        resp = httpx.get(MEXC_DEPTH_URL, params=params, timeout=5.0)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"mexc_request_error: {e}")

    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"mexc_http_{resp.status_code}: {resp.text[:200]}",
        )

    data = resp.json()
    bids = data.get("bids") or []
    asks = data.get("asks") or []

    def _best_price(levels):
        if not levels:
            return None
        try:
            return float(levels[0][0])
        except Exception:
            return None

    bid = _best_price(bids)
    ask = _best_price(asks)

    if bid is None or ask is None:
        raise HTTPException(status_code=502, detail="no_orderbook")

    # оценим количество знаков после запятой
    price_str = str(bid)
    if "." in price_str:
        price_scale = len(price_str.split(".")[1])
    else:
        price_scale = 0

    return {
        "status": "ok",
        "symbol": s,
        "bid": bid,
        "ask": ask,
        "price_scale": price_scale,
    }


# ==== PRICE: Matcha (0x) через наш бекенд ====


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


# ==== PRICE: Jupiter (по mint) ====


@app.get("/price/jupiter")
def price_jupiter(
    mint: str = Query(..., description="Token mint"),
    decimals: int = Query(..., ge=0, description="Token decimals"),
):
    m = mint.strip()
    if not m:
        raise HTTPException(status_code=400, detail="empty_mint")

    try:
        usdt_amount_raw = int(
            JUPITER_USDT_AMOUNT * (Decimal(10) ** JUPITER_USDT_DECIMALS)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"usdt_amount_error: {e}")

    try:
        resp = httpx.get(
            JUPITER_QUOTE_URL,
            params={
                "inputMint": JUPITER_USDT_MINT,
                "outputMint": m,
                "amount": str(usdt_amount_raw),
                "swapMode": "ExactIn",
            },
            timeout=2.0,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"jupiter_request_error: {e}")

    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"jupiter_http_{resp.status_code}: {resp.text[:200]}",
        )

    data = resp.json()
    out_amount_str = data.get("outAmount")
    if not out_amount_str:
        raise HTTPException(status_code=502, detail=f"no_outAmount: {data}")

    try:
        out_amount_raw = int(out_amount_str)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"bad_outAmount {out_amount_str}: {e}",
        )

    if out_amount_raw <= 0:
        raise HTTPException(status_code=502, detail="non_positive_outAmount")

    token_amount = Decimal(out_amount_raw) / (Decimal(10) ** decimals)
    if token_amount <= 0:
        raise HTTPException(status_code=502, detail="non_positive_token_amount")

    price = JUPITER_USDT_AMOUNT / token_amount

    return {
        "status": "ok",
        "price": float(price),
        "usdt_amount": float(JUPITER_USDT_AMOUNT),
        "out_amount_raw": out_amount_raw,
    }
