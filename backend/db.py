import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# В Render мы положим переменную окружения DATABASE_URL.
# Это строка подключения к Postgres (External Database URL из твоей БД).
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. "
        "На Render надо в Environment добавить переменную DATABASE_URL "
        "со значением External Database URL из hydra-db."
    )

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)

Base = declarative_base()


def get_db():
    """Шаблон для FastAPI зависимостей (на будущее)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
