# core.py
import httpx
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
from typing import Optional
import random
from concurrent.futures import ThreadPoolExecutor


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
JUPITER_USDT_DECIMALS = 6


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

    # лог будет красным, если что-то не так с сеткой (по словам "ошибка"/"не удалось"),
    # но здесь просто информируем:
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


def get_pancake_price_usdt(token_address: str) -> Optional[float]:
    """
    Цена токена в USDT через DexScreener, в первую очередь по PancakeSwap.
    Если нормальных Pancake-пулов нет — берём лучший пул вообще (uniswap и т.п.).
    """
    addr = (token_address or "").strip()
    if not addr:
        return None

    url = f"{DEXSCREENER_TOKENS_URL}/{addr}"

    try:
        resp = http_client.get(url, timeout=DEXSCREENER_TIMEOUT)
        if resp.status_code != 200:
            add_log(f"Pancake: HTTP {resp.status_code} для {addr}")
            return None

        data = resp.json()
    except Exception as e:
        add_log(f"Pancake: ошибка запроса для {addr}: {e}")
        proxy_mark_bad(str(e))
        return None

    pairs = data.get("pairs") or []
    if not isinstance(pairs, list) or not pairs:
        add_log(f"Pancake: нет маркетов для токена {addr}")
        return None

    def liq_usd_val(p: dict) -> float:
        liq = p.get("liquidity") or {}
        try:
            return float(liq.get("usd") or 0.0)
        except Exception:
            return 0.0

    pancake_pairs: List[dict] = []
    best_any_pair: Optional[dict] = None

    for pair in pairs:
        dex_id = str(pair.get("dexId", "")).lower()
        price_str = pair.get("priceUsd")
        if price_str is None:
            continue

        # читаем цену и сразу режем явный мусор
        try:
            price_val = float(price_str)
        except Exception:
            continue
        if price_val <= 0 or price_val > 1_000_000:
            # отбрасываем дичь типа 3e20 и т.п.
            continue

        liq_val = liq_usd_val(pair)
        if liq_val <= 0:
            # без ликвидности не интересует
            continue

        # кандидаты именно PancakeSwap
        if "pancake" in dex_id:
            pancake_pairs.append(pair)

        # параллельно запоминаем лучший пул вообще
        if best_any_pair is None or liq_val > liq_usd_val(best_any_pair):
            best_any_pair = pair

    if pancake_pairs:
        best = max(pancake_pairs, key=liq_usd_val)
        source = "pancake"
    elif best_any_pair is not None:
        best = best_any_pair
        source = str(best.get("dexId", "unknown"))
        add_log(
            f"Pancake: нет адекватного PancakeSwap пула для {addr}, "
            f"использую пул dexId={source} из DexScreener"
        )
    else:
        add_log(f"Pancake: нет ни одного подходящего пула для {addr}")
        return None

    try:
        price = float(best.get("priceUsd"))
    except Exception as e:
        add_log(f"Pancake: ошибка чтения priceUsd для {addr}: {e}")
        return None

    add_log(
        f"Pancake: 1 TOKEN ({addr}) = {price:.6f} USDT (dexId={source})"
    )
    return price


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


from typing import Optional, List  # как уже есть сверху
from dataclasses import dataclass


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


def _ensure_cg_coins_list() -> None:
    """
    Один раз за запуск грузим полный список монет с CoinGecko,
    чтобы потом быстро по нему искать id по символу.
    """
    global _CG_COINS_LIST, _CG_LIST_LOADED

    if _CG_LIST_LOADED:
        return

    try:
        resp = http_client.get(
            "https://api.coingecko.com/api/v3/coins/list",
            timeout=20.0,
        )
        if resp.status_code != 200:
            add_log(
                f"CoinGecko list: HTTP {resp.status_code}: "
                f"{str(resp.text)[:150]}"
            )
            _CG_COINS_LIST = []
            _CG_LIST_LOADED = True
            return

        data = resp.json()
        if isinstance(data, list):
            _CG_COINS_LIST = data
        else:
            _CG_COINS_LIST = []
        _CG_LIST_LOADED = True
        add_log(f"CoinGecko list: загружено {_CG_COINS_LIST.__len__()} монет")
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

            # 5) штраф за "плохие" слова — мосты, стейки и т.п.
            if any(w in cid_l for w in bad_words) or any(
                w in name_l for w in bad_words
            ):
                score -= 30.0

            # 6) слегка штрафуем за длину id (короче == лучше)
            score -= len(cid) * 0.01

            if best_score is None or score > best_score:
                best_score = score
                best_id = cid
        except Exception:
            continue

    if best_id:
        _CG_SYMBOL_INDEX[symbol] = best_id
        add_log(f"CoinGecko: {symbol} -> id={best_id}")
    else:
        add_log(f"CoinGecko: не нашёл id для символа {symbol}")

    return best_id


