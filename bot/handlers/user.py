from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from ..states import UserState
from ..texts import texts
from ..keyboards import inline
from ..config import settings
from ..database import crud
from ..services import vpn

router = Router()

async def is_admin(user_id: int) -> bool:
    if user_id in settings.get_admin_ids:
        return True
    admins = await crud.get_admins()
    return user_id in admins

@router.message(CommandStart())
async def cmd_start(m: Message, command: CommandObject):
    if command.args and command.args.startswith("GIFT-"):
        code = command.args
        days = await crud.use_gift_card(code)
        is_adm = await is_admin(m.from_user.id)
        if days:
            from ..services.delivery import deliver_vpn
            await deliver_vpn(m.bot, m.from_user.id, days, is_purchase=False)
            await m.answer(f"🎁 <b>Подарочный ключ активирован!</b>\nВам начислено {days} дней VPN.", reply_markup=inline.main_menu(is_adm))
        else:
            await m.answer("❌ Подарочный ключ не найден или уже использован.", reply_markup=inline.main_menu(is_adm))
        return

    ref_id = None
    ref_type = None
    if command.args:
        if command.args.startswith("B") and command.args[1:].isdigit():
            ref_id = int(command.args[1:])
            ref_type = "bonus"
        elif command.args.startswith("P") and command.args[1:].isdigit():
            ref_id = int(command.args[1:])
            ref_type = "partner"
        elif command.args.isdigit(): # Legacy
            ref_id = int(command.args)
            ref_type = "bonus"
            
        if ref_id == m.from_user.id:
            ref_id = None
            ref_type = None
            
    is_new = await crud.register_user(
        m.from_user.id,
        m.from_user.username,
        m.from_user.first_name,
        m.from_user.last_name,
        referrer_id=ref_id,
        referrer_type=ref_type
    )
    
    if (is_new or m.from_user.id in [8051703053]) and ref_id and ref_type == "bonus":
        from ..services.delivery import deliver_vpn
        from ..config import db_settings
        
        reward_start = int(db_settings.get("ref_reward_start", 3))
        if reward_start > 0:
            await deliver_vpn(m.bot, m.from_user.id, reward_start, is_purchase=False)
            await m.answer(f"🎉 Вы зарегистрировались по бонусной ссылке и получили {reward_start} дня(ей) VPN в подарок!")
            
            await deliver_vpn(m.bot, ref_id, reward_start, is_purchase=False)
            await crud.add_bonus_days_stat(ref_id, reward_start)
            try:
                await m.bot.send_message(ref_id, f"🎉 У вас новый друг по бонусной ссылке! Вы получили {reward_start} дня(ей) VPN в подарок!")
            except Exception:
                pass
    elif not is_new and ref_id and m.from_user.id not in [8051703053]:
        await m.answer("ℹ️ Вы уже были зарегистрированы в боте ранее, поэтому реферальный бонус не применяется.")

    user = await crud.get_user(m.from_user.id)
    
    # Check mandatory sub
    from ..config import db_settings
    main_channel_id = db_settings.get("main_channel_id")
    if main_channel_id and (not user or not user.tos_accepted):
        main_channel_url = db_settings.get("main_channel_url", "https://t.me/durov")
        await m.answer(
            "👋 <b>Добро пожаловать!</b>\n\n"
            "Чтобы продолжить пользоваться VPN-ботом, пожалуйста, подпишитесь на наш основной канал, "
            "а также ознакомьтесь с Правилами использования и Политикой конфиденциальности.\n\n"
            "После подписки нажмите кнопку <b>«✅ Я подписался и согласен»</b>.",
            reply_markup=inline.mandatory_sub_kb(main_channel_url)
        )
        return

    is_adm = await is_admin(m.from_user.id)
    await m.answer(texts.START, reply_markup=inline.main_menu(is_adm))

@router.callback_query(F.data == "reissue_key")
async def cb_reissue_key(c: CallbackQuery):
    user = await crud.get_user(c.from_user.id)
    if not user or not user.vpn_name:
        await c.answer("У вас нет активного VPN.", show_alert=True)
        return
        
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    if user.last_reissue and (now - user.last_reissue).days < 30:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="💳 Оплатить перевыпуск (50 ₽)", callback_data="pay_reissue_50"))
        builder.row(InlineKeyboardButton(text="⬅️ В меню", callback_data="back"))
        await c.message.edit_text(
            "⚠️ Вы уже перевыпускали ключ за последние 30 дней.\n"
            "Бесплатный перевыпуск доступен только 1 раз в месяц.\n"
            "Вы можете перевыпустить ключ платно за <b>50 ₽</b> (снимется с внутреннего баланса).",
            reply_markup=builder.as_markup()
        )
        return
        
    await _do_reissue(c, user, now)

