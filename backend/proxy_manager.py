# backend/proxy_manager.py
"""
Модуль для управления прокси и применения их к HTTP-клиентам.
"""

import random
from typing import Optional, List
from sqlalchemy.orm import Session
from .models import Proxy
from .logic import log


class ProxyManager:
    """Менеджер для работы с прокси из БД."""

    def __init__(self, db: Session):
        self.db = db

    def get_active_proxies(self) -> List[Proxy]:
        """Получить список активных прокси."""
        return self.db.query(Proxy).filter(Proxy.is_active == True).all()

    def get_random_proxy(self) -> Optional[str]:
        """
        Получить случайный активный прокси.
        Возвращает URL прокси вида:
        - socks5://user:pass@ip:port
        - http://user:pass@ip:port
        """
        proxies = self.get_active_proxies( )
        if not proxies:
            return None
        
        proxy = random.choice(proxies)
        return proxy.url

    def get_proxy_dict(self, proxy_url: Optional[str] = None) -> dict:
        """
        Получить словарь прокси для httpx/requests.
        Если proxy_url не указан, берет случайный из БД.
        
        Возвращает:
        {
            "http://": "socks5://...",
            "https://": "socks5://..."
        }
        """
        if proxy_url is None:
            proxy_url = self.get_random_proxy( )
        
        if not proxy_url:
            return {}
        
        return {
            "http://": proxy_url,
            "https://": proxy_url,
        }

    def get_proxy_safe_host(self, proxy_url: str ) -> str:
        """
        Убрать логин/пароль из URL прокси для логирования.
        Пример:
            socks5://user:pass@1.2.3.4:5555 -> 1.2.3.4:5555
        """
        try:
            rest = proxy_url.split("://", 1)[1]
            if "@" in rest:
                rest = rest.split("@", 1)[1]
            return rest
        except Exception:
            return proxy_url

    def log_proxy_usage(self, proxy_url: Optional[str]) -> None:
        """Залогировать использование прокси."""
        if proxy_url:
            safe_host = self.get_proxy_safe_host(proxy_url)
            log(f"Using proxy: {safe_host}")
        else:
            log("No proxy available, using direct connection")
