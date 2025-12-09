import cloudscraper
import httpx
from datetime import datetime
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from .logic import log
from .proxy_manager import ProxyManager


def get_http_client_with_proxy(proxy_dict: dict):
    """
    Создать cloudscraper клиент с прокси.
    proxy_dict должен быть в формате:
    {
        "http://": "socks5://user:pass@ip:port",
        "https://": "socks5://user:pass@ip:port"
    }
    """
    http_client = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    
    if proxy_dict:
        http_client.proxies = proxy_dict
    
    return http_client


async def get_httpx_client_with_proxy(proxy_dict: dict):
    """
    Создать httpx AsyncClient с прокси.
    """
    if proxy_dict:
        # Берем первый прокси из словаря (они одинаковые для http и https)
        proxy_url = list(proxy_dict.values())[0] if proxy_dict else None
        return httpx.AsyncClient(proxies=proxy_url, timeout=10)
    else:
        return httpx.AsyncClient(timeout=10)


# --- MEXC ---
def get_mexc_price(
    base: str,
    quote: str = "USDT",
    price_scale: int = 0,
    db: Optional[Session] = None
) -> Tuple[Optional[float], Optional[float]]:
    """
    Получить цену с MEXC через прокси.
    
    Args:
        base: Базовая монета (SOL, BTC и т.д.)
        quote: Котируемая монета (USDT по умолчанию)
        price_scale: Количество знаков после запятой
        db: Сессия БД для получения прокси
    
    Returns:
        (bid_price, ask_price) или (None, None) при ошибке
    """
    symbol = f"{base.upper()}_{quote.upper()}"
    
    try:
        # Получаем прокси из БД
        proxy_dict = {}
        if db:
            proxy_manager = ProxyManager(db)
            proxy_url = proxy_manager.get_random_proxy()
            if proxy_url:
                proxy_dict = proxy_manager.get_proxy_dict(proxy_url)
                proxy_manager.log_proxy_usage(proxy_url)
        
        # Создаем клиент с прокси
        http_client = get_http_client_with_proxy(proxy_dict)
        
        r = http_client.get(
            "https://api.mexc.com/api/v3/ticker/bookTicker",
            params={"symbol": symbol},
            timeout=10,
        )
        
        if r.status_code != 200:
            log(f"MEXC HTTP {r.status_code}: {r.text[:200]}")
            return None, None

        j = r.json()
        bid = float(j.get("bidPrice", 0))
        ask = float(j.get("askPrice", 0))

        if price_scale:
            bid = round(bid, price_scale)
            ask = round(ask, price_scale)

        return bid, ask

    except Exception as e:
        log(f"MEXC error: {e}")
        return None, None


# --- Matcha (0x) ---
def get_matcha_price_usdt(
    addr: str,
    decimals: int,
    db: Optional[Session] = None
) -> Optional[float]:
    """
    Получить цену с Matcha (0x) через прокси.
    
    Args:
        addr: Адрес токена
        decimals: Количество знаков после запятой
        db: Сессия БД для получения прокси
    
    Returns:
        Цена в USDT или None при ошибке
    """
    url = f"https://api.0x.org/swap/v1/price?sellToken={addr}&buyToken=USDT&sellAmount={10**decimals}"
    
    try:
        # Получаем прокси из БД
        proxy_dict = {}
        if db:
            proxy_manager = ProxyManager(db)
            proxy_url = proxy_manager.get_random_proxy()
            if proxy_url:
                proxy_dict = proxy_manager.get_proxy_dict(proxy_url)
                proxy_manager.log_proxy_usage(proxy_url)
        
        # Создаем клиент с прокси
        http_client = get_http_client_with_proxy(proxy_dict)
        
        r = http_client.get(url, timeout=10)
        
        if r.status_code != 200:
            log(f"Matcha HTTP {r.status_code}: {r.text[:200]}")
            return None
        
        return float(r.json().get("price", 0))
    
    except Exception as e:
        log(f"Matcha error: {e}")
        return None


# --- PancakeSwap (BSC) ---
async def get_pancake_price_usdt(
    token: str,
    db: Optional[Session] = None
) -> Optional[float]:
    """
    Получить цену с PancakeSwap через прокси.
    
    Args:
        token: Адрес токена на BSC
        db: Сессия БД для получения прокси
    
    Returns:
        Цена в USDT или None при ошибке
    """
    url = "https://api.dexscreener.com/latest/dex/tokens/" + token
    
    try:
        # Получаем прокси из БД
        proxy_url = None
        if db:
            proxy_manager = ProxyManager(db)
            proxy_url = proxy_manager.get_random_proxy()
            if proxy_url:
                proxy_manager.log_proxy_usage(proxy_url)
        
        # Создаем async клиент с прокси
        async with httpx.AsyncClient(proxies=proxy_url, timeout=10) as client:
            r = await client.get(url)
            
            if r.status_code != 200:
                log(f"Pancake HTTP {r.status_code}: {r.text[:200]}")
                return None
            
            j = r.json()
            pairs = j.get("pairs", [])
            if not pairs:
                return None
            
            return float(pairs[0].get("priceUsd", 0))
    
    except Exception as e:
        log(f"Pancake error: {e}")
        return None