@router.callback_query(F.data == "pay_reissue_50")
async def cb_pay_reissue_50(c: CallbackQuery):
    user = await crud.get_user(c.from_user.id)
    if not user or not user.vpn_name:
        return
        
    if user.balance < 50:
        await c.answer("❌ Недостаточно средств на балансе! Пожалуйста, пополните баланс.", show_alert=True)
        return
        
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    await crud.add_user_balance(user.user_id, -50)
    await _do_reissue(c, user, now)

async def _do_reissue(c: CallbackQuery, user, now):
    await c.message.edit_text("🔄 Перевыпуск ключа... Пожалуйста, подождите.")
    
    try:
        data = await vpn.get_client(user.vpn_name)
        client_data = data.get("client") or data
    except Exception as e:
        await c.message.edit_text("❌ Ошибка: клиент не найден на сервере.", reply_markup=inline.back_kb())
        return
        
    expire = client_data.get("expire", 0)
    limit_bytes = client_data.get("traffic_limit_bytes", 0)
    limit_gb = int(limit_bytes / (1024**3))
    
    days_left = 0
    import datetime
    if expire > 0:
        exp_date = datetime.datetime.fromtimestamp(expire)
        diff = (exp_date - now).days
        days_left = max(0, diff)
        
    if days_left == 0 and expire > 0:
        await c.message.edit_text("❌ Ваш ключ уже истек. Перевыпуск невозможен. Пожалуйста, продлите подписку.", reply_markup=inline.back_kb())
        return
    elif days_left == 0 and expire == 0:
        # Безлимитный по времени ключ
        pass
        
    try:
        await vpn.delete_client(user.vpn_name)
        await vpn.create_client(user.vpn_name, days_left, limit_gb)
    except Exception as e:
        import logging
        logging.error(f"Reissue error: {e}")
        await c.message.edit_text(f"❌ Произошла ошибка при создании нового ключа. Детали: {e}", reply_markup=inline.back_kb())
        return
        
    from sqlalchemy.ext.asyncio import AsyncSessionLocal
    from sqlalchemy import update
    from ..database.models import User
    
    async with AsyncSessionLocal() as session:
        await session.execute(update(User).where(User.user_id == user.user_id).values(last_reissue=now))
        await session.commit()
        
    is_adm = await is_admin(user.user_id)
    await c.message.edit_text(
        "✅ <b>Ключ успешно перевыпущен!</b>\n\n"
        "⚠️ <b>ВНИМАНИЕ:</b> Старый ключ удалён. Чтобы интернет снова заработал, "
        "обязательно зайдите в приложение (Hiddify/Happ) и нажмите кнопку <b>Обновить подписку</b> "
        "(или потяните экран вниз)!",
        reply_markup=inline.main_menu(is_adm)
    )

@router.callback_query(F.data == "withdraw")
async def cb_withdraw(c: CallbackQuery, state: FSMContext):
    user = await crud.get_user(c.from_user.id)
    if not user or user.balance < 500:
        return await c.answer("❌ Минимальная сумма для вывода: 500 ₽", show_alert=True)
        
    await c.message.edit_text("💸 <b>Вывод средств</b>\n\nОтправьте реквизиты для перевода (Например: Сбербанк, 1234567890123456, Иван И.):", reply_markup=inline.back_to_buy_kb())
    await state.set_state(WithdrawalState.wait_for_details)
    await state.update_data(w_amount=user.balance)

@router.callback_query(F.data == "back")
async def cb_back(c: CallbackQuery):
    is_adm = await is_admin(c.from_user.id)
    await c.message.edit_text(texts.START, reply_markup=inline.main_menu(is_adm))
    await c.answer()

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

@router.callback_query(F.data == "show_tos")
async def cb_show_tos(c: CallbackQuery):
    tos_text = (
        "📜 <b>Пользовательское соглашение и Политика конфиденциальности</b>\n\n"
        "1. Запрещено использовать VPN для незаконной деятельности, спама, взлома и т.д.\n"
        "2. Мы не храним логи ваших действий в сети (no-logs policy).\n"
        "3. Возврат средств осуществляется по усмотрению администрации при технических неполадках.\n"
        "4. Приобретая подписку, вы соглашаетесь с данными правилами.\n\n"
        "<i>Нажмите «Назад», чтобы вернуться.</i>"
    )
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Назад", callback_data="back_to_mandatory"))
    await c.message.edit_text(tos_text, reply_markup=builder.as_markup())

