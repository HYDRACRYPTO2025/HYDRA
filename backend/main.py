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
      - если он был помечен is_deleted=True, снимаем флаг и возвращаем;
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
