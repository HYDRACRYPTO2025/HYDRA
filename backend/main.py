from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import asyncio
import logging

from .db import Base, engine, get_db
from .models import Token, Proxy, AccessToken, AdminUser, PriceHistory
from .logic import fetch_L_M_for_pair, PairConfigLM, log
from .auth import verify_access_token

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаём таблицы в БД при старте
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="HYDRA backend",
    version="0.1.0",
)

# CORS для desktop приложения
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .prices_api import router as prices_router
from .admin_api import router as admin_router
from .admin_ui import router as admin_ui_router

app.include_router(prices_router, prefix="/api")
app.include_router(admin_router)
app.include_router(admin_ui_router)


# ============= Background task для очистки старых данных =============

async def cleanup_old_price_history():
    """
    Удалить записи истории цен старше 2 дней.
    Запускается каждый час.
    """
    from .db import SessionLocal
    
    db = SessionLocal()
    try:
        # Удаляем записи старше 2 дней
        cutoff_time = datetime.utcnow() - timedelta(days=2)
        
        deleted = db.query(PriceHistory).filter(
            PriceHistory.created_at < cutoff_time
        ).delete()
        
        db.commit()
        
        if deleted > 0:
            logger.info(f"Deleted {deleted} old price history records (older than 2 days)")
    
    except Exception as e:
        logger.error(f"Error cleaning up price history: {e}")
        db.rollback()
    
    finally:
        db.close()


@app.on_event("startup")
async def startup_event():
    """Запустить background task при старте сервера."""
    logger.info("Starting HYDRA backend server...")
    
    # Запускаем cleanup task каждый час
    async def cleanup_loop():
        while True:
            try:
                await cleanup_old_price_history()
                # Ждем 1 час перед следующей очисткой
                await asyncio.sleep(3600)
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(60)  # Попробуем снова через минуту
    
    # Запускаем в фоне
    asyncio.create_task(cleanup_loop())


@app.on_event("shutdown")
async def shutdown_event():
    """Логирование при остановке сервера."""
    logger.info("Shutting down HYDRA backend server...")


@app.get("/api/health")
@app.head("/api/health")
def health():
    """Health-check, чтобы проверить что сервер жив."""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "HYDRA backend"
    }


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
