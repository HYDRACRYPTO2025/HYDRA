# core.py - ОБНОВЛЕННАЯ ВЕРСИЯ
# Все запросы к Jupiter, PancakeSwap, MEXC, Matcha, CoinGecko идут через Render backend API
import os
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys
from typing import Optional, Dict, List
from PyQt5.QtCore import QThread, pyqtSignal
from decimal import Decimal
from web3 import Web3
import random
from concurrent.futures import ThreadPoolExecutor

# ===== ИМПОРТИРУЕМ API КЛИЕНТ ВМЕСТО HTTPX =====
from api_client import get_client

DEXSCREENER_TIMEOUT = 10.0
DEX_SAMPLE_TOKENS = 10000
MAX_LOG = 2000

JUPITER_USDT_DECIMALS = 6
JUPITER_USDT_AMOUNT = Decimal("100")

JUPITER_QUOTE_URL = "https://ultra-api.jup.ag/order"
JUPITER_USDT_MINT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
MEXC_FUTURES_BASE = "https://contract.mexc.com"
DEXSCREENER_SEARCH_URL = "https://api.dexscreener.com/latest/dex/search"
PANCAKE_TOKENS_API = "https://api.pancakeswap.info/api/tokens"
DEXSCREENER_TOKENS_URL = "https://api.dexscreener.com/latest/dex/tokens"

MATCHA_PRICE_URL = "https://matcha.xyz/api/gasless/price"
MATCHA_USDT = "0xfde4c96c8593536e31f229ea8f37b2ada2699bb2"
MATCHA_USDT_AMOUNT = Decimal("100")
MATCHA_CHAIN_ID = 8453
MATCHA_USDT_DECIMALS = 6
MATCHA_DEFAULT_SELL_DECIMALS = 18

MATCHA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://matcha.xyz",
    "Referer": "https://matcha.xyz/",
}

POLL_INTERVAL = 3.0
MAX_LOG_LINES = 10_000

import cloudscraper
http_client = cloudscraper.create_scraper(
    browser={
        "browser": "chrome",
        "platform": "windows",
        "mobile": False
    }
)

# =========================
#  Прокси: глобальная конфигурация
# =========================

_PROXY_ENABLED: bool = False
_PROXY_PROTOCOL: str = "socks5"
_PROXY_FILE_PATH: str = ""
_PROXY_LIST: List[str] = []
_CURRENT_PROXY_LINE: Optional[str] = None


def _proxy_parse_line(line: str, protocol: str) -> Optional[str]:
    """
    Преобразует строку из файла прокси в URL вида:
    - socks5://login:pass@ip:port
    - http://login:pass@ip:port
    Если в строке уже есть '://', возвращаем как есть.
    """
    line = (line or "").strip()
    if not line:
        return None

    if "://" in line:
        return line

    proto = (protocol or "socks5").lower()
    if proto.startswith("socks"):
        scheme = "socks5"
    else:
        scheme = "http"

    return f"{scheme}://{line}"


def _proxy_safe_host(proxy_url: str) -> str:
    """
    Убираем логин/пароль, чтобы не светить их в логах.
    Пример:
      socks5://login:pass@1.2.3.4:5555 -> 1.2.3.4:5555
    """
    try:
        rest = proxy_url.split("://", 1)[1]
        if "@" in rest:
            rest = rest.split("@", 1)[1]
        return rest
    except Exception:
        return proxy_url


def _apply_current_proxy() -> None:
    """
    Подставляет текущий прокси (_CURRENT_PROXY_LINE) в http_client.proxies.
    """
    global http_client

    if not _CURRENT_PROXY_LINE:
        http_client.proxies = {}
        return

    proxy_url = _proxy_parse_line(_CURRENT_PROXY_LINE, _PROXY_PROTOCOL)
    if not proxy_url:
        http_client.proxies = {}
        return

    http_client.proxies = {
        "http": proxy_url,
        "https": proxy_url,
    }

    add_log(f"Прокси: выбран {_PROXY_PROTOCOL.upper()} {_proxy_safe_host(proxy_url)}")


