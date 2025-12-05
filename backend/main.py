import os
from typing import List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel

from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import SessionLocal, Base, engine
from . import models


app = FastAPI()

# ==== CONFIG ====

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")
if not ADMIN_TOKEN:
    # Лучше сразу узнать, если забыли задать токен
    raise RuntimeError("ADMIN_TOKEN is not set")


# ==== DB UTILS ====


def get_db():
    """
    Даёт сессию БД в эндпоинтах.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_admin(x_admin_token: str = Header(...)) -> None:
    """
    Простейшая админ-авторизация по заголовку X-Admin-Token.
    """
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
    # Создаём таблицы при старте приложения
    Base.metadata.create_all(bind=engine)


# ==== ТЕСТОВЫЕ ЭНДПОИНТЫ ====


@app.get("/")
def read_root():
    return {"status": "ok"}


@app.get("/cg_ping")
def coingecko_ping():
    """
    Тест: сервер на Render делает запрос к CoinGecko
    и возвращает их ответ.
    """
    r = httpx.get("https://api.coingecko.com/api/v3/ping", timeout=10.0)
    return {
        "status": "ok",
        "coingecko_raw": r.json(),
    }


@app.get("/db_ping")
def db_ping():
    """
    Проверяем, что есть соединение с PostgreSQL на Render.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"db_error: {e}")


# ==== ПУБЛИЧНАЯ ЧАСТЬ ДЛЯ КЛИЕНТОВ ====


@app.post(
    "/tokens",
    response_model=TokenOut,
)
def client_add_token(
    token: TokenCreate,
    db: Session = Depends(get_db),
):
    """
    Клиент добавляет токен.

    Логика:
    - если такой chain+address уже есть и is_deleted=False → возвращаем его;
    - если есть и is_deleted=True → считаем, что админ забанил токен → 403;
    - если нет → создаём новую запись.
    """
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


@app.get(
    "/tokens",
    response_model=List[TokenOut],
)
def client_list_tokens(
    chain: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Список активных токенов для клиентов (только is_deleted=False).

    Можно фильтровать по chain, чтобы, например, получить только BSC.
    """
    q = db.query(models.Token).filter(models.Token.is_deleted == False)  # noqa: E712
    if chain:
        q = q.filter(models.Token.chain == chain)

    tokens = q.order_by(models.Token.created_at.desc()).all()
    return tokens


# ==== АДМИНКА: РАБОТА С ТОКЕНАМИ ====


@app.post(
    "/admin/tokens",
    response_model=TokenOut,
)
def admin_add_token(
    token: TokenCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    """
    Админ добавляет токен в БД.

    Если такой chain+address уже есть:
      - если он был помечен is_deleted=True, снимаем флаг и обновляем поля;
      - если активен — просто возвращаем существующую запись.
    """
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


@app.get(
    "/admin/tokens",
    response_model=List[TokenOut],
)
def admin_list_tokens(
    skip: int = 0,
    limit: int = 100,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    """
    Список токенов для админа.

    - skip / limit — пагинация
    - include_deleted=False — по умолчанию скрываем удалённые
    """
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
    """
    Мягкое удаление токена (is_deleted = True).
    Физически из БД не удаляем — можно будет восстановить.
    """
    token = db.query(models.Token).filter(models.Token.id == token_id).first()
    if not token:
        raise HTTPException(status_code=404, detail="token_not_found")

    token.is_deleted = True
    db.commit()
    return {"status": "ok", "token_id": token_id}


# ==== ЦЕНЫ / DEX: DEXSCREENER ====


DEXSCREENER_TOKENS_URL = "https://api.dexscreener.com/latest/dex/tokens"


@app.get("/price/dex_by_address")
def get_price_dex_by_address(address: str):
    """
    Публичный эндпоинт:
    Клиент даёт address токена, сервер ходит в DexScreener
    и возвращает сырые данные.

    Позже можем сделать тут расчёт спредов и красивый ответ.
    Сейчас главное — чтобы вся сеть шла через сервер.
    """
    url = f"{DEXSCREENER_TOKENS_URL}/{address}"

    try:
        r = httpx.get(url, timeout=10.0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"dexscreener_request_error: {e}")

    if r.status_code != 200:
        raise HTTPException(
            status_code=r.status_code,
            detail="bad_status_from_dexscreener",
        )

    data = r.json()
    return {
        "status": "ok",
        "source": "dexscreener",
        "address": address,
        "raw": data,
    }


# ==== CEX: MEXC FUTURES PRICE ====


MEXC_FUTURES_BASE = "https://contract.mexc.com"


@app.get("/cex/mexc_price")
def mexc_price(
    base: str,
    quote: str = "USDT",
    price_scale: Optional[int] = None,
):
    """
    Публичный эндпоинт:
    Клиент даёт base/quote (например, base=API3, quote=USDT),
    сервер ходит в MEXC фьючерсы и возвращает bid/ask.

    Это будет аналогом get_mexc_price() из core.py,
    только выполняется на сервере.
    """
    symbol = f"{base.upper()}_{quote.upper()}"

    try:
        r = httpx.get(
            f"{MEXC_FUTURES_BASE}/api/v1/contract/ticker",
            params={"symbol": symbol},
            timeout=10.0,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"mexc_request_error: {e}")

    try:
        j = r.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"bad_json_from_mexc: {e}")

    if not (j.get("success") and j.get("code") == 0 and j.get("data")):
        raise HTTPException(
            status_code=502,
            detail=f"mexc_error_response: {j}",
        )

    data = j["data"]
    bid = data.get("bid1")
    ask = data.get("ask1")

    bid_val = float(bid) if bid is not None else None
    ask_val = float(ask) if ask is not None else None

    if isinstance(price_scale, int) and price_scale >= 0:
        if bid_val is not None:
            bid_val = round(bid_val, price_scale)
        if ask_val is not None:
            ask_val = round(ask_val, price_scale)

    return {
        "symbol": symbol,
        "bid": bid_val,
        "ask": ask_val,
        "price_scale": price_scale,
    }
