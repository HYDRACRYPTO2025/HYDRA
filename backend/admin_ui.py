"""
Веб-интерфейс админ-панели.
Простой HTML интерфейс для управления прокси и токенами.
"""

from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from .db import get_db
from .models import Proxy, AccessToken, AdminUser
from .auth import hash_password, verify_password, generate_token
from .logic import log

router = APIRouter(prefix="/admin", tags=["admin_ui"])


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HYDRA Admin Panel</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header {
            background: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        }
        
        .header h1 {
            color: #333;
            font-size: 28px;
            margin-bottom: 10px;
        }
        
        .header p {
            color: #666;
            font-size: 14px;
        }
        
        .card {
            background: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        }
        
        .card h2 {
            color: #333;
            font-size: 20px;
            margin-bottom: 20px;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }
        
        .form-group {
            margin-bottom: 15px;
        }
        
        label {
            display: block;
            margin-bottom: 5px;
            color: #333;
            font-weight: 500;
        }
        
        input, textarea {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
            font-family: inherit;
        }
        
        input:focus, textarea:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 5px rgba(102, 126, 234, 0.3);
        }
        
        button {
            background: #667eea;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.3s;
        }
        
        button:hover {
            background: #5568d3;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3);
        }
        
        .success {
            background: #51cf66;
            padding: 15px;
            border-radius: 5px;
            color: white;
            margin-bottom: 20px;
        }
        
        .error {
            background: #ff6b6b;
            padding: 15px;
            border-radius: 5px;
            color: white;
            margin-bottom: 20px;
        }
        
        .info {
            background: #4dabf7;
            padding: 15px;
            border-radius: 5px;
            color: white;
            margin-bottom: 20px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        
        th {
            background: #f5f5f5;
            font-weight: 600;
            color: #333;
        }
        
        tr:hover {
            background: #f9f9f9;
        }
        
        .btn-small {
            padding: 5px 10px;
            font-size: 12px;
            margin: 0 2px;
        }
        
        .btn-danger {
            background: #ff6b6b;
        }
        
        .btn-danger:hover {
            background: #ff5252;
        }
        
        .code {
            background: #f5f5f5;
            padding: 10px;
            border-radius: 5px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            word-break: break-all;
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔐 HYDRA Admin Panel</h1>
            <p>Управление прокси и токенами доступа</p>
        </div>
        
        <div class="card">
            <h2>📝 Создать Access Token</h2>
            <form method="post" action="/api/admin/create-token">
                <div class="form-group">
                    <label for="token_name">Имя токена:</label>
                    <input type="text" id="token_name" name="token_name" placeholder="Например: Desktop App" required>
                </div>
                <button type="submit">Создать токен</button>
            </form>
        </div>
        
        <div class="card">
            <h2>🔑 Активные токены</h2>
            <p style="color: #666; font-size: 14px; margin-bottom: 15px;">
                Используйте эти токены для подключения desktop приложения к серверу.
            </p>
            <div id="tokens-list">
                <p style="color: #999;">Загрузка...</p>
            </div>
        </div>
        
        <div class="card">
            <h2>🌐 Добавить прокси</h2>
            <form method="post" action="/api/admin/add-proxy">
                <div class="form-group">
                    <label for="proxy_url">URL прокси:</label>
                    <input type="text" id="proxy_url" name="proxy_url" placeholder="http://proxy.example.com:8080" required>
                </div>
                <div class="form-group">
                    <label for="proxy_type">Тип:</label>
                    <input type="text" id="proxy_type" name="proxy_type" placeholder="http, https, socks5" value="http">
                </div>
                <button type="submit">Добавить прокси</button>
            </form>
        </div>
        
        <div class="card">
            <h2>📋 Список прокси</h2>
            <div id="proxies-list">
                <p style="color: #999;">Загрузка...</p>
            </div>
        </div>
        
        <div class="card">
            <h2>ℹ️ Информация</h2>
            <div class="info">
                <strong>Как использовать:</strong><br>
                1. Создайте access token<br>
                2. Скопируйте токен<br>
                3. Откройте desktop приложение<br>
                4. Введите server URL и токен в настройках
            </div>
        </div>
    </div>
    
    <script>
        // Загрузить список токенов
        async function loadTokens() {
            try {
                const response = await fetch('/api/admin/tokens');
                const data = await response.json();
                const tokensList = document.getElementById('tokens-list');
                
                if (data.tokens && data.tokens.length > 0) {
                    let html = '<table><tr><th>Имя</th><th>Токен</th><th>Создан</th><th>Действие</th></tr>';
                    data.tokens.forEach(token => {
                        html += `
                            <tr>
                                <td>${token.name}</td>
                                <td><code class="code">${token.token}</code></td>
                                <td>${new Date(token.created_at).toLocaleString()}</td>
                                <td>
                                    <button class="btn-small btn-danger" onclick="deleteToken('${token.id}')">Удалить</button>
                                </td>
                            </tr>
                        `;
                    });
                    html += '</table>';
                    tokensList.innerHTML = html;
                } else {
                    tokensList.innerHTML = '<p style="color: #999;">Нет активных токенов</p>';
                }
            } catch (error) {
                console.error('Error loading tokens:', error);
                document.getElementById('tokens-list').innerHTML = '<p style="color: #ff6b6b;">Ошибка загрузки токенов</p>';
            }
        }
        
        // Загрузить список прокси
        async function loadProxies() {
            try {
                const response = await fetch('/api/admin/proxies');
                const data = await response.json();
                const proxiesList = document.getElementById('proxies-list');
                
                if (data.proxies && data.proxies.length > 0) {
                    let html = '<table><tr><th>URL</th><th>Тип</th><th>Статус</th><th>Действие</th></tr>';
                    data.proxies.forEach(proxy => {
                        html += `
                            <tr>
                                <td>${proxy.url}</td>
                                <td>${proxy.proxy_type}</td>
                                <td><span style="color: #51cf66;">✓ Активен</span></td>
                                <td>
                                    <button class="btn-small btn-danger" onclick="deleteProxy('${proxy.id}')">Удалить</button>
                                </td>
                            </tr>
                        `;
                    });
                    html += '</table>';
                    proxiesList.innerHTML = html;
                } else {
                    proxiesList.innerHTML = '<p style="color: #999;">Нет добавленных прокси</p>';
                }
            } catch (error) {
                console.error('Error loading proxies:', error);
                document.getElementById('proxies-list').innerHTML = '<p style="color: #ff6b6b;">Ошибка загрузки прокси</p>';
            }
        }
        
        async function deleteToken(tokenId) {
            if (confirm('Вы уверены?')) {
                try {
                    await fetch(`/api/admin/token/${tokenId}`, { method: 'DELETE' });
                    loadTokens();
                } catch (error) {
                    console.error('Error deleting token:', error);
                }
            }
        }
        
        async function deleteProxy(proxyId) {
            if (confirm('Вы уверены?')) {
                try {
                    await fetch(`/api/admin/proxy/${proxyId}`, { method: 'DELETE' });
                    loadProxies();
                } catch (error) {
                    console.error('Error deleting proxy:', error);
                }
            }
        }
        
        // Загрузить данные при загрузке страницы
        loadTokens();
        loadProxies();
        
        // Обновлять каждые 5 секунд
        setInterval(() => {
            loadTokens();
            loadProxies();
        }, 5000);
    </script>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse)
def admin_panel(request: Request):
    """
    Главная страница админ-панели.
    Возвращает HTML интерфейс.
    """
    return HTML_TEMPLATE


@router.post("/add-proxy")
async def add_proxy_form(
    proxy_url: str = Form(...),
    proxy_type: str = Form("http"),
    db: Session = Depends(get_db)
):
    """
    Обработчик формы для добавления прокси.
    """
    try:
        # Проверяем, что прокси с таким URL еще не существует
        existing = db.query(Proxy).filter(Proxy.url == proxy_url).first()
        if existing:
            return RedirectResponse(url="/admin?error=Proxy already exists", status_code=303)
        
        new_proxy = Proxy(
            url=proxy_url,
            protocol=proxy_type,
            is_active=True
        )
        
        db.add(new_proxy)
        db.commit()
        
        log(f"Created new proxy: {proxy_url}")
        return RedirectResponse(url="/admin?success=Proxy added", status_code=303)
    
    except Exception as e:
        log(f"Error adding proxy: {e}")
        return RedirectResponse(url="/admin?error=Error adding proxy", status_code=303)


@router.post("/create-token")
async def create_token_form(
    token_name: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Обработчик формы для создания токена доступа.
    """
    try:
        # Генерируем уникальный токен
        token_value = generate_token()
        
        new_token = AccessToken(
            token=token_value,
            name=token_name,
            is_active=True
        )
        
        db.add(new_token)
        db.commit()
        db.refresh(new_token)
        
        log(f"Created new access token: {token_name}")
        
        # Перенаправляем обратно с токеном в URL (для отображения)
        return RedirectResponse(url=f"/admin?token={token_value}&name={token_name}", status_code=303)
    
    except Exception as e:
        log(f"Error creating token: {e}")
        return RedirectResponse(url="/admin?error=Error creating token", status_code=303)


@router.get("/api/admin/tokens")
async def get_tokens_api(db: Session = Depends(get_db)):
    """
    API для получения списка токенов (для JavaScript).
    """
    tokens = db.query(AccessToken).filter(AccessToken.is_active == True).all()
    return {
        "tokens": [
            {
                "id": t.id,
                "name": t.name,
                "token": t.token,
                "created_at": t.created_at.isoformat() if t.created_at else None
            }
            for t in tokens
        ]
    }


@router.get("/api/admin/proxies")
async def get_proxies_api(db: Session = Depends(get_db)):
    """
    API для получения списка прокси (для JavaScript).
    """
    proxies = db.query(Proxy).filter(Proxy.is_active == True).all()
    return {
        "proxies": [
            {
                "id": p.id,
                "url": p.url,
                "proxy_type": p.protocol,
                "created_at": p.created_at.isoformat() if p.created_at else None
            }
            for p in proxies
        ]
    }


@router.delete("/api/admin/token/{token_id}")
async def delete_token_api(token_id: int, db: Session = Depends(get_db)):
    """
    API для удаления токена (для JavaScript).
    """
    token = db.query(AccessToken).filter(AccessToken.id == token_id).first()
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    
    db.delete(token)
    db.commit()
    
    log(f"Deleted access token {token_id}")
    return {"message": "Token deleted"}


@router.delete("/api/admin/proxy/{proxy_id}")
async def delete_proxy_api(proxy_id: int, db: Session = Depends(get_db)):
    """
    API для удаления прокси (для JavaScript).
    """
    proxy = db.query(Proxy).filter(Proxy.id == proxy_id).first()
    if not proxy:
        raise HTTPException(status_code=404, detail="Proxy not found")
    
    db.delete(proxy)
    db.commit()
    
    log(f"Deleted proxy {proxy_id}")
    return {"message": "Proxy deleted"}