def _pick_new_proxy() -> None:
    """
    Берёт случайную строку из _PROXY_LIST и применяет её.
    """
    global _CURRENT_PROXY_LINE

    if not _PROXY_LIST:
        add_log("Прокси: список пуст, отключаем прокси.")
        http_client.proxies = {}
        return

    _CURRENT_PROXY_LINE = random.choice(_PROXY_LIST)
    _apply_current_proxy()


def configure_proxy_settings(enabled: bool, protocol: str, file_path: str) -> None:
    """
    Включает/выключает прокси и загружает список из txt-файла.
    Вызывается из главного окна при старте и после закрытия диалога настроек.
    """
    global _PROXY_ENABLED, _PROXY_PROTOCOL, _PROXY_FILE_PATH, _PROXY_LIST, _CURRENT_PROXY_LINE

    _PROXY_ENABLED = bool(enabled)
    _PROXY_PROTOCOL = (protocol or "socks5").lower()
    _PROXY_FILE_PATH = file_path or ""
    _PROXY_LIST = []
    _CURRENT_PROXY_LINE = None

    if not _PROXY_ENABLED:
        http_client.proxies = {}
        add_log("Прокси: отключены, все запросы идут напрямую.")
        return

    p = Path(_PROXY_FILE_PATH)
    if not p.is_file():
        add_log(f"Прокси: файл не найден: {_PROXY_FILE_PATH}")
        http_client.proxies = {}
        _PROXY_ENABLED = False
        return

    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    except Exception as e:
        add_log(f"Прокси: ошибка чтения файла {_PROXY_FILE_PATH}: {e}")
        http_client.proxies = {}
        _PROXY_ENABLED = False
        return

    if not lines:
        add_log(f"Прокси: файл {_PROXY_FILE_PATH} пустой.")
        http_client.proxies = {}
        _PROXY_ENABLED = False
        return

    _PROXY_LIST = lines
    add_log(f"Прокси: загружено {len(_PROXY_LIST)} строк из файла.")
    _pick_new_proxy()


def proxy_mark_bad(reason: str = "") -> None:
    """
    Вызывается при сетевой ошибке: текущий прокси считается "умершим",
    лог красится и выбирается новый прокси.
    """
    if not _PROXY_ENABLED:
        return

    if not _CURRENT_PROXY_LINE:
        return

    try:
        proxy_url = _proxy_parse_line(_CURRENT_PROXY_LINE, _PROXY_PROTOCOL) or _CURRENT_PROXY_LINE
        safe_host = _proxy_safe_host(proxy_url)
        if reason:
            add_log(f"Прокси: не удалось использовать {safe_host}: {reason}. Берём другой.")
        else:
            add_log(f"Прокси: не удалось использовать {safe_host}. Берём другой.")
    except Exception:
        add_log("Прокси: текущий прокси не работает, выбираем другой.")

    _pick_new_proxy()

LOG_LINES: List[str] = []

BSC_RPC = "https://bsc-dataseed.binance.org"
bsc_web3 = Web3(Web3.HTTPProvider(BSC_RPC))

PANCAKE_ROUTER = bsc_web3.to_checksum_address(
    "0x10ED43C718714eb63d5aA57B78B54704E256024E"
)
BSC_USDT = bsc_web3.to_checksum_address("0x55d398326f99059fF775485246999027B3197955")

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function",
    },
]

