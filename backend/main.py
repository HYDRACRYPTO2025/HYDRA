from fastapi import FastAPI
import httpx

app = FastAPI()


@app.get("/")
def read_root():
    return {"status": "ok"}


@app.get("/cg_ping")
def coingecko_ping():
    """
    Тест: сервер на Render делает запрос к CoinGecko
    и возвращает их ответ.
    """
    r = httpx.get("https://api.coingecko.com/api/v3/ping", timeout=10.0)
    return {
        "status": "ok",
        "coingecko_raw": r.json(),
    }
