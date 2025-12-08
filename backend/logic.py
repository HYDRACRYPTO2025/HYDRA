from dataclasses import dataclass
from typing import Optional, Dict

from datetime import datetime

import cloudscraper


def log(msg: str) -> None:
    """Простой лог — увидишь его в LOGS на Render."""
    ts = datetime.utcnow().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# === HTTP клиент с cloudscraper, как в core.py ===

http_client = cloudscraper.create_scraper(
    browser={
        "browser": "chrome",
        "platform": "windows",
        "mobile": False,
    }
)

# === Dataclass для конфигурации L/M ===


@dataclass
class PairConfigLM:
    base: str
    cg_id: Optional[str] = None


# === Работа с CoinGecko (кэш списка монет) ===

_CG_COINS_LIST = []
_CG_LIST_LOADED = False
_CG_SYMBOL_INDEX: Dict[str, str] = {}


def _ensure_cg_coins_list() -> None:
    """Один раз за запуск грузим полный список CoinGecko."""
    global _CG_COINS_LIST, _CG_LIST_LOADED

    if _CG_LIST_LOADED:
        return

    try:
        resp = http_client.get(
            "https://api.coingecko.com/api/v3/coins/list",
            timeout=20.0,
        )
        if resp.status_code != 200:
            log(f"CoinGecko list: HTTP {resp.status_code}: {str(resp.text)[:150]}")
            _CG_COINS_LIST = []
            _CG_LIST_LOADED = True
            return

        data = resp.json()
        if isinstance(data, list):
            _CG_COINS_LIST = data
        else:
            _CG_COINS_LIST = []
        _CG_LIST_LOADED = True
        log(f"CoinGecko list: loaded {len(_CG_COINS_LIST)} coins")
    except Exception as e:
        log(f"CoinGecko list: error: {e}")
        _CG_COINS_LIST = []
        _CG_LIST_LOADED = True


def _pick_coingecko_id_for_symbol(symbol: str) -> Optional[str]:
    """Подбор id по символу — логика похожа на твою в core.py."""
    global _CG_SYMBOL_INDEX

    symbol = (symbol or "").strip().upper()
    if not symbol:
        return None

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

            if cid_l == sym_lower:
                score += 100.0

            if name_l == sym_lower:
                score += 50.0

            if name_l.startswith(sym_lower):
                score += 25.0

            if "-" not in cid and " " not in cid:
                score += 10.0

            if any(w in cid_l for w in bad_words) or any(
                w in name_l for w in bad_words
            ):
                score -= 30.0

            score -= len(cid) * 0.01

            if best_score is None or score > best_score:
                best_score = score
                best_id = cid
        except Exception:
            continue

    if best_id:
        _CG_SYMBOL_INDEX[symbol] = best_id
        log(f"CoinGecko: {symbol} -> id={best_id}")
    else:
        log(f"CoinGecko: no id for symbol {symbol}")

    return best_id


def fetch_L_M_for_pair(pair_cfg: PairConfigLM) -> Optional[Dict[str, float]]:
    """
    Аналог твоей функции fetch_L_M_for_pair:
    - берём цену и amount24 с MEXC futures (BASE_USDT),
    - берём капитализацию M с CoinGecko.

    Возвращаем dict:
      {
        "price_mexc": float | None,
        "L": float | None,
        "M": float | None,
        "cg_id": str | None
      }
    """
    base = (getattr(pair_cfg, "base", "") or "").upper().strip()
    if not base:
        return None

    price_mexc: Optional[float] = None
    L: Optional[float] = None
    M: Optional[float] = None

    # ------ MEXC futures: тикер BASE_USDT ------
    symbol_fut = f"{base}_USDT"
    try:
        r = http_client.get(
            "https://contract.mexc.com/api/v1/contract/ticker",
            params={"symbol": symbol_fut},
            timeout=10.0,
        )
        if r.status_code != 200:
            log(
                f"MEXC L/M futures: HTTP {r.status_code} for {symbol_fut}: "
                f"{str(r.text)[:200]}"
            )
        else:
            data = r.json()
            if data.get("success"):
                t = data.get("data") or {}
                try:
                    price_mexc = float(t.get("lastPrice") or 0.0)
                except Exception:
                    price_mexc = None
                try:
                    L = float(t.get("amount24") or 0.0)
                except Exception:
                    L = None
            else:
                log(
                    f"MEXC L/M futures: code={data.get('code')} "
                    f"msg={data.get('message')} for {symbol_fut}"
                )
    except Exception as e:
        log(f"MEXC L/M futures: error for {symbol_fut}: {e}")

    # ------ CoinGecko: капитализация M ------
    cg_id = getattr(pair_cfg, "cg_id", None)
    if not cg_id:
        cg_id = _pick_coingecko_id_for_symbol(base) or base.lower()

    if cg_id:
        try:
            r = http_client.get(
                "https://api.coingecko.com/api/v3/coins/markets",
                params={"vs_currency": "usd", "ids": cg_id},
                timeout=10.0,
            )
            if r.status_code != 200:
                log(
                    f"CoinGecko M: HTTP {r.status_code} for {cg_id}: "
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
            log(f"CoinGecko M: error for {cg_id}: {e}")

    if price_mexc is None and L is None and M is None:
        return None

    return {
        "price_mexc": price_mexc,
        "L": L,
        "M": M,
        "cg_id": cg_id,
    }