def fetch_L_M_for_pair(pair_cfg: PairConfig) -> Optional[Dict[str, float]]:
    """
    Получить:
    - price_mexc: текущая цена с MEXC (spot, 24h ticker)
    - L: ликвидность за 24 часа (quoteVolume, USDT)
    - M: глобальная капитализация с CoinGecko

    Основано на тикере BASE/USDT:
    - MEXC symbol: BASEUSDT
    - CoinGecko id: cg_id из PairConfig, либо подбирается по symbol (SOL -> solana и т.п.)
    """
    base = (getattr(pair_cfg, "base", "") or "").upper().strip()
    if not base:
        return None

    price_mexc: Optional[float] = None
    L: Optional[float] = None
    M: Optional[float] = None

    # ---------- MEXC: 24h тикер (ликвидность L) ----------
    symbol_fut = f"{base}_USDT"
    try:
        r = http_client.get(
            "https://contract.mexc.com/api/v1/contract/ticker",
            params={"symbol": symbol_fut},
            timeout=10.0,
        )
        if r.status_code != 200:
            add_log(
                f"MEXC L/M futures: HTTP {r.status_code} для {symbol_fut}: "
                f"{str(r.text)[:200]}"
            )
        else:
            data = r.json()
            if data.get("success"):
                t = data.get("data") or {}
                # Цена берём lastPrice с фьючерсов
                try:
                    price_mexc = float(t.get("lastPrice") or 0.0)
                except Exception:
                    price_mexc = None
                # Ликвидность L = оборот за 24ч в валюте (USDT)
                try:
                    L = float(t.get("amount24") or 0.0)
                except Exception:
                    L = None
            else:
                add_log(
                    f"MEXC L/M futures: code={data.get('code')} "
                    f"msg={data.get('message')} для {symbol_fut}"
                )
    except Exception as e:
        add_log(f"MEXC L/M futures: ошибка для {symbol_fut}: {e}")

    # ---------- CoinGecko: капитализация M ----------
    cg_id = getattr(pair_cfg, "cg_id", None)
    if not cg_id:
        cg_id = _pick_coingecko_id_for_symbol(base) or base.lower()
        # запомним в конфиге, чтобы потом сохранить в tokens.json
        try:
            pair_cfg.cg_id = cg_id
        except Exception:
            pass

    if cg_id:
        try:
            r = http_client.get(
                "https://api.coingecko.com/api/v3/coins/markets",
                params={"vs_currency": "usd", "ids": cg_id},
                timeout=10.0,
            )
            if r.status_code != 200:
                add_log(
                    f"CoinGecko M: HTTP {r.status_code} для {cg_id}: "
                    f"{str(r.text)[:150]}"
                )
            else:
                data = r.json()
                if isinstance(data, list) and data:
                    item = data[0]
                    try:
                        M = float(item.get("market_cap") or 0.0)
                    except Exception:
                        M = None
        except Exception as e:
            add_log(f"CoinGecko M: ошибка для {cg_id}: {e}")

    # если вообще ничего не удалось — вернуть None
    if price_mexc is None and L is None and M is None:
        return None

    return {
        "price_mexc": price_mexc,
        "L": L,
        "M": M,
    }




# --- директории ---
if getattr(sys, "frozen", False):
    # exe: сюда будем писать tokens.json / settings.json (рядом с .exe)
    BASE_DIR = Path(sys.executable).resolve().parent
    # а тут лежат ресурсы, упакованные PyInstaller (--add-data)
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
else:
    # обычный запуск из .py
    BASE_DIR = Path(__file__).resolve().parent
    RESOURCE_DIR = BASE_DIR

# файлы данных (должны быть в записываемой директории)
_TOKENS_FILE = BASE_DIR / "tokens.json"
_SETTINGS_FILE = BASE_DIR / "settings.json"

# чтобы относительные пути в стилях (Icon/arrow_up.png) искались в папке ресурсов
os.chdir(RESOURCE_DIR)

