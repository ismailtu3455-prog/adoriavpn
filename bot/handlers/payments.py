import uuid
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, PreCheckoutQuery, Message, LabeledPrice
from ..texts import texts
from ..keyboards import inline
from ..config import settings
from ..database import crud
from ..services import cryptopay, tome
from ..services.delivery import deliver_vpn
from ..states import PaymentState

router = Router()

@router.callback_query(F.data.startswith("plan:") | F.data.startswith("giftplan:"))
async def cb_plan(c: CallbackQuery):
    is_gift = c.data.startswith("giftplan:")
    plan_key = c.data.split(":")[1]
    plan = await crud.get_plan(plan_key)
    if not plan:
        return await c.answer("Неизвестный тариф", show_alert=True)
        
    price = plan.price
    user = await crud.get_user(c.from_user.id)
    if user and user.active_promo:
        promo = await crud.get_promocode(user.active_promo)
        if promo and promo.promo_type == "discount":
            price = price * (1 - promo.value / 100)
    balance = user.balance if user else 0.0
            
    await c.message.edit_text(
        texts.CHOOSE_PAYMENT.format(title=plan.title, price=price),
        reply_markup=inline.payment_methods_kb(plan_key, balance, price, is_gift)
    )
    await c.answer()

@router.callback_query(F.data.startswith("pay:") | F.data.startswith("giftpay:"))
async def cb_pay(c: CallbackQuery, state: FSMContext):
    is_gift = c.data.startswith("giftpay:")
    _, plan_key, gateway = c.data.split(":")
    plan = await crud.get_plan(plan_key)
    if not plan:
        return await c.answer("Неизвестный тариф", show_alert=True)
        
    amount = plan.price
    user = await crud.get_user(c.from_user.id)
    if user and user.active_promo:
        promo = await crud.get_promocode(user.active_promo)
        if promo and promo.promo_type == "discount":
            amount = amount * (1 - promo.value / 100)
            
    desc = f"VPN {plan.title} для {c.from_user.id}"
    
    invoice_id = None
    pay_url = None
    usd_amount = None
    
    if gateway == "balance":
        if not user or user.balance < amount:
            return await c.answer("Недостаточно средств на балансе!", show_alert=True)
            
        await crud.add_user_balance(c.from_user.id, -amount)
        await crud.create_invoice(
            invoice_id=f"bal_{uuid.uuid4().hex[:8]}",
            user_id=c.from_user.id,
            plan=plan_key,
            days=plan.days,
            amount=amount,
            asset="RUB",
            gateway="balance",
            status="paid",
            is_gift=is_gift
        )
        await crud.update_user_promo(c.from_user.id, None)
        
        if is_gift:
            import secrets
            code = f"GIFT-{secrets.token_hex(4).upper()}"
            await crud.create_gift_card(code, plan.days)
            bot_info = await c.bot.me()
            await c.message.edit_text(f"✅ Подарочный ключ оплачен с баланса!\nВаш подарок готов.", reply_markup=inline.share_gift_kb(code, plan.days, bot_info.username, c.from_user.first_name))
        else:
            await deliver_vpn(c.bot, c.from_user.id, plan.days, is_purchase=True, gateway="Баланс")
            await c.message.edit_text(f"✅ Оплачено с баланса! Вам выдано {plan.days} дней.", reply_markup=inline.main_menu())
            
        await crud.update_user_promo(c.from_user.id, None)
        return
        
    elif gateway == "manual":
        invoice_id = str(uuid.uuid4())
        await crud.create_invoice(
            invoice_id=invoice_id,
            user_id=c.from_user.id,
            plan=plan_key,
            days=plan.days,
            amount=amount,
            asset="RUB",
            gateway="manual",
            status="pending_manual",
            is_gift=is_gift
        )
        
        from ..states import PaymentState
        await state.set_state(PaymentState.wait_for_receipt)
        await state.update_data(manual_invoice_id=invoice_id)
        
        text = (
            f"💳 <b>Перевод по реквизитам</b>\n\n"
            f"Тариф: {plan.title}\n"
            f"Сумма к оплате: <b>{amount} ₽</b>\n\n"
            f"Оплатите на карту Озон Банк: <code>89893338505</code>\n"
            f"Получатель: Исмаил\n\n"
            f"📸 <b>После успешной оплаты отправьте скриншот чека прямо в этот чат.</b>\n"
            f"<i>Для отмены нажмите кнопку ниже.</i>"
        )
        await c.message.edit_text(text, reply_markup=inline.back_to_buy_kb())
        await c.answer()
        return

    elif gateway == "cryptopay":
        amount = round(amount * 1.03, 2)
        usd_amount = round(amount * 0.0125, 2)
        res = await cryptopay.create_crypto_invoice(amount, desc, f"{c.from_user.id}:{plan_key}")
        if res:
            invoice_id, pay_url = res
    elif gateway == "stars":
        prefix = "giftstars" if is_gift else "stars"
        prices = [LabeledPrice(label="XTR", amount=int(amount / settings.stars_rate))]
        await c.message.answer_invoice(
            title=plan.title,
            description=desc,
            payload=f"{prefix}:{c.from_user.id}:{plan_key}:{amount}",
            provider_token="",
            currency="XTR",
            prices=prices
        )
        return await c.answer()
    elif gateway == "tome":
        res = await tome.create_tome_invoice(amount, desc)
        if res:
            invoice_id, pay_url = res
            
    if not invoice_id or not pay_url:
        return await c.answer("Ошибка создания счета. Попробуйте другой способ.", show_alert=True)
        
    db_asset = "RUB"
    if gateway == "cryptopay":
        msg_text = (
            f"🧾 <b>Счёт создан</b>\n\n"
            f"Тариф: {plan.title}\n"
            f"Способ: CryptoBot\n"
            f"Сумма: {usd_amount} USD (~{amount} RUB)\n\n"
            f"После оплаты нажмите «Я оплатил». Бот также проверяет оплаты автоматически."
        )
        db_asset = "USD"
    elif gateway == "tome":
        amount_with_fee = round(amount * 1.04, 2)
        msg_text = (
            f"🧾 <b>Счёт создан</b>\n\n"
            f"Тариф: {plan.title}\n"
            f"Способ: СБП / Карта\n"
            f"Сумма: {amount_with_fee} RUB\n\n"
            f"После оплаты нажмите «Я оплатил». Бот также проверяет оплаты автоматически."
        )

    await crud.create_invoice(
        invoice_id=invoice_id,
        user_id=c.from_user.id,
        plan=plan_key,
        days=plan.days,
        amount=usd_amount if gateway == "cryptopay" else amount,
        asset=db_asset,
        gateway=gateway,
        is_gift=is_gift
    )
    
    await c.message.edit_text(msg_text, reply_markup=inline.invoice_kb(pay_url, invoice_id))
    await c.answer()