PANCAKE_ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"}
        ],
        "name": "getAmountsOut",
        "outputs": [
            {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

pancake_router = bsc_web3.eth.contract(address=PANCAKE_ROUTER, abi=PANCAKE_ROUTER_ABI)


# ===== ОБНОВЛЕННЫЕ ФУНКЦИИ КОТОРЫЕ ИДУТ ЧЕРЕЗ BACKEND API =====

def get_pancake_price_usdt(token_address: str) -> Optional[float]:
    """
    Цена токена в USDT через DexScreener (через backend API).
    В первую очередь по PancakeSwap.
    Если нормальных Pancake-пулов нет — берём лучший пул вообще (uniswap и т.п.).
    
    ОБНОВЛЕНО: Теперь запрос идет через backend API на Render сервер.
    """
    addr = (token_address or "").strip()
    if not addr:
        return None

    try:
        client = get_client()
        response = client.get_price_pancake(addr)
        
        if response.get("status") == "ok":
            price = response.get("price")
            if price and price > 0:
                add_log(f"Pancake: 1 TOKEN ({addr}) = {price:.6f} USDT (через backend API)")
                return price
        
        add_log(f"Pancake: ошибка получения цены для {addr} через backend")
        return None
    except Exception as e:
        add_log(f"Pancake: ошибка запроса для {addr}: {e}")
        return None


def get_mexc_price(base: str, quote: str = "USDT", price_scale: Optional[int] = None) -> (
    Optional[float], Optional[float]
):
    """
    Цена фьючерсного контракта на MEXC (USDT) (через backend API).
    
    ОБНОВЛЕНО: Теперь запрос идет через backend API на Render сервер.
    """
    symbol = f"{base.upper()}_{quote.upper()}"
    try:
        client = get_client()
        response = client.get_price_mexc(symbol=symbol)
        
        if response.get("status") == "ok":
            bid = response.get("bid")
            ask = response.get("ask")
            
            bid_val = float(bid) if bid is not None else None
            ask_val = float(ask) if ask is not None else None

            # priceScale на MEXC — это КОЛИЧЕСТВО знаков после запятой
            if isinstance(price_scale, int) and price_scale >= 0:
                if bid_val is not None:
                    bid_val = round(bid_val, price_scale)
                if ask_val is not None:
                    ask_val = round(ask_val, price_scale)

            add_log(f"MEXC: {symbol} bid={bid_val}, ask={ask_val} (price_scale={price_scale}) (через backend API)")
            return bid_val, ask_val

        add_log(f"MEXC: неуспешный ответ для {symbol} через backend")
    except Exception as e:
        add_log(f"MEXC: ошибка для {symbol}: {e}")

    return None, None


def get_pancake_price(base: str, quote: str = "USDT") -> Optional[float]:
    """
    Цена одного токена на Pancake (через backend API).
    Возвращает цену в USDT.
    
    ОБНОВЛЕНО: Теперь запрос идет через backend API на Render сервер.
    """
    symbol = (base or "").upper()
    if not symbol:
        return None

    try:
        client = get_client()
        response = client.get_price_pancake_by_symbol(symbol=symbol)
        
        if response.get("status") == "ok":
            price = response.get("price")
            if price and price > 0:
                add_log(f"Pancake: {symbol} = {price:.6f} USDT (через backend API)")
                return price
        
        add_log(f"Pancake: токен {symbol} не найден через backend")
        return None

    except Exception as e:
        add_log(f"Pancake: ошибка для {symbol}: {e}")
        return None


def get_jupiter_price_usdt(mint: str, decimals: int) -> Optional[float]:
    """
    Цена 1 токена (mint) в USDT через Jupiter (через backend API).
    
    ОБНОВЛЕНО: Теперь запрос идет через backend API на Render сервер.
    """
    mint = (mint or "").strip()
    if not mint or decimals is None or decimals < 0:
        return None

    try:
        client = get_client()
        response = client.get_price_jupiter(mint=mint, decimals=decimals)
        
        if response.get("status") == "ok":
            price = response.get("price")
            if price and price > 0:
                add_log(f"Jupiter: 1 TOKEN ({mint}) = {float(price):.8f} USDT (через backend API)")
                return float(price)
        
        add_log(f"Jupiter: ошибка получения цены для {mint} через backend")
        return None

    except Exception as e:
        add_log(f"Ошибка при запросе к Jupiter для mint={mint}: {e}")
        return None


def get_matcha_price_usdt(
    token_address: str,
    token_decimals: int = MATCHA_DEFAULT_SELL_DECIMALS,
    chain_id: int = MATCHA_CHAIN_ID,
    usdt_token: str = MATCHA_USDT,
    usdt_decimals: int = MATCHA_USDT_DECIMALS,
) -> Optional[float]:
    """
    Цена 1 токена (token_address) в USDT через Matcha (через backend API).
    
    ОБНОВЛЕНО: Теперь запрос идет через backend API на Render сервер.
    """
    token_address = (token_address or "").strip()
    usdt_token = (usdt_token or "").strip()

    if not token_address or not usdt_token:
        return None
    if token_decimals is None or token_decimals < 0:
        return None
    if usdt_decimals is None or usdt_decimals < 0:
        return None

    try:
        client = get_client()
        response = client.get_price_matcha(
            address=token_address,
            token_decimals=token_decimals,
            chain_id=chain_id,
            usdt_token=usdt_token,
            usdt_decimals=usdt_decimals,
        )
        
        if response.get("status") == "ok":
            price = response.get("price")
            if price and price > 0:
                add_log(f"Matcha: 1 TOKEN ({token_address}) = {float(price):.8f} USDT (через backend API)")
                return float(price)
        
        add_log(f"Matcha: ошибка получения цены для {token_address} через backend")
        return None

    except Exception as e:
        add_log(f"Ошибка при запросе к Matcha для {token_address}: {e}")
        return None


def get_matcha_token_info(token_address: str, chain_id: int = MATCHA_CHAIN_ID) -> Optional[dict]:
    """
    Запрашивает сведения о токене: decimals, symbol, name (через backend API).
    Возвращает dict с ключами: address, decimals, symbol, name или None при ошибке.
    
    ОБНОВЛЕНО: Теперь запрос идет через backend API на Render сервер.
    """
    addr = (token_address or "").strip()
    if not addr:
        return None

    try:
        client = get_client()
        response = client.get_matcha_token_info(address=addr, chain_id=chain_id)
        
        if response.get("status") == "ok":
            data = response.get("data")
            if data:
                result = {
                    "address": data.get("address", addr),
                    "decimals": int(data.get("decimals", 18)),
                    "symbol": data.get("symbol"),
                    "name": data.get("name"),
                }
                add_log(f"Matcha token info: {result.get('symbol') or addr} decimals={result['decimals']} (через backend API)")
                return result
        
        add_log(f"Matcha token info: ошибка для {addr} через backend")
        return None

    except Exception as e:
        add_log(f"Ошибка получения meta от Matcha для {token_address}: {e}")
        return None


def _ensure_cg_coins_list() -> None:
    """
    Один раз за запуск грузим полный список монет с CoinGecko (через backend API).
    """
    global _CG_COINS_LIST, _CG_LIST_LOADED

    if _CG_LIST_LOADED:
        return

    try:
        client = get_client()
        response = client.get_coingecko_coins_list()
        
        if response.get("status") == "ok":
            coins = response.get("coins", [])
            if isinstance(coins, list):
                _CG_COINS_LIST = coins
            else:
                _CG_COINS_LIST = []
        else:
            _CG_COINS_LIST = []
        
        _CG_LIST_LOADED = True
        add_log(f"CoinGecko list: загружено {len(_CG_COINS_LIST)} монет (через backend API)")
    except Exception as e:
        add_log(f"CoinGecko list: ошибка загрузки: {e}")
        _CG_COINS_LIST = []
        _CG_LIST_LOADED = True


def _pick_coingecko_id_for_symbol(symbol: str) -> Optional[str]:
    """
    Нормализованный выбор id из списка coins/list по символу.
    Примеры:
      - SOL -> solana
      - API3 -> api3
    """
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return None

    # кеш по символу
    if symbol in _CG_SYMBOL_INDEX:
        return _CG_SYMBOL_INDEX[symbol]

    _ensure_cg_coins_list()
    if not _CG_COINS_LIST:
        return None

    sym_lower = symbol.lower()
    best_id: Optional[str] = None
    best_score: Optional[float] = None

    bad_words = (
        "wrapped", "bridge", "bridged", "staked",
        "wormhole", "peg", "binance", "binance-peg",
        "weth", "leveraged", "bull", "bear",
    )

    for item in _CG_COINS_LIST:
        try:
            sym = str(item.get("symbol") or "").upper()
            if sym != symbol:
                continue

            cid = str(item.get("id") or "")
            name = str(item.get("name") or "")
            cid_l = cid.lower()
            name_l = name.lower()

            score = 0.0

            # 1) идеальный кейс: id == symbol.lower() (API3 -> api3)
            if cid_l == sym_lower:
                score += 100.0

            # 2) имя равно символу
            if name_l == sym_lower:
                score += 50.0

            # 3) имя начинается с символа
            if name_l.startswith(sym_lower):
                score += 25.0

            # 4) без дефисов/пробелов — обычно основной коин (solana, api3)
            if "-" not in cid and " " not in cid:
                score += 10.0

            # 5) отбрасываем "плохие" слова в id
            has_bad = any(bad in cid_l for bad in bad_words)
            if has_bad:
                score -= 50.0

            if best_score is None or score > best_score:
                best_id = cid
                best_score = score

        except Exception:
            continue

    if best_id:
        _CG_SYMBOL_INDEX[symbol] = best_id
        return best_id

    return None


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    LOG_LINES.append(line)
    if len(LOG_LINES) > MAX_LOG:
        del LOG_LINES[: len(LOG_LINES) - MAX_LOG]


def log_exc(prefix: str, exc: Exception):
    """Сокращённая запись исключений в лог."""
    log(f"{prefix}: {type(exc).__name__}: {exc}")


def add_log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    LOG_LINES.append(line)
    if len(LOG_LINES) > MAX_LOG_LINES:
        del LOG_LINES[0: len(LOG_LINES) - MAX_LOG_LINES]


@dataclass
class PairConfig:
    name: str
    base: str
    quote: str = "USDT"
    dexes: Optional[List[str]] = None

    jupiter_mint: Optional[str] = None
    jupiter_decimals: Optional[int] = None

    bsc_address: Optional[str] = None

    mexc_price_scale: Optional[int] = None

    matcha_address: Optional[str] = None
    matcha_decimals: Optional[int] = None

    # CoinGecko id для капитализации (например "solana", "api3")
    cg_id: Optional[str] = None

    # флаги, по каким направлениям вообще слать оповещения
    spread_direct: bool = True
    spread_reverse: bool = True

    # СТАРОЕ: общий порог спреда (оставляем для совместимости со старым tokens.json)
    spread_threshold: Optional[float] = None

    # НОВОЕ: отдельные пороги для прямого и обратного спреда (%, можно None)
    spread_direct_threshold: Optional[float] = None
    spread_reverse_threshold: Optional[float] = None


PAIRS: Dict[str, PairConfig] = {}

_CG_COINS_LIST: List[dict] = []
_CG_LIST_LOADED: bool = False
_CG_SYMBOL_INDEX: Dict[str, str] = {}


# ===== ОСТАЛЬНЫЕ ФУНКЦИИ ОСТАЮТСЯ БЕЗ ИЗМЕНЕНИЙ =====
# Скопируйте остальные функции из оригинального core.py
# которые не делают прямые HTTP запросы к Jupiter, PancakeSwap, MEXC, Matcha, CoinGecko

def get_dexscreener_pairs(base: str, quote: str):
    """Получить пары из DexScreener (через backend API)"""
    q = f"{base.upper()}/{quote.upper()}"
    try:
        client = get_client()
        response = client.search_dexscreener(query=q)
        
        if response.get("status") == "ok":
            results = response.get("results", [])
            add_log(f"DexScreener: найдено {len(results)} пар для {q} (через backend API)")
            return results
        
        add_log(f"DexScreener: ошибка поиска для {q} через backend")
        return []
    except Exception as e:
        add_log(f"DexScreener: ошибка для {q}: {e}")
        return []


def search_dexscreener(query: str) -> Optional[List[Dict]]:
    """
    Поиск токенов в DexScreener (через backend API).
    
    ОБНОВЛЕНО: Теперь запрос идет через backend API на Render сервер.
    """
    q = (query or "").strip()
    if not q:
        return None

    try:
        client = get_client()
        response = client.search_dexscreener(query=q)
        
        if response.get("status") == "ok":
            results = response.get("results", [])
            add_log(f"DexScreener Search: найдено {len(results)} результатов для '{q}' (через backend API)")
            return results
        
        return None
    except Exception as e:
        add_log(f"DexScreener Search: ошибка поиска '{q}': {e}")
        return None


def get_pancake_tokens_list() -> Optional[Dict]:
    """
    Получить список всех токенов с PancakeSwap (через backend API).
    
    ОБНОВЛЕНО: Теперь запрос идет через backend API на Render сервер.
    """
    try:
        client = get_client()
        response = client.get_pancake_tokens_list()
        
        if response.get("status") == "ok":
            tokens = response.get("tokens", {})
            add_log(f"PancakeSwap: загружено {len(tokens)} токенов (через backend API)")
            return tokens
        
        return None
    except Exception as e:
        add_log(f"PancakeSwap: ошибка получения списка токенов: {e}")
        return None


def get_coingecko_coins_list() -> Optional[List[Dict]]:
    """
    Получить список всех монет с CoinGecko (через backend API).
    
    ОБНОВЛЕНО: Теперь запрос идет через backend API на Render сервер.
    """
    try:
        client = get_client()
        response = client.get_coingecko_coins_list()
        
        if response.get("status") == "ok":
            coins = response.get("coins", [])
            add_log(f"CoinGecko: загружено {len(coins)} монет (через backend API)")
            return coins
        
        return None
    except Exception as e:
        add_log(f"CoinGecko: ошибка получения списка монет: {e}")
        return None


def get_coingecko_markets(ids: str, vs_currency: str = "usd") -> Optional[List[Dict]]:
    """
    Получить информацию о монетах с CoinGecko (через backend API).
    
    ОБНОВЛЕНО: Теперь запрос идет через backend API на Render сервер.
    """
    if not ids:
        return None

    try:
        client = get_client()
        response = client.get_coingecko_markets(ids=ids, vs_currency=vs_currency)
        
        if response.get("status") == "ok":
            markets = response.get("markets", [])
            add_log(f"CoinGecko Markets: получено {len(markets)} монет (через backend API)")
            return markets
        
        return None
    except Exception as e:
        add_log(f"CoinGecko Markets: ошибка получения данных: {e}")
        return None


def fetch_L_M_for_pair(pair_cfg) -> Optional[Dict[str, float]]:
    """
    Получить L и M для пары (Liquidity и Market Cap) (через backend API).
    
    ОБНОВЛЕНО: Теперь использует backend API для получения данных.
    """
    if not pair_cfg or not pair_cfg.bsc_address:
        return None

    try:
        client = get_client()
        
        # Получить данные через DexScreener
        response = client.get_price_dex(address=pair_cfg.bsc_address)
        
        if response.get("status") == "ok":
            raw_data = response.get("raw", {})
            pairs = raw_data.get("pairs", [])
            if not pairs:
                return None
            
            # Берем первую пару (лучшую по ликвидности)
            pair = pairs[0]
            liquidity = pair.get("liquidity", {})
            
            return {
                "L": float(liquidity.get("usd", 0) or 0),
                "M": float(pair.get("marketCap", 0) or 0),
            }
        
        return None
    except Exception as e:
        add_log(f"Fetch L/M: ошибка для {pair_cfg.bsc_address}: {e}")
        return None


# ===== ИНИЦИАЛИЗАЦИЯ =====

def initialize_api_client():
    """
    Инициализировать API клиент при старте приложения.
    """
    try:
        backend_url = os.getenv("BACKEND_URL", "https://hydra-tra4.onrender.com")
        admin_token = os.getenv("ADMIN_TOKEN", "")
        
        client = get_client(base_url=backend_url, admin_token=admin_token)
        add_log(f"API Client инициализирован: {backend_url}")
        return client
    except Exception as e:
        add_log(f"Ошибка инициализации API Client: {e}")
        return None


def close_api_client():
    """
    Закрыть API клиент при завершении приложения.
    """
    try:
        from api_client import close_client
        close_client()
        add_log("API Client закрыт")
    except Exception as e:
        add_log(f"Ошибка закрытия API Client: {e}")