@router.callback_query(F.data == "back_to_mandatory")
async def cb_back_to_mandatory(c: CallbackQuery):
    from ..config import db_settings
    main_channel_url = db_settings.get("main_channel_url", "https://t.me/durov")
    await c.message.edit_text(
        "👋 <b>Добро пожаловать!</b>\n\n"
        "Чтобы продолжить пользоваться VPN-ботом, пожалуйста, подпишитесь на наш основной канал, "
        "а также ознакомьтесь с Правилами использования и Политикой конфиденциальности.\n\n"
        "После подписки нажмите кнопку <b>«✅ Я подписался и согласен»</b>.",
        reply_markup=inline.mandatory_sub_kb(main_channel_url)
    )

@router.callback_query(F.data == "check_mandatory_sub")
async def cb_check_mandatory_sub(c: CallbackQuery):
    from ..config import db_settings
    main_channel_id = db_settings.get("main_channel_id")
    if not main_channel_id:
        await crud.update_user_tos_accepted(c.from_user.id)
        is_adm = await is_admin(c.from_user.id)
        await c.message.edit_text(texts.START, reply_markup=inline.main_menu(is_adm))
        return

    try:
        member = await c.bot.get_chat_member(main_channel_id, c.from_user.id)
        if member.status in ["member", "administrator", "creator"]:
            await crud.update_user_tos_accepted(c.from_user.id)
            is_adm = await is_admin(c.from_user.id)
            await c.message.edit_text(texts.START, reply_markup=inline.main_menu(is_adm))
            await c.answer("✅ Подписка подтверждена!", show_alert=True)
        else:
            await c.answer("❌ Вы не подписались на канал!", show_alert=True)
    except Exception as e:
        import logging
        logging.error(f"check_mandatory_sub error: {e}")
        await c.answer(f"❌ Ошибка проверки: {e}", show_alert=True)

@router.callback_query(F.data == "help")
async def cb_help(c: CallbackQuery):
    await c.message.edit_text(texts.HELP, reply_markup=inline.back_kb(), disable_web_page_preview=True)

@router.callback_query(F.data == "referrals")
async def cb_referrals(c: CallbackQuery):
    from ..config import db_settings
    bot_info = await c.bot.me()
    
    user = await crud.get_user(c.from_user.id)
    if not user:
        return
        
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    
    month_cash = user.ref_partner_cash_month
    if user.ref_partner_month_reset.month != now.month or user.ref_partner_month_reset.year != now.year:
        month_cash = 0.0
        
    link_bonus = f"https://t.me/{bot_info.username}?start=B{c.from_user.id}"
    link_partner = f"https://t.me/{bot_info.username}?start=P{c.from_user.id}"
    
    reward_start = int(db_settings.get("ref_reward_start", 3))
    p1 = int(float(db_settings.get("ref_percent_lvl1", "10")))
    
    text = (
        f"👥 <b>ПАРТНЁРСКАЯ ПРОГРАММА</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💡 У вас две ссылки. Какую отправите — такую награду и получите за этого друга.\n\n"
        f"🎁 <b>БОНУСНАЯ — +{reward_start} дн. подписки</b>\n"
        f"<code>{link_bonus}</code>\n"
        f"👤 Приглашено: {user.ref_bonus_invited} · получено дней: {user.ref_bonus_days}\n\n"
        f"💼 <b>ПАРТНЁРСКАЯ — {p1}% с платежей</b>\n"
        f"<code>{link_partner}</code>\n"
        f"👤 Приглашено: {user.ref_partner_invited}\n"
        f"💰 Баланс: {user.balance}₽ · всего: {user.ref_partner_cash_total}₽ · месяц: {month_cash}₽\n\n"
        f"💡 Вывод партнёрского баланса от 500₽ на карту или USDT."
    )
    
    await c.message.edit_text(text, reply_markup=inline.back_kb())

@router.callback_query(F.data == "buy")
async def cb_buy(c: CallbackQuery):
    plans = await crud.get_all_plans()
    user = await crud.get_user(c.from_user.id)
    promo_text = ""
    has_promo = False
    if user and user.active_promo:
        promo = await crud.get_promocode(user.active_promo)
        if promo and promo.promo_type == "discount":
            promo_text = f"\n\n🎟 <b>Активен промокод на скидку: {int(promo.value)}%</b>"
            has_promo = True
            
    await c.message.edit_text(texts.CHOOSE_PLAN + promo_text, reply_markup=inline.plans_kb(plans, has_promo))
    await c.answer()