# --- создаём файл автоматически, если он отсутствует ---
if not _TOKENS_FILE.exists():
    try:
        default_data = {
            "pairs": [],
            "favorites": []
        }
        _TOKENS_FILE.write_text(
            json.dumps(default_data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        # лучше в лог, если уже есть log()
        try:
            print(f"Ошибка создания tokens.json: {e}")
        except:
            pass
if not _TOKENS_FILE.exists():
    _TOKENS_FILE.write_text(json.dumps({"pairs": [], "favorites": []}, indent=2, ensure_ascii=False), encoding="utf-8")


_SETTINGS_FILE = BASE_DIR / "settings.json"

_DEFAULT_SETTINGS = {
    "telegram_chat_id": "",
    "telegram_token": "",
    "interval_sec": 3.0,
    "favorites": [],
    "dex_states": {},
    "cex_states": {},
    "mode_states": {},
    "spread_direct_palette": "green",
    "spread_reverse_palette": "red",
    "main_positive_spread_color": "green",  # ключ палитры
    "main_negative_spread_color": "red",    # ключ палитры
    "spread_pairs": [],
    "notifications_enabled": True,
    "notifications_max_count": 3,

    # --- новые поля для прокси ---
    "proxy_enabled": False,
    "proxy_protocol": "socks5",   # "socks5" или "http"
    "proxy_file_path": "",
}


def load_settings() -> dict:
    """
    Загружаем настройки из settings.json.
    Если файла нет / он битый — возвращаем дефолт.
    """
    if not _SETTINGS_FILE.exists():
        return _DEFAULT_SETTINGS.copy()

    try:
        raw = _SETTINGS_FILE.read_text(encoding="utf-8")
        if not raw.strip():
            return _DEFAULT_SETTINGS.copy()
        data = json.loads(raw)
        if not isinstance(data, dict):
            return _DEFAULT_SETTINGS.copy()
    except Exception as e:
        try:
            log(f"Ошибка чтения {_SETTINGS_FILE.name}: {e}")
        except Exception:
            pass
        return _DEFAULT_SETTINGS.copy()

    cfg = _DEFAULT_SETTINGS.copy()
    cfg.update({k: v for k, v in data.items() if k in cfg})

    # нормализуем интервал опроса
    try:
        iv = float(cfg.get("interval_sec", POLL_INTERVAL))
        if iv <= 0:
            iv = POLL_INTERVAL
        cfg["interval_sec"] = iv
    except Exception:
        cfg["interval_sec"] = POLL_INTERVAL

    # нормализуем флаг экранных уведомлений
    cfg["notifications_enabled"] = bool(cfg.get("notifications_enabled", True))

    # нормализуем количество одновременно отображаемых уведомлений
    try:
        mc = int(cfg.get("notifications_max_count", 1))
        if mc <= 0:
            mc = 1
        cfg["notifications_max_count"] = mc
    except Exception:
        cfg["notifications_max_count"] = 1

    return cfg


def save_settings(
        telegram_chat_id: str,
        telegram_token: str,
        interval_sec: float,
        *,
        favorites=None,
        dex_states=None,
        cex_states=None,
        mode_states=None,
        spread_direct_palette: Optional[str] = None,
        spread_reverse_palette: Optional[str] = None,
        spread_pairs=None,
        notif_enabled: Optional[bool] = None,
        notif_max_count: Optional[int] = None,
        # --- новые аргументы ---
        proxy_enabled: Optional[bool] = None,
        proxy_protocol: Optional[str] = None,
        proxy_file_path: Optional[str] = None,
        main_positive_spread_color: Optional[str] = None,
        main_negative_spread_color: Optional[str] = None,
) -> dict:
    """
    Сохраняем настройки в settings.json.
    Создаём файл, если его ещё нет.
    """
    try:
        iv = float(interval_sec)
        if iv <= 0:
            iv = POLL_INTERVAL
    except Exception:
        iv = POLL_INTERVAL

    # читаем существующий файл, чтобы не потерять чужие ключи
    data: dict = {}
    if _SETTINGS_FILE.exists():
        try:
            raw = _SETTINGS_FILE.read_text(encoding="utf-8")
            if raw.strip():
                loaded = json.loads(raw)
                if isinstance(loaded, dict):
                    data.update(loaded)
        except Exception as e:
            try:
                log(f"Ошибка чтения {_SETTINGS_FILE.name} перед записью: {e}")
            except Exception:
                pass

    # обновляем базовые поля
    data["telegram_chat_id"] = telegram_chat_id or ""
    data["telegram_token"] = telegram_token or ""
    data["interval_sec"] = iv

    # --- настройки уведомлений ---
    if notif_enabled is not None:
        data["notifications_enabled"] = bool(notif_enabled)

    if notif_max_count is not None:
        try:
            mc = int(notif_max_count)
            if mc <= 0:
                mc = 1
        except Exception:
            mc = 3
        data["notifications_max_count"] = mc

    # --- новые поля прокси ---
    if proxy_enabled is not None:
        data["proxy_enabled"] = bool(proxy_enabled)

    if proxy_protocol is not None:
        data["proxy_protocol"] = str(proxy_protocol)

    if proxy_file_path is not None:
        data["proxy_file_path"] = str(proxy_file_path)

    # --- палитры цвета спреда ---
    if spread_direct_palette is not None:
        data["spread_direct_palette"] = str(spread_direct_palette)
    if spread_reverse_palette is not None:
        data["spread_reverse_palette"] = str(spread_reverse_palette)

    if main_positive_spread_color is not None:
        data["main_positive_spread_color"] = str(main_positive_spread_color)
    if main_negative_spread_color is not None:
        data["main_negative_spread_color"] = str(main_negative_spread_color)

    try:
        _SETTINGS_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        try:
            log(f"Ошибка записи {_SETTINGS_FILE.name}: {e}")
        except Exception:
            pass

def save_pairs_and_favorites(pairs: Dict[str, "PairConfig"], favorites: set) -> None:
    try:
        pairs_list = []
        for p in pairs.values():
            item = {
                "name": p.name,
                "base": p.base,
                "quote": p.quote,
            }

            if getattr(p, "dexes", None):
                item["dexes"] = p.dexes
            if getattr(p, "jupiter_mint", None):
                item["jupiter_mint"] = p.jupiter_mint
            if getattr(p, "jupiter_decimals", None) is not None:
                item["jupiter_decimals"] = p.jupiter_decimals
            if getattr(p, "bsc_address", None):
                item["bsc_address"] = p.bsc_address
            if getattr(p, "mexc_price_scale", None) is not None:
                item["mexc_price_scale"] = p.mexc_price_scale
            if getattr(p, "matcha_address", None):
                item["matcha_address"] = p.matcha_address
            if getattr(p, "matcha_decimals", None) is not None:
                item["matcha_decimals"] = p.matcha_decimals

            if getattr(p, "cg_id", None):
                item["cg_id"] = p.cg_id
            item["spread_direct"] = bool(getattr(p, "spread_direct", True))
            item["spread_reverse"] = bool(getattr(p, "spread_reverse", True))

            # общий порог (для старых версий)
            thr_common = getattr(p, "spread_threshold", None)
            if thr_common is not None:
                try:
                    item["spread_threshold"] = float(thr_common)
                except Exception:
                    pass

            # НОВОЕ: отдельные пороги прямой/обратный
            thr_dir = getattr(p, "spread_direct_threshold", None)
            if thr_dir is not None:
                try:
                    item["spread_direct_threshold"] = float(thr_dir)
                except Exception:
                    pass

            thr_rev = getattr(p, "spread_reverse_threshold", None)
            if thr_rev is not None:
                try:
                    item["spread_reverse_threshold"] = float(thr_rev)
                except Exception:
                    pass




            pairs_list.append(item)

        data = {
            "pairs": pairs_list,
            "favorites": list(favorites),
        }

        _TOKENS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        try:
            log(f"Ошибка сохранения {_TOKENS_FILE.name}: {e}")
        except Exception:
            pass


def load_saved_pairs_and_favorites() -> set:
    """
    Загружаем пары и избранные токены из файла tokens.json.
    Наполняем глобальный словарь PAIRS и возвращаем set избранных имён пар.
    """
    favs: set = set()

    if not _TOKENS_FILE.exists():
        return favs

    try:
        raw = _TOKENS_FILE.read_text(encoding="utf-8")
        data = json.loads(raw) if raw.strip() else {}
    except Exception as e:
        try:
            log(f"Ошибка чтения {_TOKENS_FILE.name}: {e}")
        except Exception:
            pass
        return favs

    pairs_data = data.get("pairs") or []
    for item in pairs_data:
        try:
            name = item.get("name")
            if not name:
                continue

            base = item.get("base") or name.split("-")[0]
            if "-" in name:
                quote = item.get("quote") or name.split("-")[1]
            else:
                quote = item.get("quote") or "USDT"

            dexes = item.get("dexes") or None

            j_mint = item.get("jupiter_mint")
            j_dec = item.get("jupiter_decimals")
            bsc_addr = item.get("bsc_address")
            mexc_ps = item.get("mexc_price_scale")
            matcha_address = item.get("matcha_address")
            matcha_decimals = item.get("matcha_decimals")

            spread_direct = item.get("spread_direct", True)
            spread_reverse = item.get("spread_reverse", True)

            # общий порог (старое поле)
            spread_threshold = item.get("spread_threshold")

            # НОВОЕ: отдельные пороги, могут отсутствовать в старом файле
            spread_direct_threshold = item.get("spread_direct_threshold")
            spread_reverse_threshold = item.get("spread_reverse_threshold")

            cg_id = item.get("cg_id")

            PAIRS[name] = PairConfig(
                name=name,
                base=base,
                quote=quote,
                dexes=dexes,
                jupiter_mint=j_mint,
                jupiter_decimals=j_dec,
                bsc_address=bsc_addr,
                mexc_price_scale=mexc_ps,
                matcha_address=matcha_address,
                matcha_decimals=matcha_decimals,
                cg_id=cg_id,
                spread_direct=spread_direct,
                spread_reverse=spread_reverse,
                spread_threshold=spread_threshold,
                spread_direct_threshold=spread_direct_threshold,
                spread_reverse_threshold=spread_reverse_threshold,
            )
        except Exception as e:
            try:
                log(f"Ошибка разбора пары из {_TOKENS_FILE.name}: {e}")
            except Exception:
                pass
            continue

    favs_list = data.get("favorites") or []
    try:
        favs = set(str(x) for x in favs_list)
    except Exception as e:
        try:
            log(f"Ошибка чтения favorites из {_TOKENS_FILE.name}: {e}")
        except Exception:
            pass

    return favs


def get_mexc_price(base: str, quote: str = "USDT", price_scale: Optional[int] = None) -> (
    Optional[float], Optional[float]
):
    """Цена фьючерсного контракта на MEXC (USDT)."""
    symbol = f"{base.upper()}_{quote.upper()}"
    try:
        r = http_client.get(
            f"{MEXC_FUTURES_BASE}/api/v1/contract/ticker",
            params={"symbol": symbol},
        )
        j = r.json()
        if j.get("success") and j.get("code") == 0 and j.get("data"):
            data = j["data"]
            bid = data.get("bid1")
            ask = data.get("ask1")

            bid_val = float(bid) if bid is not None else None
            ask_val = float(ask) if ask is not None else None

            # priceScale на MEXC — это КОЛИЧЕСТВО знаков после запятой, а не множитель.
            # Используем его только для округления, но не делим на 10**priceScale.
            if isinstance(price_scale, int) and price_scale >= 0:
                if bid_val is not None:
                    bid_val = round(bid_val, price_scale)
                if ask_val is not None:
                    ask_val = round(ask_val, price_scale)

            add_log(f"MEXC: {symbol} bid={bid_val}, ask={ask_val} (price_scale={price_scale})")
            return bid_val, ask_val

        add_log(f"MEXC: неуспешный ответ для {symbol}: {j}")
    except Exception as e:
        add_log(f"MEXC: ошибка для {symbol}: {e}")

    return None, None

    return None, None


def get_pancake_price(base: str, quote: str = "USDT") -> Optional[float]:
    """
    Цена одного токена на Pancake (через https://api.pancakeswap.info/api/tokens).
    Возвращает цену в USDT (берём price в USD и считаем, что USDT ≈ 1 USD).
    """
    symbol = (base or "").upper()
    if not symbol:
        return None

    try:
        r = http_client.get(PANCAKE_TOKENS_API)
        j = r.json()
        data = j.get("data") or {}

        best_price = None

        for addr, info in data.items():
            try:
                if str(info.get("symbol", "")).upper() != symbol:
                    continue

                price_str = info.get("price")
                if not price_str:
                    continue

                price = float(price_str)

                # Если вдруг несколько токенов с одинаковым символом —
                # берём первую или более "дорогую" запись.
                if best_price is None or price > best_price:
                    best_price = price
            except Exception:
                # Один кривой токен не должен ломать всё
                continue

        if best_price is None:
            add_log(f"Pancake: токен {symbol} не найден в /api/tokens")
        return best_price

    except Exception as e:
        add_log(f"Pancake: ошибка для {symbol}: {e}")
        return None


def get_jupiter_price_usdt(mint: str, decimals: int) -> Optional[float]:
    """
    Цена 1 токена (mint) в USDT через Jupiter ultra-api /order.

    Логика:
      - отправляем фиксированные 100 USDT (ExactIn) как inputMint = USDT;
      - читаем, сколько токенов получили (outAmount);
      - цена 1 токена = 100 USDT / полученное количество токенов.
    """
    mint = (mint or "").strip()
    if not mint or decimals is None or decimals < 0:
        return None

    # raw-количество USDT для отправки (100 USDT * 10^6)
    try:
        usdt_amount_raw = int(JUPITER_USDT_AMOUNT * (Decimal(10) ** JUPITER_USDT_DECIMALS))
    except Exception as e:
        add_log(f"Jupiter price: ошибка подготовки суммы USDT: {e}")
        return None

    try:
        resp = http_client.get(
            JUPITER_QUOTE_URL,
            params={
                "inputMint": JUPITER_USDT_MINT,  # отдаём USDT
                "outputMint": mint,              # получаем наш токен
                "amount": str(usdt_amount_raw),  # 100 USDT в raw
                "swapMode": "ExactIn",
            },
            timeout=1.0,
        )

        if resp.status_code != 200:
            add_log(
                f"Jupiter order HTTP {resp.status_code} для mint={mint}: "
                f"{resp.text[:150]}"
            )
            return None

        data = resp.json()

        # Для /order нам нужен только outAmount (кол-во токенов)
        out_amount_str = data.get("outAmount")
        if not out_amount_str:
            add_log(f"Jupiter order: нет outAmount для mint={mint}: {data}")
            return None

        try:
            out_amount_raw = int(out_amount_str)
        except Exception as e:
            add_log(
                f"Jupiter order: некорректный outAmount для mint={mint}: "
                f"{out_amount_str} ({e})"
            )
            return None

        if out_amount_raw <= 0:
            return None

        # нормализуем количество токенов по decimals
        token_amount = Decimal(out_amount_raw) / (Decimal(10) ** decimals)
        if token_amount <= 0:
            return None

        # цена 1 токена в USDT: 100 / кол-во токенов
        price = JUPITER_USDT_AMOUNT / token_amount

        add_log(
            f"Jupiter: 1 TOKEN ({mint}) = {float(price):.8f} USDT "
            f"(через {JUPITER_USDT_AMOUNT} USDT ExactIn)"
        )
        return float(price)

    except Exception as e:
        add_log(f"Ошибка при запросе к Jupiter order для mint={mint}: {e}")
        return None

def get_matcha_price_usdt(
    token_address: str,
    token_decimals: int = MATCHA_DEFAULT_SELL_DECIMALS,
    chain_id: int = MATCHA_CHAIN_ID,
    usdt_token: str = MATCHA_USDT,
    usdt_decimals: int = MATCHA_USDT_DECIMALS,
) -> Optional[float]:
    """
    Цена 1 токена (token_address) в USDT через Matcha (0x gasless API).

    Логика:
      - всегда отправляем MATCHA_USDT_AMOUNT USDT (ExactIn)
      - sellToken = USDT, buyToken = наш токен
      - берём buyAmount (кол-во токенов)
      - цена 1 токена = MATCHA_USDT_AMOUNT / кол-во токенов.
    """
    token_address = (token_address or "").strip()
    usdt_token = (usdt_token or "").strip()

    if not token_address or not usdt_token:
        return None
    if token_decimals is None or token_decimals < 0:
        return None
    if usdt_decimals is None or usdt_decimals < 0:
        return None

    # сырой sellAmount для USDT: 100 * 10^6
    try:
        sell_amount_raw = int(
            MATCHA_USDT_AMOUNT * (Decimal(10) ** int(usdt_decimals))
        )
    except Exception:
        return None

    try:
        resp = http_client.get(
            MATCHA_PRICE_URL,
            params={
                "chainId": chain_id,
                "sellToken": usdt_token,          # отдаём USDT
                "buyToken": token_address,        # получаем наш токен
                "sellAmount": str(sell_amount_raw),
                "useIntents": "true",
            },
            headers=MATCHA_HEADERS,
        )
        if resp.status_code != 200:
            add_log(
                f"Matcha price HTTP {resp.status_code} для {token_address}: "
                f"{resp.text[:150]}"
            )
            return None

        data = resp.json()

        s_raw = data.get("sellAmount")
        b_raw = data.get("buyAmount")

        if not s_raw or not b_raw:
            add_log(
                f"Matcha price: нет sellAmount/buyAmount для {token_address}"
            )
            return None

        try:
            s_amt = Decimal(str(s_raw))
            b_amt = Decimal(str(b_raw))
        except Exception as e:
            add_log(f"Matcha price: ошибка конвертации чисел: {e}")
            return None

        if s_amt <= 0 or b_amt <= 0:
            return None

        # нормализуем количество токенов по их decimals
        token_amount = b_amt / (Decimal(10) ** token_decimals)
        if token_amount <= 0:
            return None

        # Цена 1 токена в USDT: 100 / кол-во токенов
        price = MATCHA_USDT_AMOUNT / token_amount

        add_log(
            f"Matcha: 1 TOKEN ({token_address}) = {float(price):.8f} USDT "
            f"(через {MATCHA_USDT_AMOUNT} USDT, chainId={chain_id})"
        )

        return float(price)

    except Exception as e:
        add_log(f"Ошибка при запросе к Matcha для {token_address}: {e}")
        return None


def get_matcha_token_info(token_address: str, chain_id: int = MATCHA_CHAIN_ID) -> Optional[dict]:
    """
    Запрашивает у matcha.xyz сведения о токене: decimals, symbol, name.
    Возвращает dict с ключами: address, decimals, symbol, name  или None при ошибке.
    """
    addr = (token_address or "").strip()
    if not addr:
        return None

    try:
        url = "https://matcha.xyz/api/tokens/search"
        params = {"addresses": addr, "chainId": chain_id}

        # MATCHA_HEADERS определены в том же модуле
        resp = http_client.get(url, params=params, headers=MATCHA_HEADERS, timeout=6.0)
        if resp.status_code != 200:
            add_log(f"Matcha token info HTTP {resp.status_code} для {addr}: {resp.text[:150]}")
            return None

        j = resp.json()
        data = j.get("data") or []
        if not data or not isinstance(data, list):
            add_log(f"Matcha token info: пустой data для {addr}")
            return None

        # Иногда API возвращает несколько записей — берём первую
        info = data[0]
        decimals = info.get("decimals")
        symbol = info.get("symbol")
        name = info.get("name")
        address = info.get("address") or addr

        # валидация
        if decimals is None:
            add_log(f"Matcha token info: нет decimals для {addr}")
            return None

        result = {
            "address": address,
            "decimals": int(decimals),
            "symbol": symbol,
            "name": name,
        }
        add_log(f"Matcha token info: {symbol or address} decimals={result['decimals']}")
        return result

    except Exception as e:
        add_log(f"Ошибка получения meta от Matcha для {token_address}: {e}")
        return None



def get_dexscreener_pairs(base: str, quote: str):
    q = f"{base.upper()}/{quote.upper()}"
    try:
        r = http_client.get(DEXSCREENER_SEARCH_URL, params={"q": q})
        if r.status_code != 200:
            add_log(f"Pancake HTTP {r.status_code} для {q}: {r.text[:150]}")
            return []
        data = r.json()
        pairs = data.get("pairs") or []
        if not isinstance(pairs, list):
            add_log(f"Pancake: неверный формат ответа для {q}")
            return []
        return pairs
    except Exception as e:
        add_log(f"Pancake: ошибка для {q}: {e}")
        return []


def pick_price_for_dex(pairs, base: str, quote: str, dex: str) -> Optional[float]:
    base_u = base.upper()
    quote_u = quote.upper()
    cands: List[dict] = []

    for p in pairs:
        bt = p.get("baseToken") or {}
        qt = p.get("quoteToken") or {}
        bt_sym = str(bt.get("symbol", "")).upper()
        qt_sym = str(qt.get("symbol", "")).upper()
        chain = str(p.get("chainId", "")).lower()
        dex_id = str(p.get("dexId", "")).lower()

        if bt_sym != base_u:
            continue
        if quote_u and qt_sym != quote_u:
            continue

        if dex == "pancake":
            if not dex_id.startswith("pancakeswap"):
                continue
        elif dex == "jupiter":
            if chain != "solana":
                continue
        elif dex == "matcha":
            if chain not in ("ethereum", "arbitrum", "optimism", "polygon"):
                continue

        cands.append(p)

    if not cands:
        return None

    def liq_usd(pair: dict) -> float:
        liq = pair.get("liquidity") or {}
        try:
            return float(liq.get("usd") or 0)
        except Exception:
            return 0.0

    best = max(cands, key=liq_usd)
    try:
        return float(best.get("priceUsd"))
    except Exception as e:
        add_log(f"Pancake: ошибка конвертации priceUsd: {e}")
        return None


def calc_spread(cex_bid: float, cex_ask: float, dex_price: float):
    if dex_price is None or dex_price <= 0:
        return None, None

    # прямой спред — продаём на MEXC по bid1
    direct = None
    if cex_bid and cex_bid > 0:
        direct = (cex_bid - dex_price) / dex_price * 100.0

    # обратный спред — покупаем на MEXC по ask1
    reverse = None
    if cex_ask and cex_ask > 0:
        reverse = (dex_price - cex_ask) / cex_ask * 100.0

    return direct, reverse


class PriceWorker(QThread):
    data_ready = pyqtSignal(dict)

    def __init__(self, pairs, interval: float = POLL_INTERVAL):
        super().__init__()
        self.pairs = pairs
        self.interval = interval
        self._running = True

    def _process_pair(self, name, cfg):
        """
        Обработка одной пары в отдельном потоке.
        Это тот же код, что раньше был внутри цикла for name, cfg in self.pairs.items().
        """
        try:
            base = cfg.base.upper()
            quote = cfg.quote.upper()

            # -------------- CEX (MEXC) --------------
            cex_bid, cex_ask = get_mexc_price(base, quote, cfg.mexc_price_scale)

            allowed = set(cfg.dexes) if cfg.dexes else set()

            # если dexes явно не указаны — включаем только те DEX,
            # для которых реально есть данные в cfg
            if not cfg.dexes:
                has_any_addr = False

                if getattr(cfg, "bsc_address", None):
                    allowed.add("pancake")
                    has_any_addr = True

                if getattr(cfg, "jupiter_mint", None):
                    allowed.add("jupiter")
                    has_any_addr = True

                if getattr(cfg, "matcha_address", None):
                    allowed.add("matcha")
                    has_any_addr = True

                # если вообще НИЧЕГО не настроено — старый режим:
                # ищем по символу через DexScreener/Jupiter/Matcha/Pancake
                if not has_any_addr:
                    allowed = {"pancake", "jupiter", "matcha"}
            spreads = {}

            # ------------------------------------------------------
            # -------------- PANCAKE (BSC) -------------------------
            # ------------------------------------------------------
            if "pancake" in allowed:
                bsc_addr = getattr(cfg, "bsc_address", None)

                if not bsc_addr:
                    add_log(f"[{name}] Pancake: нет bsc_address в cfg")
                else:
                    dex_price = get_pancake_price_usdt(bsc_addr)

                    if dex_price is None:
                        add_log(f"[{name}] Pancake: цена не получена")
                    else:
                        d, r = calc_spread(cex_bid, cex_ask, dex_price)
                        spreads["pancake"] = {
                            "direct": d,
                            "reverse": r,
                            "dex_price": dex_price,
                            "cex_bid": cex_bid,
                            "cex_ask": cex_ask,
                        }

            # ------------------------------------------------------
            # -------------- JUPITER -------------------------------
            # ------------------------------------------------------
            ds_pairs = None

            if "jupiter" in allowed:
                j_price = None
                mint = getattr(cfg, "jupiter_mint", None)
                dec = getattr(cfg, "jupiter_decimals", None)

                if mint and isinstance(dec, int):
                    j_price = get_jupiter_price_usdt(mint, dec)

                if j_price is None:
                    if ds_pairs is None:
                        ds_pairs = get_dexscreener_pairs(base, quote)
                    j_price = pick_price_for_dex(ds_pairs, base, quote, "jupiter")

                if j_price:
                    d, r = calc_spread(cex_bid, cex_ask, j_price)
                    spreads["jupiter"] = {
                        "direct": d,
                        "reverse": r,
                        "dex_price": j_price,
                        "cex_bid": cex_bid,
                        "cex_ask": cex_ask,
                    }

            # ------------------------------------------------------
            # -------------- MATCHA --------------------------------
            # ------------------------------------------------------
            if "matcha" in allowed:
                sell_token = getattr(cfg, "matcha_address", None)
                sell_decimals = getattr(cfg, "matcha_decimals", None)

                if sell_token:
                    sell_decimals = sell_decimals or MATCHA_DEFAULT_SELL_DECIMALS

                    m_price = get_matcha_price_usdt(
                        token_address=sell_token,  # matcha_address из cfg
                        token_decimals=sell_decimals,  # matcha_decimals
                        chain_id=MATCHA_CHAIN_ID,
                        usdt_token=MATCHA_USDT,
                        usdt_decimals=MATCHA_USDT_DECIMALS,
                    )

                    if m_price:
                        d, r = calc_spread(cex_bid, cex_ask, m_price)
                        spreads["matcha"] = {
                            "direct": d,
                            "reverse": r,
                            "dex_price": m_price,
                            "cex_bid": cex_bid,
                            "cex_ask": cex_ask,
                        }
                else:
                    add_log(f"[{name}] Matcha: нет matcha_address в cfg")

            # финальный результат ДЛЯ ЭТОЙ ПАРЫ
            return name, {
                "mexc_price": (cex_bid, cex_ask),
                "spreads": spreads,
            }

        except Exception as e:
            add_log(f"Worker: ошибка при обработке {name}: {e}")
            return None

    def run(self):
        while self._running:
            snapshot = {}

            try:
                items = list(self.pairs.items())
                if items:
                    # сколько потоков одновременно использовать
                    max_workers = min(8, len(items))  # можешь поднять до 16 / 32

                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        futures = [
                            executor.submit(self._process_pair, name, cfg)
                            for name, cfg in items
                        ]

                        for fut in futures:
                            try:
                                res = fut.result()
                            except Exception as e:
                                add_log(f"Worker: ошибка в потоке: {e}")
                                continue

                            if not res:
                                continue

                            name, data = res
                            if data is not None:
                                snapshot[name] = data

            except Exception as e:
                add_log(f"Worker: неперехваченное исключение: {e}")

            if snapshot:
                self.data_ready.emit(snapshot)

            # та же логика ожидания по interval, что и была
            steps = max(1, int(float(self.interval) * 10))

            for _ in range(steps):
                if not self._running:
                    break

                # спим 100 мс
                self.msleep(100)

                # если интервал поменяли в настройках — выходим из цикла ожидания
                new_steps = max(1, int(float(self.interval) * 10))
                if new_steps != steps:
                    # интервал изменился (например, с 999 на 1) — переходим к новому циклу
                    break

    def stop(self):
        self._running = False


log("Приложение запущено")