@router.callback_query(F.data.startswith("cancel:"))
async def cb_cancel(c: CallbackQuery):
    invoice_id = c.data.split(":")[1]
    await crud.update_invoice_status(invoice_id, "canceled")
    await c.message.edit_text("Счет отменен.", reply_markup=inline.main_menu())
    await c.answer()
    
# Проверка оплаты происходит в фоновом цикле в __main__.py 
# или может быть вызвана кнопкой "Я оплатил", но чтобы не дублировать логику выдачи,
# сделаем заглушку, которая просто просит подождать.
@router.callback_query(F.data.startswith("check:"))
async def cb_check(c: CallbackQuery):
    await c.answer("Оплата проверяется автоматически. Подождите пару минут.", show_alert=True)

@router.pre_checkout_query()
async def pre_checkout_query(pcq: PreCheckoutQuery):
    await pcq.answer(ok=True)

@router.message(F.successful_payment)
async def successful_payment(m: Message):
    payload = m.successful_payment.invoice_payload
    if payload.startswith("stars:") or payload.startswith("giftstars:"):
        is_gift = payload.startswith("giftstars:")
        _, user_id, plan_key, orig_amount = payload.split(":")
        plan = await crud.get_plan(plan_key)
        
        charge_id = m.successful_payment.telegram_payment_charge_id
        await crud.create_invoice(
            invoice_id=charge_id,
            user_id=int(user_id),
            plan=plan_key,
            days=plan.days,
            amount=m.successful_payment.total_amount,
            asset="XTR",
            gateway="stars",
            status="paid",
            is_gift=is_gift
        )
        await crud.update_user_promo(int(user_id), None)
        
        if is_gift:
            import secrets
            code = f"GIFT-{secrets.token_hex(4).upper()}"
            await crud.create_gift_card(code, plan.days)
            bot_info = await m.bot.me()
            await m.answer(f"✅ Успешно оплачено Звездами!\nВаш подарок готов.", reply_markup=inline.share_gift_kb(code, plan.days, bot_info.username, m.from_user.first_name))
        else:
            await deliver_vpn(m.bot, int(user_id), plan.days, is_purchase=True, gateway="Telegram Stars")
            await crud.process_referral_bonus(m.bot, int(user_id), float(orig_amount))
            await m.answer(f"✅ Оплата Звездами прошла успешно! Вам выдано {plan.days} дней.")
        
        from ..config import db_settings
        channel_id = db_settings.get("payment_channel_id")
        if channel_id:
            try:
                await m.bot.send_message(
                    chat_id=int(channel_id),
                    text=f"💰 <b>Новая оплата!</b>\nПользователь: <a href='tg://user?id={user_id}'>{user_id}</a>\nСумма: {m.successful_payment.total_amount} XTR\nТариф: {plan.days} дней"
                )
            except Exception:
                pass