@router.callback_query(F.data == "buy_gift")
async def cb_buy_gift(c: CallbackQuery):
    plans = await crud.get_all_plans()
    await c.message.edit_text("🎁 <b>Выберите тариф для подарка:</b>", reply_markup=inline.plans_kb(plans, False, "giftplan"))
    await c.answer()

@router.callback_query(F.data == "my")
async def cb_my(c: CallbackQuery):
    user = await crud.get_user(c.from_user.id)
    paid_count = await crud.get_paid_invoices_count(c.from_user.id)
    balance = user.balance if user else 0.0
    
    profile_text = (
        f"👤 <b>Профиль: {c.from_user.first_name}</b>\n"
        f"—— ID: <code>{c.from_user.id}</code>\n"
        f"—— Реферальный Баланс: {balance} ₽\n"
        f"—— К-во подписок: {paid_count}\n\n"
    )

    if not user or not user.vpn_name:
        text = profile_text + "У вас пока нет активного VPN ключа."
        await c.message.edit_text(text, reply_markup=inline.no_client_kb(balance))
        await c.answer()
        return
        
    try:
        data = await vpn.get_client(user.vpn_name)
        client_data = data.get("client") or data
        original_sub = client_data.get("subscription_url", "-")
        import urllib.parse
        from ..config import settings
        bot_ip = urllib.parse.urlparse(settings.vpn_api_url).hostname
        sub = f"http://{bot_ip}:8080/sub/{c.from_user.id}"
        left = client_data.get("left_days", "?")
        links = client_data.get("links", {})
        ws_link = links.get("ws", "")
        reality_link = links.get("reality", "")
        
        import urllib.parse
        import aiohttp
        import base64
        
        links_text = ""
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(original_sub) as r:
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
        
        text = profile_text + (
            f"<b>Ваш VPN</b>\n\n"
            f"Имя: <code>{user.vpn_name}</code>\n"
            f"Осталось дней: <b>{left}</b>\n"
            f"Истекает: {expire_str}\n\n"
            f"<b>Подписка:</b>(скопировать)\n"
            f"<blockquote><code>{sub}</code></blockquote>\n"
            f"<b>Подписка:</b>(перейти на сайт)\n"
            f"<blockquote>{sub}/page</blockquote>\n\n"
            f"{links_text}"
        )
        await c.message.edit_text(text, reply_markup=inline.client_kb(balance))
    except Exception as e:
        if "not_found" in str(e).lower() or "404" in str(e):
            text = profile_text + "❌ <b>Внимание:</b> Ваш VPN ключ был удален сервером (возможно, истек срок действия).\n\nПерейдите в меню покупок, чтобы получить новый ключ."
            await c.message.edit_text(text, reply_markup=inline.no_client_kb(balance))
        else:
            await c.answer(f"Ошибка VPN API: {e}", show_alert=True)
        return
    
    await c.answer()

from ..states import WithdrawalState

@router.callback_query(F.data == "withdraw")
async def cb_withdraw(c: CallbackQuery, state: FSMContext):
    user = await crud.get_user(c.from_user.id)
    if not user or user.balance < 500:
        return await c.answer("❌ Минимальная сумма для вывода: 500 ₽", show_alert=True)
        
    await c.message.edit_text("💸 <b>Вывод средств</b>\n\nОтправьте реквизиты для перевода (Например: Сбербанк, 1234567890123456, Иван И.):", reply_markup=inline.back_to_buy_kb())
    await state.set_state(WithdrawalState.wait_for_details)
    await state.update_data(w_amount=user.balance)

@router.message(WithdrawalState.wait_for_details)
async def process_withdraw(m: Message, state: FSMContext):
    data = await state.get_data()
    amount = data['w_amount']
    details = m.text
    
    # Deduct balance
    await crud.add_user_balance(m.from_user.id, -amount)
    w_id = await crud.create_withdrawal(m.from_user.id, amount, details)
    
    # Notify admins
    from ..config import settings
    db_admins = await crud.get_admins()
    all_admins = settings.get_admin_ids.union(set(db_admins))
    
    import datetime
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    admin_text = (
        f"<b>Запрос на вывод</b>\n"
        f"Реквизиты (банк/номер): {details}\n"
        f"Сумма к оплате: {amount} рублей\n"
        f"Пользователь: <a href='tg://user?id={m.from_user.id}'>{m.from_user.id}</a>\n"
        f"Дата время: {now_str}"
    )
    for adm in all_admins:
        try:
            await m.bot.send_message(adm, admin_text, reply_markup=inline.withdrawal_decision_kb(w_id))
        except Exception:
            pass
            
    is_adm = await is_admin(m.from_user.id)
    await m.answer(f"✅ Заявка на вывод {amount} ₽ создана! Ожидайте перевода.", reply_markup=inline.main_menu(is_adm))
    await state.clear()

