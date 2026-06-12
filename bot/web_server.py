import base64
import urllib.parse
import logging
from aiohttp import web
from .database import crud
from .services import vpn

log = logging.getLogger(__name__)

async def sub_handler(request: web.Request) -> web.Response:
    user_id_str = request.match_info.get('user_id', '')
    if not user_id_str.isdigit():
        return web.Response(text="Invalid user_id", status=400)
        
    user_id = int(user_id_str)
    user = await crud.get_user(user_id)
    if not user or not user.vpn_name:
        return web.Response(text="User or VPN not found", status=404)
        
    try:
        data = await vpn.get_client(user.vpn_name)
        client = data.get("client") or data
    except Exception as e:
        log.error(f"Failed to fetch client for sub proxy: {e}")
        return web.Response(text="Failed to fetch VPN data", status=500)
        
    # Get traffic stats
    limit_bytes = client.get("traffic_limit_bytes", 0)
        
    used_bytes = client.get("used_bytes", 0)
    expire_ts = client.get("expire", 0)
    
    host = request.headers.get("Host", "127.0.0.1:8080")
    info_url = f"http://{host}/info/{user_id}"

    userinfo_parts = [f"upload=0", f"download={used_bytes}"]
    if limit_bytes > 0:
        userinfo_parts.append(f"total={limit_bytes}")
    if expire_ts > 0:
        userinfo_parts.append(f"expire={expire_ts}")

    headers = {
        "subscription-userinfo": "; ".join(userinfo_parts),
        "profile-update-interval": "1",
        "profile-title": "Adoria VPN",
        "profile-web-page-url": info_url,
        "support-url": "https://t.me/Adoria_funbot"
    }
    
    sub_links = []
    original_sub = client.get("subscription_url")
    if original_sub:
        import aiohttp
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(original_sub) as r:
                    text = await r.text()
                    links_in_text = [l.strip() for l in text.split('\n') if l.strip().startswith('vless://')]
                    if links_in_text:
                        sub_links = links_in_text
                    else:
                        decoded = base64.b64decode(text).decode('utf-8')
                        sub_links = [l.strip() for l in decoded.split('\n') if l.strip().startswith('vless://')]
        except Exception as e:
            log.error(f"Failed to fetch original sub: {e}")
            
    if not sub_links:
        links = client.get("links", {})
        sub_links = [l for l in links.values() if l and l.startswith('vless://')]
    
    # Красивые названия серверов
    final_links = []
    
    for sl in sub_links:
        if "#" in sl:
            name_part = urllib.parse.unquote(sl.split("#")[1])
            name_part = name_part.replace("193.23.199.80", "🇩🇪 Германия")
            name_part = name_part.replace("FI-Финляндия", "🇫🇮 Финляндия")
            sl = sl.split("#")[0] + "#" + urllib.parse.quote(name_part)
        final_links.append(sl)
    
    content = "\n".join(final_links)
    base64_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    
    return web.Response(text=base64_content, headers=headers)

async def handle_info(request: web.Request) -> web.Response:
    user_id_str = request.match_info.get('user_id')
    try:
        user_id = int(user_id_str)
    except ValueError:
        return web.Response(text="Invalid user ID", status=400)
        
    user = await crud.get_user(user_id)
    if not user or not user.vpn_name:
        return web.Response(text="User or VPN not found", status=404)
        
    try:
        data = await vpn.get_client(user.vpn_name)
        client = data.get("client") or data
    except Exception as e:
        log.error(f"Failed to fetch client for info: {e}")
        return web.Response(text="Failed to fetch VPN data", status=500)
        
    uuid = client.get("uuid", "Неизвестно")
    used_bytes = client.get("used_bytes", 0)
    limit_bytes = client.get("traffic_limit_bytes", 0)
    
    used_gb = round(used_bytes / (1024**3), 2)
    limit_text = "∞" if not limit_bytes or limit_bytes == 0 else f"{round(limit_bytes / (1024**3), 2)} GB"
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta charset="utf-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: transparent;
            color: #333;
            text-align: center;
            padding: 20px;
            margin: 0;
            line-height: 1.5;
        }}
        @media (prefers-color-scheme: dark) {{
            body {{ color: #eee; }}
        }}
        .title {{ font-size: 15px; margin-bottom: 20px; font-weight: bold; }}
        .list {{ font-size: 15px; margin-bottom: 25px; display: inline-block; text-align: left; }}
        .usage {{ font-size: 15px; opacity: 0.9; margin-bottom: 20px; }}
        .footer {{ font-size: 12px; opacity: 0.6; }}
    </style>
</head>
<body>
    <div class="title">Подписка: {uuid}</div>
    
    <div class="list">
        🚀 - Надежный VLESS VPN<br>
        🛡️ - Обходит блокировки<br>
        💨 - Не режет скорость
    </div>
    
    <div class="usage">
        Использовано:<br>
        {used_gb} GB / {limit_text}
    </div>
    
    <div class="footer">
        Трафик расходуется только на активных серверах.
    </div>
</body>
</html>"""
    
    return web.Response(text=html, content_type='text/html', charset='utf-8')

async def start_web_server():
    app = web.Application()
    app.router.add_get('/sub/{user_id}', sub_handler)
    app.router.add_get('/info/{user_id}', handle_info)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    log.info("Subscription proxy started on port 8080")
