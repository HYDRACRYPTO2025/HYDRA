# backend/auth.py
"""
Модуль для аутентификации и работы с токенами доступа.
"""

import secrets
import hashlib
from datetime import datetime
from typing import Optional
from fastapi import HTTPException, Depends, Header
from sqlalchemy.orm import Session
from .models import AccessToken, AdminUser
from .db import get_db
from .logic import log


def generate_token(length: int = 32) -> str:
    """Генерировать случайный токен доступа."""
    return "hydra_" + secrets.token_urlsafe(length)


def hash_password(password: str) -> str:
    """Хешировать пароль."""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """Проверить пароль."""
    return hash_password(password) == password_hash


def verify_access_token(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> AccessToken:
    """
    Зависимость FastAPI для проверки токена доступа.
    Используется в защищенных эндпоинтах.
    
    Ожидает заголовок: Authorization: Bearer {token}
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    # Парсим "Bearer {token}"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    token = parts[1]
    
    # Ищем токен в БД
    db_token = db.query(AccessToken).filter(
        AccessToken.token == token,
        AccessToken.is_active == True
    ).first()
    
    if not db_token:
        raise HTTPException(status_code=401, detail="Invalid or inactive token")
    
    # Обновляем время последнего использования
    db_token.last_used_at = datetime.utcnow()
    db.commit()
    
    return db_token


def verify_admin(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> AdminUser:
    """
    Зависимость FastAPI для проверки админ-сессии.
    Используется в админ-панели.
    
    Ожидает заголовок: Authorization: Bearer {admin_session_token}
    (или можно использовать cookies для веб-интерфейса)
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    token = parts[1]
    
    # Для простоты: ищем админа по токену (в реальном приложении использовать JWT)
    # Пока просто проверяем, что это валидный админ-токен
    # В будущем можно добавить таблицу admin_sessions
    
    # На данный момент просто проверяем, что админ существует и активен
    # Логика будет доработана в следующих версиях
    
    raise HTTPException(status_code=401, detail="Admin authentication not yet implemented")
