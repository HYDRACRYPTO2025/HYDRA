# backend/admin_api.py
"""
API эндпоинты для админ-панели.
Управление прокси, токенами доступа и админ-пользователями.
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from .db import get_db
from .models import Proxy, AccessToken, AdminUser
from .auth import generate_token, hash_password, verify_password
from .logic import log

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ============= Pydantic Models =============

class ProxyCreate(BaseModel):
    url: str
    protocol: str = "socks5"  # http, https, socks5
    note: Optional[str] = None


class ProxyResponse(BaseModel ):
    id: int
    url: str
    protocol: str
    is_active: bool
    note: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AccessTokenCreate(BaseModel):
    name: Optional[str] = None


class AccessTokenResponse(BaseModel):
    id: int
    token: str
    name: Optional[str]
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime]

    class Config:
        from_attributes = True


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    token: str
    message: str


# ============= Прокси Endpoints =============

@router.get("/proxies", response_model=List[ProxyResponse])
def get_proxies(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None)
):
    """
    Получить список всех прокси.
    Требует аутентификацию админа.
    """
    # TODO: Проверить аутентификацию админа
    proxies = db.query(Proxy).all()
    return proxies


@router.post("/proxies", response_model=ProxyResponse)
def create_proxy(
    proxy_data: ProxyCreate,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None)
):
    """
    Создать новый прокси.
    Требует аутентификацию админа.
    """
    # TODO: Проверить аутентификацию админа
    
    # Проверяем, что прокси с таким URL еще не существует
    existing = db.query(Proxy).filter(Proxy.url == proxy_data.url).first()
    if existing:
        raise HTTPException(status_code=400, detail="Proxy with this URL already exists")
    
    new_proxy = Proxy(
        url=proxy_data.url,
        protocol=proxy_data.protocol,
        note=proxy_data.note,
        is_active=True
    )
    
    db.add(new_proxy)
    db.commit()
    db.refresh(new_proxy)
    
    log(f"Created new proxy: {new_proxy.url}")
    
    return new_proxy


@router.put("/proxies/{proxy_id}", response_model=ProxyResponse)
def update_proxy(
    proxy_id: int,
    proxy_data: ProxyCreate,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None)
):
    """
    Обновить прокси.
    Требует аутентификацию админа.
    """
    # TODO: Проверить аутентификацию админа
    
    proxy = db.query(Proxy).filter(Proxy.id == proxy_id).first()
    if not proxy:
        raise HTTPException(status_code=404, detail="Proxy not found")
    
    proxy.url = proxy_data.url
    proxy.protocol = proxy_data.protocol
    proxy.note = proxy_data.note
    
    db.commit()
    db.refresh(proxy)
    
    log(f"Updated proxy {proxy_id}: {proxy.url}")
    
    return proxy


@router.delete("/proxies/{proxy_id}")
def delete_proxy(
    proxy_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None)
):
    """
    Удалить прокси.
    Требует аутентификацию админа.
    """
    # TODO: Проверить аутентификацию админа
    
    proxy = db.query(Proxy).filter(Proxy.id == proxy_id).first()
    if not proxy:
        raise HTTPException(status_code=404, detail="Proxy not found")
    
    db.delete(proxy)
    db.commit()
    
    log(f"Deleted proxy {proxy_id}")
    
    return {"message": "Proxy deleted successfully"}


@router.post("/proxies/{proxy_id}/toggle")
def toggle_proxy(
    proxy_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None)
):
    """
    Активировать/деактивировать прокси.
    Требует аутентификацию админа.
    """
    # TODO: Проверить аутентификацию админа
    
    proxy = db.query(Proxy).filter(Proxy.id == proxy_id).first()
    if not proxy:
        raise HTTPException(status_code=404, detail="Proxy not found")
    
    proxy.is_active = not proxy.is_active
    db.commit()
    
    status = "activated" if proxy.is_active else "deactivated"
    log(f"Proxy {proxy_id} {status}")
    
    return {"id": proxy.id, "is_active": proxy.is_active}


# ============= Access Tokens Endpoints =============

@router.get("/access-tokens", response_model=List[AccessTokenResponse])
def get_access_tokens(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None)
):
    """
    Получить список всех токенов доступа.
    Требует аутентификацию админа.
    """
    # TODO: Проверить аутентификацию админа
    tokens = db.query(AccessToken).all()
    return tokens


@router.post("/access-tokens", response_model=AccessTokenResponse)
def create_access_token(
    token_data: AccessTokenCreate,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None)
):
    """
    Создать новый токен доступа.
    Требует аутентификацию админа.
    """
    # TODO: Проверить аутентификацию админа
    
    # Генерируем уникальный токен
    token_value = generate_token()
    
    new_token = AccessToken(
        token=token_value,
        name=token_data.name,
        is_active=True
    )
    
    db.add(new_token)
    db.commit()
    db.refresh(new_token)
    
    log(f"Created new access token: {new_token.name or 'unnamed'}")
    
    return new_token


@router.delete("/access-tokens/{token_id}")
def delete_access_token(
    token_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None)
):
    """
    Удалить токен доступа.
    Требует аутентификацию админа.
    """
    # TODO: Проверить аутентификацию админа
    
    token = db.query(AccessToken).filter(AccessToken.id == token_id).first()
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    
    db.delete(token)
    db.commit()
    
    log(f"Deleted access token {token_id}")
    
    return {"message": "Token deleted successfully"}


@router.post("/access-tokens/{token_id}/toggle")
def toggle_access_token(
    token_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None)
):
    """
    Активировать/деактивировать токен доступа.
    Требует аутентификацию админа.
    """
    # TODO: Проверить аутентификацию админа
    
    token = db.query(AccessToken).filter(AccessToken.id == token_id).first()
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    
    token.is_active = not token.is_active
    db.commit()
    
    status = "activated" if token.is_active else "deactivated"
    log(f"Access token {token_id} {status}")
    
    return {"id": token.id, "is_active": token.is_active}


# ============= Admin Users Endpoints =============

@router.post("/login", response_model=AdminLoginResponse)
def admin_login(
    credentials: AdminLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Вход в админ-панель.
    Возвращает токен сессии.
    """
    admin = db.query(AdminUser).filter(
        AdminUser.username == credentials.username,
        AdminUser.is_active == True
    ).first()
    
    if not admin or not verify_password(credentials.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Генерируем токен сессии (в реальном приложении использовать JWT)
    session_token = generate_token()
    
    log(f"Admin {credentials.username} logged in")
    
    return {
        "token": session_token,
        "message": "Login successful"
    }


@router.post("/users")
def create_admin_user(
    username: str,
    password: str,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None)
):
    """
    Создать нового админ-пользователя.
    Требует аутентификацию админа.
    """
    # TODO: Проверить аутентификацию админа
    
    # Проверяем, что пользователь с таким именем еще не существует
    existing = db.query(AdminUser).filter(AdminUser.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this username already exists")
    
    new_user = AdminUser(
        username=username,
        password_hash=hash_password(password),
        is_active=True
    )
    
    db.add(new_user)
    db.commit()
    
    log(f"Created new admin user: {username}")
    
    return {"message": "Admin user created successfully"}
