from fastapi import FastAPI, HTTPException
import httpx

from sqlalchemy import text

from .db import SessionLocal, Base, engine
from . import models  # важно: чтобы токены были зарегистрированы в метаданных

app = FastAPI()


# Создаём таблицы при старте приложения
@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


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


# дальше будем добавлять эндпоинты для токенов и админ-панели
