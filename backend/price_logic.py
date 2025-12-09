import cloudscraper
import httpx
from datetime import datetime

from .logic import log  # используем твой логгер


http_client = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)


# --- MEXC ---
def get_mexc_price(base: str, quote: str = "USDT", price_scale: int = 0):
    symbol = f"{base.upper()}_{quote.upper()}"
    try:
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
def get_matcha_price_usdt(addr: str, decimals: int):
    url = f"https://api.0x.org/swap/v1/price?sellToken={addr}&buyToken=USDT&sellAmount={10**decimals}"
    try:
        r = http_client.get(url, timeout=10)
        if r.status_code != 200:
            log(f"Matcha HTTP {r.status_code}: {r.text[:200]}")
            return None
        return float(r.json().get("price", 0))
    except Exception as e:
        log(f"Matcha error: {e}")
        return None


# --- PancakeSwap (BSC) ---
async def get_pancake_price_usdt(token: str):
    url = (
        "https://api.dexscreener.com/latest/dex/tokens/"
        + token
    )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
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
