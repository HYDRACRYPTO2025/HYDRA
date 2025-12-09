from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from .db import Base, engine, get_db
from .models import Token, Proxy, AccessToken, AdminUser
from .logic import fetch_L_M_for_pair, PairConfigLM, log
from .auth import verify_access_token

# Создаём таблицы в БД при старте (для простоты)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="HYDRA backend",
    version="0.1.0",
)
from .prices_api import router as prices_router
from .admin_api import router as admin_router
from .admin_ui import router as admin_ui_router

app.include_router(prices_router, prefix="/api")
app.include_router(admin_router)
app.include_router(admin_ui_router)

@app.get("/api/health")
def health():
    """Health-check, чтобы проверить что сервер жив."""
    return {"status": "ok"}


class LMRequest(BaseModel):
    base: str
    cg_id: Optional[str] = None


class LMResponse(BaseModel):
    base: str
    cg_id: Optional[str]
    price_mexc: Optional[float]
    L: Optional[float]
    M: Optional[float]


@app.post("/api/lm", response_model=LMResponse)
def get_lm(
    data: LMRequest,
    db: Session = Depends(get_db),
    token = Depends(verify_access_token)
):
    """
    Получить L/M для монеты (base/USDT на MEXC + CoinGecko market_cap) через прокси.
    Требует валидный токен доступа в заголовке Authorization: Bearer {token}

    Пример запроса:
    POST /api/lm
    {
      "base": "SOL"
    }
    """
    cfg = PairConfigLM(base=data.base, cg_id=data.cg_id)
    result = fetch_L_M_for_pair(cfg, db=db)
    if result is None:
        raise HTTPException(status_code=404, detail="No data for this symbol")

    return LMResponse(
        base=data.base.upper(),
        cg_id=result.get("cg_id"),
        price_mexc=result.get("price_mexc"),
        L=result.get("L"),
        M=result.get("M"),
    )
