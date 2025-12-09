import cloudscraper
import httpx
from datetime import datetime
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from .logic import log
from .proxy_manager import ProxyManager


def get_http_client_with_proxy(proxy_dict: dict):
    """
    Создать httpx AsyncClient с прокси.
    """
    if proxy_dict:
        # Берем первый прокси из словаря (они одинаковые для http и https)
        proxy_url = list(proxy_dict.values())[0] if proxy_dict else None
        return httpx.AsyncClient(proxy=proxy_url, timeout=10)
    else:
        return httpx.AsyncClient(timeout=10)


# ... MEXC UTILS ---
def normalize_mexc_symbol(token: str) -> str:
    """
    Приводим тикер к формату AAA_BBB (например MEMERUSH_USDT).

    Поддерживаем:
    - MEMERUSH        -> MEMERUSH_USDT
    - MEMERUSHUSDT    -> MEMERUSH_USDT
    - MEMERUSH_USDT   -> MEMERUSH_USDT (без изменений)
    - memerush        -> MEMERUSH_USDT (приводим в верхний регистр)
    """
    t = (token or "").upper().replace(" ", "").strip()
    if not t:
        return ""

    # Уже нормальный формат
    if t.endswith("_USDT"):
        return t

    # MEMERUSHUSDT или MEMERUSH_USDT (без нижнего подчёркивания)
    if t.endswith("USDT"):
        base = t[:-4]  # отрезаем 'USDT'
        if base.endswith("_"):
            base = base[:-1]
        return f"{base}_USDT"

    # Просто MEMERUSH -> MEMERUSH_USDT
    return f"{t}_USDT"
# --- КОНЕЦ MEXC UTILS ---


# ... MEXC ---
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
    # КРИТИЧНО: Нормализуем символ перед отправкой на MEXC
    normalized_base = normalize_mexc_symbol(base)
    if not normalized_base:
        log(f"MEXC error: Invalid base symbol: {base}")
        return None, None

    try:
        # Получаем прокси из БД
        proxy_dict = {}
        proxy_url = None
        if db:
            proxy_manager = ProxyManager(db)
            proxy_url = proxy_manager.get_random_proxy()
            # ИСПРАВЛЕНО: Передаём proxy_url в log_proxy_usage
            proxy_manager.log_proxy_usage(proxy_url)
            if proxy_url:
                proxy_dict = {
                    "http://": proxy_url,
                    "https://": proxy_url
                }

        # Создаём клиент с прокси
        http_client = get_http_client_with_proxy(proxy_dict)

        # ИСПРАВЛЕНО: Используем нормализованный символ
        symbol = f"{normalized_base}_{quote.upper()}"

        r = http_client.get(
            "https://api.mexc.com/api/v3/ticker/bookTicker",
            params={"symbol": symbol},
            timeout=10,
        )

        if r.status_code != 200:
            log(f"MEXC HTTP {r.status_code} для {symbol}: {str(r.text)[:200]}")
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
    Получить цену токена в USDT через Matcha (0x) через прокси.
    """
    addr = (addr or "").strip()
    if not addr:
        return None

    try:
        # Получаем прокси из БД
        proxy_dict = {}
        proxy_url = None
        if db:
            proxy_manager = ProxyManager(db)
            proxy_url = proxy_manager.get_random_proxy()
            # ИСПРАВЛЕНО: Передаём proxy_url в log_proxy_usage
            proxy_manager.log_proxy_usage(proxy_url)
            if proxy_url:
                proxy_dict = {
                    "http://": proxy_url,
                    "https://": proxy_url
                }

        # Создаём клиент с прокси
        http_client = get_http_client_with_proxy(proxy_dict)

        r = http_client.get(
            "https://api.matcha.xyz/api/gasless/price",
            params={
                "sellTokenAddress": addr,
                "buyTokenAddress": "0xfde4c96c8593536e31f229ea8f37b2ada2699bb2",  # USDT
                "sellAmount": int(10 ** decimals),
                "chainId": 8453,
            },
            timeout=10,
        )

        if r.status_code != 200:
            log(f"Matcha: HTTP {r.status_code} для {addr}")
            return None

        j = r.json()
        price = float(j.get("buyAmount", 0)) / (10 ** 6)  # USDT decimals = 6
        return price if price > 0 else None

    except Exception as e:
        log(f"Matcha error: {e}")
        return None


# --- PancakeSwap (BSC) ---
def get_pancake_price_usdt(
    addr: str,
    db: Optional[Session] = None
) -> Optional[float]:
    """
    Получить цену токена в USDT через PancakeSwap (BSC) через прокси.
    """
    addr = (addr or "").strip()
    if not addr:
        return None

    try:
        # Получаем прокси из БД
        proxy_dict = {}
        proxy_url = None
        if db:
            proxy_manager = ProxyManager(db)
            proxy_url = proxy_manager.get_random_proxy()
            # ИСПРАВЛЕНО: Передаём proxy_url в log_proxy_usage
            proxy_manager.log_proxy_usage(proxy_url)
            if proxy_url:
                proxy_dict = {
                    "http://": proxy_url,
                    "https://": proxy_url
                }

        # Создаём клиент с прокси
        http_client = get_http_client_with_proxy(proxy_dict)

        r = http_client.get(
            "https://api.dexscreener.com/latest/dex/tokens/bsc/" + addr,
            timeout=10,
        )

        if r.status_code != 200:
            log(f"PancakeSwap: HTTP {r.status_code} для {addr}")
            return None

        j = r.json()
        pairs = j.get("pairs") or []
        if not pairs:
            return None

        # Ищем пару с наибольшей ликвидностью
        best_pair = max(
            pairs,
            key=lambda p: float(p.get("liquidity", {}).get("usd", 0))
        )
        price = float(best_pair.get("priceUsd", 0))
        return price if price > 0 else None

    except Exception as e:
        log(f"PancakeSwap error: {e}")
        return None
