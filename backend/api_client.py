# api_client.py
# Клиент для работы с backend API
# Все запросы к внешним API идут через этот клиент на сервер Render

import httpx
import os
from typing import Optional, Dict, Any, List
from decimal import Decimal


class APIClient:
    """
    Клиент для работы с backend API на Render сервере.
    Вместо прямых запросов к MEXC, Jupiter, DexScreener и т.д.,
    клиент отправляет запросы на backend, который проксирует их.
    """
    
    def __init__(self, base_url: str = None, admin_token: str = None):
        """
        Инициализация клиента.
        
        Args:
            base_url: URL backend сервера (по умолчанию из переменной окружения)
            admin_token: Admin токен для защищенных endpoints
        """
        self.base_url = base_url or os.getenv("BACKEND_URL", "https://hydra-tra4.onrender.com")
        self.admin_token = admin_token or os.getenv("ADMIN_TOKEN", "")
        self.client = httpx.Client(timeout=30.0)
    
    def _get_headers(self, admin: bool = False) -> Dict[str, str]:
        """Получить заголовки для запроса"""
        headers = {"Content-Type": "application/json"}
        if admin and self.admin_token:
            headers["X-Admin-Token"] = self.admin_token
        return headers
    
    def _make_request(self, method: str, endpoint: str, admin: bool = False, **kwargs) -> Dict[str, Any]:
        """Сделать запрос к backend"""
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers(admin=admin)
        
        try:
            if method.upper() == "GET":
                resp = self.client.get(url, headers=headers, **kwargs)
            elif method.upper() == "POST":
                resp = self.client.post(url, headers=headers, **kwargs)
            elif method.upper() == "DELETE":
                resp = self.client.delete(url, headers=headers, **kwargs)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            raise Exception(f"API Error: {e}")
    
    # ==== HEALTH CHECK ====
    
    def health_check(self) -> Dict[str, Any]:
        """Проверить статус backend"""
        return self._make_request("GET", "/health")
    
    def db_ping(self) -> Dict[str, Any]:
        """Проверить соединение с БД"""
        return self._make_request("GET", "/db_ping")
    
    def cg_ping(self) -> Dict[str, Any]:
        """Проверить CoinGecko API"""
        return self._make_request("GET", "/cg_ping")
    
    # ==== PRICE ENDPOINTS ====
    
    def get_price_dex(self, address: str) -> Dict[str, Any]:
        """Получить цену через DexScreener"""
        return self._make_request("GET", "/price/dex_by_address", params={"address": address})
    
    def get_price_pancake(self, address: str) -> Dict[str, Any]:
        """Получить цену на PancakeSwap"""
        return self._make_request("GET", "/price/pancake", params={"address": address})
    
    def get_price_mexc(self, symbol: str) -> Dict[str, Any]:
        """Получить цену на MEXC"""
        return self._make_request("GET", "/price/mexc", params={"symbol": symbol})
    
    def get_price_matcha(
        self,
        address: str,
        token_decimals: int = 18,
        chain_id: int = 8453,
        usdt_token: str = "0xfde4c96c8593536e31f229ea8f37b2ada2699bb2",
        usdt_decimals: int = 6,
    ) -> Dict[str, Any]:
        """Получить цену через Matcha (0x)"""
        return self._make_request(
            "GET",
            "/price/matcha_by_address",
            params={
                "address": address,
                "token_decimals": token_decimals,
                "chain_id": chain_id,
                "usdt_token": usdt_token,
                "usdt_decimals": usdt_decimals,
            }
        )
    
    def get_price_jupiter(self, mint: str, decimals: int) -> Dict[str, Any]:
        """Получить цену через Jupiter"""
        return self._make_request(
            "GET",
            "/price/jupiter",
            params={"mint": mint, "decimals": decimals}
        )
    
    # ==== SEARCH ENDPOINTS ====
    
    def search_dexscreener(self, query: str) -> Dict[str, Any]:
        """Поиск токенов в DexScreener"""
        return self._make_request("GET", "/search/dexscreener", params={"q": query})
    
    def search_jupiter(self, query: str) -> Dict[str, Any]:
        """Поиск токенов в Jupiter"""
        return self._make_request("GET", "/search/jupiter", params={"q": query})
    
    def search_matcha(self, query: str) -> Dict[str, Any]:
        """Поиск токенов в Matcha"""
        return self._make_request("GET", "/search/matcha", params={"q": query})
    
    # ==== FUTURES ====
    
    def get_mexc_futures_ticker(self, symbol: str) -> Dict[str, Any]:
        """Получить информацию о фьючерсе на MEXC"""
        return self._make_request("GET", "/futures/mexc_ticker", params={"symbol": symbol})
    
    # ==== TOKENS ====
    
    def get_pancake_tokens_list(self) -> Dict[str, Any]:
        """Получить список токенов с PancakeSwap"""
        return self._make_request("GET", "/tokens/pancake_list")
    
    def get_coingecko_coins_list(self) -> Dict[str, Any]:
        """Получить список монет с CoinGecko"""
        return self._make_request("GET", "/coingecko/coins_list")
    
    def get_coingecko_markets(self, ids: str, vs_currency: str = "usd") -> Dict[str, Any]:
        """Получить информацию о монетах с CoinGecko"""
        return self._make_request(
            "GET",
            "/coingecko/markets",
            params={"ids": ids, "vs_currency": vs_currency}
        )
    
    # ==== TOKEN MANAGEMENT ====
    
    def add_token(self, chain: str, address: str, symbol: Optional[str] = None, name: Optional[str] = None) -> Dict[str, Any]:
        """Добавить токен"""
        return self._make_request(
            "POST",
            "/tokens",
            json={"chain": chain, "address": address, "symbol": symbol, "name": name}
        )
    
    def list_tokens(self, chain: Optional[str] = None) -> List[Dict[str, Any]]:
        """Получить список токенов"""
        params = {}
        if chain:
            params["chain"] = chain
        return self._make_request("GET", "/tokens", params=params)
    
    def admin_add_token(self, chain: str, address: str, symbol: Optional[str] = None, name: Optional[str] = None) -> Dict[str, Any]:
        """Добавить токен (admin)"""
        return self._make_request(
            "POST",
            "/admin/tokens",
            admin=True,
            json={"chain": chain, "address": address, "symbol": symbol, "name": name}
        )
    
    def admin_list_tokens(self, skip: int = 0, limit: int = 100, include_deleted: bool = False) -> List[Dict[str, Any]]:
        """Получить список токенов (admin)"""
        return self._make_request(
            "GET",
            "/admin/tokens",
            admin=True,
            params={"skip": skip, "limit": limit, "include_deleted": include_deleted}
        )
    
    def admin_delete_token(self, token_id: int) -> Dict[str, Any]:
        """Удалить токен (admin)"""
        return self._make_request("DELETE", f"/admin/tokens/{token_id}", admin=True)
    
    def close(self):
        """Закрыть соединение"""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Глобальный клиент (для удобства)
_global_client: Optional[APIClient] = None


def get_client(base_url: str = None, admin_token: str = None) -> APIClient:
    """Получить или создать глобальный клиент"""
    global _global_client
    if _global_client is None:
        _global_client = APIClient(base_url=base_url, admin_token=admin_token)
    return _global_client


def close_client():
    """Закрыть глобальный клиент"""
    global _global_client
    if _global_client:
        _global_client.close()
        _global_client = None
