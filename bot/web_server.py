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
        client = await vpn.get_client(user.vpn_name)
    except Exception as e:
        log.error(f"Failed to fetch client for sub proxy: {e}")
        return web.Response(text="Failed to fetch VPN data", status=500)
        
    # Get traffic stats
    limit_bytes = client.get("traffic_limit_bytes", 0)
    if not limit_bytes or limit_bytes == 0:
        limit_bytes = 175 * 1024**3 # Default visual limit if none
        
    used_bytes = client.get("used_bytes", 0)
    expire_ts = client.get("expire", 0)
    
    headers = {
        "subscription-userinfo": f"upload=0; download={used_bytes}; total={limit_bytes}; expire={expire_ts}",
        "profile-update-interval": "1",
        "profile-title": "Adoria VPN"
    }
    
    sub_links = client.get("sub_links", [])
    
    uuid = client.get("uuid", "00000000-0000-0000-0000-000000000000")
    
    def make_dummy(text: str) -> str:
        safe_text = urllib.parse.quote(text, safe="")
        return f"vless://{uuid}@1.1.1.1:443?encryption=none&security=none&type=tcp#{safe_text}"
        
    lines = []
    lines.append(make_dummy("⚡ Нет рекламы на YouTube"))
    lines.append(make_dummy("⭐ Работает везде"))
    lines.append(make_dummy("🎮 Игровой сервер"))
    lines.extend(sub_links)
    
    content = "\n".join(lines)
    base64_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    
    return web.Response(text=base64_content, headers=headers)

async def start_web_server():
    app = web.Application()
    app.router.add_get('/sub/{user_id}', sub_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    log.info("Subscription proxy started on port 8080")
