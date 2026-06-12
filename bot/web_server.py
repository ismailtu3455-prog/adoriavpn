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
    
    headers = {
        "subscription-userinfo": f"upload=0; download={used_bytes}; total={limit_bytes}; expire={expire_ts}",
        "profile-update-interval": "1",
        "profile-title": "Adoria VPN",
        "profile-web-page-url": "https://t.me/Adoria_funbot",
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

async def start_web_server():
    app = web.Application()
    app.router.add_get('/sub/{user_id}', sub_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    log.info("Subscription proxy started on port 8080")