@router.message(PaymentState.wait_for_receipt, F.photo | F.document)
async def process_receipt(m: Message, state: FSMContext):
    data = await state.get_data()
    invoice_id = data.get("manual_invoice_id")
    if not invoice_id:
        await m.answer("Счет не найден. Попробуйте оформить заказ заново.")
        await state.clear()
        return
        
    inv = await crud.get_invoice(invoice_id)
    if not inv or inv.status != "pending_manual":
        await m.answer("Заказ уже обработан или отменен.")
        await state.clear()
        return

    # Notify user
    await m.answer("✅ Чек получен! Ожидайте подтверждения администратором.", reply_markup=inline.main_menu())
    await state.clear()
    
    # Send to admin
    from ..config import db_settings, settings
    channel_id = db_settings.get("payment_channel_id")
    
    admin_text = (
        f"📝 <b>Новая заявка на ручную оплату</b>\n\n"
        f"Юзер: <a href='tg://user?id={m.from_user.id}'>{m.from_user.id}</a>\n"
        f"Тариф: {inv.plan} ({inv.days} дней)\n"
        f"Сумма: {inv.amount} ₽\n"
        f"Подарок: {'Да' if inv.is_gift else 'Нет'}\n\n"
        f"Проверьте поступление средств и примите решение."
    )
    
    markup = inline.manual_pay_decision_kb(invoice_id)
    
    # Try sending to payment channel if configured, otherwise fallback to admin IDs
    sent = False
    if channel_id:
        try:
            if m.photo:
                await m.bot.send_photo(int(channel_id), m.photo[-1].file_id, caption=admin_text, reply_markup=markup)
            else:
                await m.bot.send_document(int(channel_id), m.document.file_id, caption=admin_text, reply_markup=markup)
            sent = True
        except Exception:
            pass
            
    if not sent:
        for adm in settings.admin_ids:
            try:
                if m.photo:
                    await m.bot.send_photo(adm, m.photo[-1].file_id, caption=admin_text, reply_markup=markup)
                else:
                    await m.bot.send_document(adm, m.document.file_id, caption=admin_text, reply_markup=markup)
            except Exception:
                pass
