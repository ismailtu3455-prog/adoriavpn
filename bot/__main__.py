import asyncio
import logging
import secrets
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from .config import settings
from .database import crud
from .database.crud import init_db, get_active_invoices, update_invoice_status, get_user, set_vpn_name, get_setting
from .middlewares.db_user import DbUserMiddleware
from .handlers import user, payments, admin
from .services import vpn, cryptopay, tome
from .services.delivery import deliver_vpn
from .config import db_settings
from .web_server import start_web_server

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Настройка прокси, если он указан в .env
session = AiohttpSession(proxy=settings.proxy_url) if settings.proxy_url else None
bot = Bot(token=settings.bot_token, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

async def background_payment_checker():
    while True:
        try:
            invoices = await get_active_invoices()
            for inv in invoices:
                status = "active"
                if inv.gateway == "cryptopay":
                    status = await cryptopay.get_crypto_invoice_status(inv.invoice_id)
                elif inv.gateway == "tome":
                    status = await tome.get_tome_invoice_status(inv.invoice_id)
                
                if status in ("paid", "completed", "succeeded"):
                    await update_invoice_status(inv.invoice_id, "paid")
                    
                    if inv.is_gift:
                        import secrets
                        from .keyboards import inline
                        code = f"GIFT-{secrets.token_hex(4).upper()}"
                        await crud.create_gift_card(code, inv.days)
                        bot_info = await bot.me()
                        buyer = await get_user(inv.user_id)
                        buyer_name = buyer.first_name if buyer and buyer.first_name else "Кто-то"
                        try:
                            await bot.send_message(
                                inv.user_id,
                                "✅ Успешно оплачено!\nВаш подарок готов.",
                                reply_markup=inline.share_gift_kb(code, inv.days, bot_info.username, buyer_name)
                            )
                        except Exception:
                            pass
                    else:
                        await deliver_vpn(bot, inv.user_id, inv.days, is_purchase=True)
                        plan = await crud.get_plan(inv.plan)
                        if plan:
                            await crud.process_referral_bonus(bot, inv.user_id, plan.price)

                    channel_id = db_settings.get("payment_channel_id")
                    if channel_id:
                        try:
                            await bot.send_message(
                                chat_id=int(channel_id),
                                text=f"💰 <b>Новая оплата!</b>\nПользователь: <a href='tg://user?id={inv.user_id}'>{inv.user_id}</a>\nСумма: {inv.amount} {inv.asset}\nТариф: {inv.days} дней"
                            )
                        except Exception as e:
                            log.error(f"Failed to send to channel: {e}")
                elif status in ("expired", "canceled", "inactive"):
                    await update_invoice_status(inv.invoice_id, "canceled")
        except Exception as e:
            log.error(f"Payment checker error: {e}")
            
        await asyncio.sleep(15)

async def background_expiry_checker():
    from .database.crud import get_all_users, update_user_reminders
    from .services import vpn
    from .keyboards import inline
    import time
    
    milestones = [72, 24, 12, 3, 1] # hours
    
    while True:
        try:
            users = await get_all_users()
            now = int(time.time())
            
            for u in users:
                if not u.vpn_name:
                    continue
                    
                await asyncio.sleep(0.5) # Anti-spam API delay
                
                try:
                    client = await vpn.get_client(u.vpn_name)
                    expire = client.get("expire", 0)
                    
                    if not expire or expire == 0:
                        continue
                        
                    remaining_hours = (expire - now) / 3600.0
                    
                    if remaining_hours <= 0:
                        continue
                        
                    if remaining_hours > max(milestones):
                        if u.last_reminded_milestone != 0:
                            await update_user_reminders(u.user_id, expire, 0)
                        continue
                        
                    target_milestone = None
                    for ms in sorted(milestones):
                        if remaining_hours <= ms:
                            target_milestone = ms
                            break
                            
                    if target_milestone and target_milestone != u.last_reminded_milestone:
                        # Convert milestone to human readable text
                        ms_text = f"{target_milestone} часа(ов)"
                        if target_milestone == 72: ms_text = "3 дня"
                        elif target_milestone == 24: ms_text = "24 часа"
                        
                        text = f"⏳ <b>Внимание!</b>\nВаша подписка на VPN заканчивается менее чем через {ms_text}.\nНе забудьте продлить её, чтобы оставаться на связи!"
                        try:
                            await bot.send_message(u.user_id, text, reply_markup=inline.back_to_buy_kb())
                            await update_user_reminders(u.user_id, expire, target_milestone)
                        except Exception:
                            pass
                except Exception as e:
                    pass
        except Exception as e:
            log.error(f"Expiry checker error: {e}")
            
        await asyncio.sleep(900) # Run every 15 minutes

async def load_settings():
    for key in db_settings.keys():
        val = await get_setting(key)
        if val is not None:
            db_settings[key] = val

async def main():
    await init_db()
    await load_settings()
    
    from aiogram.types import BotCommand
    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню")
    ])
    
    dp = Dispatcher()
    dp.message.middleware(DbUserMiddleware())
    dp.callback_query.middleware(DbUserMiddleware())
    
    dp.include_router(user.router)
    dp.include_router(payments.router)
    dp.include_router(admin.router)
    
    asyncio.create_task(background_payment_checker())
    asyncio.create_task(background_expiry_checker())
    asyncio.create_task(start_web_server())
    
    log.info("Bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
