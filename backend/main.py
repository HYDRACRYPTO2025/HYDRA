from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

from .db import Base, engine
from .models import Token, Proxy
from .logic import fetch_L_M_for_pair, PairConfigLM, log

# Создаём таблицы в БД при старте (для простоты)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="HYDRA backend",
    version="0.1.0",
)
from .prices_api import router as prices_router
app.include_router(prices_router, prefix="/api")

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
def get_lm(data: LMRequest):
    """
    Получить L/M для монеты (base/USDT на MEXC + CoinGecko market_cap).

    Пример запроса:
    POST /api/lm
    {
      "base": "SOL"
    }
    """
    cfg = PairConfigLM(base=data.base, cg_id=data.cg_id)
    result = fetch_L_M_for_pair(cfg)
    if result is None:
        raise HTTPException(status_code=404, detail="No data for this symbol")

    return LMResponse(
        base=data.base.upper(),
        cg_id=result.get("cg_id"),
        price_mexc=result.get("price_mexc"),
        L=result.get("L"),
        M=result.get("M"),
    )