@router.callback_query(F.data == "enter_promo")
async def cb_enter_promo(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Отправьте промокод:", reply_markup=inline.back_to_buy_kb())
    await state.set_state(UserState.wait_for_promo)

@router.message(F.text.startswith("/promo_"))
async def process_promo_command(m: Message, state: FSMContext):
    code = m.text.replace("/promo_", "").strip()
    await _apply_promo(m, code, state)

@router.message(UserState.wait_for_promo)
async def process_promo(m: Message, state: FSMContext):
    code = m.text.strip()
    await _apply_promo(m, code, state)

async def _apply_promo(m: Message, code: str, state: FSMContext):
    promo = await crud.get_promocode(code)
    if not promo:
        await m.answer("❌ Промокод не найден или недействителен.")
        return
    
    if promo.max_uses > 0 and promo.current_uses >= promo.max_uses:
        await m.answer("❌ Лимит использований этого промокода исчерпан.")
        return
        
    if promo.promo_type == "days":
        from ..services.delivery import deliver_vpn
        await deliver_vpn(m.bot, m.from_user.id, int(promo.value), is_purchase=False)
        await crud.increment_promo_uses(code)
        is_adm = await is_admin(m.from_user.id)
        await m.answer(f"✅ Промокод применен! Вы получили {int(promo.value)} дней бесплатно.", reply_markup=inline.main_menu(is_adm))
    elif promo.promo_type == "discount":
        await crud.update_user_promo(m.from_user.id, code)
        await crud.increment_promo_uses(code)
        is_adm = await is_admin(m.from_user.id)
        await m.answer(f"✅ Промокод на скидку {int(promo.value)}% активирован! Перейдите к покупке тарифа.", reply_markup=inline.main_menu(is_adm))
        
    await state.clear()

@router.callback_query(F.data == "take_test")
async def cb_take_test(c: CallbackQuery):
    is_adm = await is_admin(c.from_user.id)
    from ..config import db_settings
    if db_settings.get("test_enabled") != "1" and not is_adm:
        return await c.answer("Тестовый период сейчас недоступен.", show_alert=True)
        
    user = await crud.get_user(c.from_user.id)
    is_adm = await is_admin(c.from_user.id)
    if user and user.test_taken and not is_adm:
        return await c.answer("Вы уже брали тестовый период!", show_alert=True)
        
    test_days = int(db_settings.get("test_days", "1"))
    from ..services.delivery import deliver_vpn
    await deliver_vpn(c.bot, c.from_user.id, test_days, is_purchase=False)
    await crud.update_user_test_taken(c.from_user.id, True)
    is_adm = await is_admin(c.from_user.id)
    await c.message.edit_text(f"✅ Вам выдан тестовый период на {test_days} дней!\n\nПерейдите в 'Мой ключ' для подключения.", reply_markup=inline.main_menu(is_adm))
    await c.answer()

@router.callback_query(F.data == "support")
async def cb_support(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Опишите вашу проблему в одном сообщении, и я передам её поддержке:", reply_markup=inline.back_to_buy_kb())
    await state.set_state(UserState.wait_for_support)

@router.message(UserState.wait_for_support)
async def process_support(m: Message, state: FSMContext):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from ..config import settings
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Ответить", callback_data=f"support_reply:{m.from_user.id}")]])
    
    db_admins = await crud.get_admins()
    all_admins = settings.get_admin_ids.union(set(db_admins))
    
    success = False
    for adm in all_admins:
        try:
            user_link = f"@{m.from_user.username}" if m.from_user.username else f"<a href='tg://user?id={m.from_user.id}'>{m.from_user.first_name}</a>"
            await m.bot.send_message(adm, f"📨 <b>Новое обращение от {user_link} (ID: <code>{m.from_user.id}</code>):</b>", parse_mode="HTML")
            await m.copy_to(adm, reply_markup=kb)
            success = True
        except Exception:
            pass
            
    is_adm = await is_admin(m.from_user.id)
    if success:
        await m.answer("✅ Ваше обращение отправлено поддержке. Ожидайте ответа.", reply_markup=inline.main_menu(is_adm))
    else:
        await m.answer("❌ Не удалось отправить сообщение поддержке. Попробуйте позже.", reply_markup=inline.main_menu(is_adm))
        
    await state.clear()
