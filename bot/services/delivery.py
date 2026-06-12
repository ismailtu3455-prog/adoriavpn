import secrets
import logging
from aiogram import Bot
from .vpn import extend_client, create_client, get_client
from ..database.crud import get_user, set_vpn_name

log = logging.getLogger(__name__)

async def deliver_vpn(bot: Bot, user_id: int, days: int, is_purchase: bool = False) -> bool:
    u = await get_user(user_id)
    if not u:
        return False
        
    name = u.vpn_name
    try:
        if name:
            await extend_client(name, days)
        else:
            name = f"tg{user_id}{secrets.token_hex(2)}"
            from ..config import db_settings
            limit = int(db_settings.get("default_limit_gb", 0))
            await create_client(name, days, limit_gb=limit)
            await set_vpn_name(user_id, name)
            
        data = await get_client(name)
        client_data = data.get("client") or data
        sub = client_data.get("subscription_url", "-")
        links = client_data.get("links", {})
        ws_link = links.get("ws", "")
        reality_link = links.get("reality", "")
        
        import urllib.parse
        import aiohttp
        import base64
        
        links_text = ""
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(sub) as r:
                    text = await r.text()
                    decoded = base64.b64decode(text).decode('utf-8')
                    sub_links = [l.strip() for l in decoded.split('\n') if l.strip().startswith('vless://')]
                    
                    if sub_links:
                        for idx, sl in enumerate(sub_links):
                            name_part = "VPN"
                            if "#" in sl:
                                name_part = urllib.parse.unquote(sl.split("#")[1])
                                # Красивые названия
                                name_part = name_part.replace("193.23.199.80", "🇩🇪 Германия")
                                name_part = name_part.replace("FI-Финляндия", "🇫🇮 Финляндия")
                                sl = sl.split("#")[0] + "#" + urllib.parse.quote(name_part)
                            links_text += f"<b>Сервер {idx+1} ({name_part}):</b>\n<blockquote expandable><code>{sl}</code></blockquote>\n"
        except Exception:
            pass
            
        if not links_text:
            if ws_link:
                ws_link = ws_link.split("#")[0] + "#" + urllib.parse.quote("🛡 VPN (WS)")
                links_text += f"<b>VLESS WS+TLS:</b>\n<blockquote expandable><code>{ws_link}</code></blockquote>\n"
            if reality_link:
                reality_link = reality_link.split("#")[0] + "#" + urllib.parse.quote("🛡 VPN (Reality)")
                links_text += f"<b>VLESS Reality:</b>\n<blockquote expandable><code>{reality_link}</code></blockquote>"
        
        import datetime
        expires_at = client_data.get("expires_at", 0)
        expire_str = datetime.datetime.utcfromtimestamp(expires_at).strftime('%d.%m.%Y %H:%M UTC') if expires_at else "Неизвестно"
        left_days = client_data.get("left_days", "?")
        
        msg = (
            f"<b>Ключ активирован</b>\n\n"
            f"Имя: <code>{name}</code>\n"
            f"Осталось дней: <b>{left_days}</b>\n"
            f"Истекает: {expire_str}\n\n"
            f"<b>Подписка:</b>(скопировать)\n"
            f"<blockquote><code>{sub}</code></blockquote>\n"
            f"<b>Подписка:</b>(перейти на сайт)\n"
            f"<blockquote>{sub}/page</blockquote>\n\n"
            f"{links_text}"
        )
        await bot.send_message(user_id, msg)
        
        if is_purchase and u.referrer_id:
            from ..database.crud import get_paid_invoices_count
            count = await get_paid_invoices_count(user_id)
            if count == 1:
                from ..config import db_settings
                reward_pay = int(db_settings.get("ref_reward_pay", 10))
                if reward_pay > 0:
                    await deliver_vpn(bot, u.referrer_id, reward_pay, is_purchase=False)
                    try:
                        await bot.send_message(u.referrer_id, f"🎁 Ваш реферал совершил свою первую покупку! Вы получили {reward_pay} дней VPN в подарок.")
                    except Exception:
                        pass
        return True
    except Exception as e:
        log.error(f"Deliver VPN error for {user_id}: {e}")
        try:
            await bot.send_message(user_id, f"⚠️ Произошла ошибка при выдаче VPN: {e}")
        except Exception:
            pass
        return False
