from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from ..texts import texts
from ..keyboards import inline
from ..database import crud
from ..config import db_settings
from ..states import AdminState, AdminPaymentState, AdminSettingsState, AdminInvoiceState

router = Router()

@router.callback_query(F.data == "adm:home")
async def cb_adm_home(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.edit_text(texts.ADMIN_HOME, reply_markup=inline.admin_menu_kb())
    await c.answer()

@router.callback_query(F.data == "adm:stats")
async def cb_adm_stats(c: CallbackQuery):
    stats = await crud.get_dashboard_stats()
    text = (
        f"<b>📊 Статистика</b>\n\n"
        f"Пользователей: {stats['users']['total']}\n"
        f"С VPN: {stats['users']['with_vpn']}\n\n"
        f"Инвойсов: {stats['invoices']['total']}\n"
        f"Оплачено: {stats['invoices']['paid']}\n"
        f"Ожидают: {stats['invoices']['active']}"
    )
    await c.message.edit_text(text, reply_markup=inline.admin_back_kb())
    await c.answer()

@router.callback_query(F.data == "adm:manage")
async def cb_adm_manage(c: CallbackQuery):
    await c.message.edit_text("⚙️ <b>Меню управления</b>\n\nВыберите действие:", reply_markup=inline.admin_manage_kb())

@router.callback_query(F.data == "adm:payments")
async def cb_adm_payments(c: CallbackQuery):
    await c.message.edit_text(
        "💳 <b>Настройка систем оплат</b>\n\nВключите нужные методы для ваших клиентов:",
        reply_markup=inline.admin_payments_kb(db_settings)
    )

# --- Payment Setup ---
@router.callback_query(F.data == "adm:pay_setup:crypto")
async def cb_setup_crypto(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text(
        "🪙 <b>CryptoBot</b>\n\n"
        "Для подключения отправьте API токен.\n"
        "Получить токен: <a href='https://t.me/CryptoBot?start=pay'>Crypto Pay</a>\n\n"
        "<i>Для отключения отправьте 0</i>",
        reply_markup=inline.admin_back_kb(),
        disable_web_page_preview=True
    )
    await state.set_state(AdminPaymentState.wait_for_crypto_token)

@router.message(AdminPaymentState.wait_for_crypto_token)
async def process_crypto_token(m: Message, state: FSMContext):
    val = m.text.strip()
    if val == "0":
        val = None
    await crud.set_setting("crypto_pay_token", val)
    db_settings["crypto_pay_token"] = val
    await m.answer("✅ Настройки CryptoBot сохранены!", reply_markup=inline.admin_menu_kb())
    await state.clear()

@router.callback_query(F.data == "adm:pay_setup:stars")
async def cb_setup_stars(c: CallbackQuery):
    current = db_settings.get("stars_enabled")
    new_val = "0" if current == "1" else "1"
    await crud.set_setting("stars_enabled", new_val)
    db_settings["stars_enabled"] = new_val
    await c.message.edit_text(
        f"⭐️ <b>Telegram Stars</b>\n\nУспешно {'включены' if new_val == '1' else 'отключены'}!",
        reply_markup=inline.admin_payments_kb(db_settings)
    )

@router.callback_query(F.data == "adm:pay_setup:tome")
async def cb_setup_tome(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text(
        "💳 <b>СБП (tome.ge)</b>\n\n"
        "Зарегистрируйтесь на сайте tome.ge и получите Shop ID и Secret Key.\n"
        "Отправьте их сюда через пробел (например: <code>12345 secret_abc123</code>)\n\n"
        "<i>Для отключения отправьте 0</i>",
        reply_markup=inline.admin_back_kb()
    )
    await state.set_state(AdminPaymentState.wait_for_tome_creds)

@router.message(AdminPaymentState.wait_for_tome_creds)
async def process_tome_creds(m: Message, state: FSMContext):
    val = m.text.strip()
    if val == "0":
        await crud.set_setting("tome_shop_id", None)
        await crud.set_setting("tome_secret_key", None)
        db_settings["tome_shop_id"] = None
        db_settings["tome_secret_key"] = None
    else:
        parts = val.split()
        if len(parts) != 2:
            await m.answer("⚠️ Неверный формат. Отправьте Shop ID и Secret Key через пробел.", reply_markup=inline.admin_back_kb())
            return
        await crud.set_setting("tome_shop_id", parts[0])
        await crud.set_setting("tome_secret_key", parts[1])
        db_settings["tome_shop_id"] = parts[0]
        db_settings["tome_secret_key"] = parts[1]
        
    await m.answer("✅ Настройки tome.ge сохранены!", reply_markup=inline.admin_menu_kb())
    await state.clear()

# --- Management Tools ---
@router.callback_query(F.data == "adm:find_user")
async def cb_find_user(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Отправьте Telegram ID или юзернейм (@username) пользователя:", reply_markup=inline.admin_back_kb())
    await state.set_state(AdminState.find_user)

@router.message(AdminState.find_user)
async def process_find_user(m: Message, state: FSMContext):
    u = await crud.get_user_by_id_or_username(m.text)
    if not u:
        await m.answer("❌ Пользователь не найден. Убедитесь, что он запускал бота.", reply_markup=inline.admin_back_kb())
        return
    await m.answer(
        f"👤 Пользователь <code>{u.user_id}</code> (@{u.username})\n"
        f"Имя: {u.first_name}\n"
        f"Ключ: {u.vpn_name or 'Нет'}",
        reply_markup=inline.user_manage_kb(u.user_id)
    )
    await state.clear()

@router.callback_query(F.data.startswith("adm:del_user:"))
async def cb_del_user(c: CallbackQuery):
    user_id = int(c.data.split(":")[2])
    u = await crud.get_user(user_id)
    if u:
        if u.vpn_name:
            from ..services.vpn import delete_client
            try:
                await delete_client(u.vpn_name)
            except Exception:
                pass
        await crud.delete_user(user_id)
        
    await c.message.edit_text(f"✅ Пользователь {user_id} полностью удален из базы. Теперь он может перейти по реферальной ссылке как новый юзер.", reply_markup=inline.admin_menu_kb())

@router.callback_query(F.data.startswith("adm:add_balance:"))
async def cb_add_balance(c: CallbackQuery, state: FSMContext):
    user_id = int(c.data.split(":")[2])
    await state.update_data(balance_user_id=user_id)
    await c.message.edit_text(f"Отправьте сумму для начисления на баланс пользователю {user_id}:", reply_markup=inline.admin_back_kb())
    await state.set_state(AdminState.wait_for_balance_amount)

@router.message(AdminState.wait_for_balance_amount)
async def process_add_balance_amount(m: Message, state: FSMContext):
    try:
        amount = float(m.text)
        data = await state.get_data()
        user_id = data['balance_user_id']
        await crud.add_user_balance(user_id, amount)
        await m.answer(f"✅ Баланс пользователя {user_id} пополнен на {amount} ₽!", reply_markup=inline.admin_menu_kb())
        
        # Notify user
        try:
            await m.bot.send_message(user_id, f"💰 <b>Ваш баланс пополнен!</b>\nАдминистратор начислил вам {amount} ₽.")
        except Exception:
            pass
            
        await state.clear()
    except ValueError:
        await m.answer("Сумма должна быть числом!")

@router.callback_query(F.data == "adm:gift_create")
async def cb_gift_create(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Отправьте количество дней для подарочного ключа (например: 30):", reply_markup=inline.admin_back_kb())
    await state.set_state(AdminState.wait_for_gift_days)

@router.message(AdminState.wait_for_gift_days)
async def process_gift_days(m: Message, state: FSMContext):
    if not m.text.isdigit():
        return
    days = int(m.text)
    import secrets
    code = f"GIFT-{secrets.token_hex(4).upper()}"
    await crud.create_gift_card(code, days)
    bot_info = await m.bot.me()
    link = f"https://t.me/{bot_info.username}?start={code}"
    
    text = (
        f"✅ <b>Подарочный ключ создан!</b>\n\n"
        f"Дней: {days}\n"
        f"Код: <code>{code}</code>\n"
        f"Ссылка для активации:\n<code>{link}</code>"
    )
    await m.answer(text, reply_markup=inline.admin_menu_kb())
    await state.clear()

@router.callback_query(F.data == "adm:grant_vpn")
async def cb_grant_vpn(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Отправьте Telegram ID или юзернейм (@username) пользователя, которому выдать VPN:", reply_markup=inline.admin_back_kb())
    await state.set_state(AdminState.grant_user_id)

@router.message(AdminState.grant_user_id)
async def process_grant_id(m: Message, state: FSMContext):
    u = await crud.get_user_by_id_or_username(m.text)
    if not u:
        await m.answer("❌ Пользователь не найден. Юзер должен запустить бота.", reply_markup=inline.admin_back_kb())
        return
    await state.update_data(user_id=u.user_id)
    await m.answer("На сколько дней выдать VPN? (Напишите число)", reply_markup=inline.admin_back_kb())
    await state.set_state(AdminState.grant_days)

@router.message(AdminState.grant_days)
async def process_grant_days(m: Message, state: FSMContext):
    if not m.text.isdigit():
        return
    days = int(m.text)
    data = await state.get_data()
    user_id = data['user_id']
    
    from ..services.delivery import deliver_vpn
    success = await deliver_vpn(m.bot, user_id, days, is_purchase=False)
    if success:
        await m.answer(f"✅ VPN успешно выдан юзеру <code>{user_id}</code> на {days} дней!", reply_markup=inline.admin_menu_kb())
    else:
        await m.answer(f"❌ Ошибка при выдаче VPN. Проверьте логи.", reply_markup=inline.admin_menu_kb())
    await state.clear()

@router.callback_query(F.data == "adm:payinvoice")
async def cb_payinvoice_list(c: CallbackQuery, state: FSMContext):
    await state.update_data(inv_page=0, inv_sort="time_desc", inv_search=None)
    await show_invoices_page(c.message, 0, "time_desc", None)
    await c.answer()

async def show_invoices_page(message: Message, page: int, sort_mode: str, search_user_id: int | None):
    invs = await crud.get_active_invoices_filtered(sort_mode, search_user_id)
    if not invs:
        text = "📭 Активных счетов не найдено."
        if search_user_id:
            text += " (С учетом поиска)"
    else:
        text = f"💳 <b>Одобрение счетов</b>\nНайдено неоплаченных: {len(invs)}"
        
    await message.edit_text(text, reply_markup=inline.invoices_list_kb(invs, page, sort_mode, bool(search_user_id)))

@router.callback_query(F.data.startswith("adm:inv:page:"))
async def cb_inv_page(c: CallbackQuery, state: FSMContext):
    page = int(c.data.split(":")[3])
    data = await state.get_data()
    sort_mode = data.get("inv_sort", "time_desc")
    search_user_id = data.get("inv_search")
    await state.update_data(inv_page=page)
    await show_invoices_page(c.message, page, sort_mode, search_user_id)
    await c.answer()

@router.callback_query(F.data == "adm:inv:sort")
async def cb_inv_sort(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    sort_mode = data.get("inv_sort", "time_desc")
    modes = ["time_desc", "time_asc", "price_desc", "price_asc"]
    next_idx = (modes.index(sort_mode) + 1) % len(modes)
    new_mode = modes[next_idx]
    
    search_user_id = data.get("inv_search")
    page = data.get("inv_page", 0)
    
    await state.update_data(inv_sort=new_mode)
    await show_invoices_page(c.message, page, new_mode, search_user_id)
    await c.answer()

@router.callback_query(F.data == "adm:inv:search")
async def cb_inv_search(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Отправьте Telegram ID или юзернейм (@username) для поиска инвойсов:", reply_markup=inline.admin_back_kb())
    from ..states import AdminInvoiceState
    await state.set_state(AdminInvoiceState.wait_for_search)
    await c.answer()

@router.callback_query(F.data == "adm:inv:clear_search")
async def cb_inv_clear_search(c: CallbackQuery, state: FSMContext):
    await state.update_data(inv_search=None, inv_page=0)
    data = await state.get_data()
    await show_invoices_page(c.message, 0, data.get("inv_sort", "time_desc"), None)
    await c.answer()

@router.message(AdminInvoiceState.wait_for_search)
async def process_inv_search(m: Message, state: FSMContext):
    u = await crud.get_user_by_id_or_username(m.text)
    if not u:
        await m.answer("❌ Пользователь не найден. Он должен хотя бы раз запустить бота.", reply_markup=inline.admin_back_kb())
        return
        
    await state.update_data(inv_search=u.user_id, inv_page=0)
    data = await state.get_data()
    sort_mode = data.get("inv_sort", "time_desc")
    
    msg = await m.answer("⏳ Поиск...")
    await show_invoices_page(msg, 0, sort_mode, u.user_id)
    await state.set_state(None)

@router.callback_query(F.data.startswith("adm:inv:approve:"))
async def cb_inv_approve(c: CallbackQuery, state: FSMContext):
    invoice_id = c.data.split(":")[3]
    inv = await crud.get_invoice(invoice_id)
    if not inv or inv.status != "active":
        await c.answer("⚠️ Инвойс не найден или уже оплачен!", show_alert=True)
        data = await state.get_data()
        await show_invoices_page(c.message, data.get("inv_page", 0), data.get("inv_sort", "time_desc"), data.get("inv_search"))
        return
        
    await crud.update_invoice_status(invoice_id, "paid")
    from ..services.delivery import deliver_vpn
    success = await deliver_vpn(c.bot, inv.user_id, inv.days, is_purchase=True)
    if success:
        plan = await crud.get_plan(inv.plan)
        if plan:
            await crud.process_referral_bonus(c.bot, inv.user_id, plan.price)
        await c.answer("✅ Успешно одобрено и VPN выдан!", show_alert=True)
    else:
        await c.answer("❌ Одобрено, но произошла ошибка при выдаче VPN", show_alert=True)
        
    data = await state.get_data()
    await show_invoices_page(c.message, data.get("inv_page", 0), data.get("inv_sort", "time_desc"), data.get("inv_search"))

@router.callback_query(F.data == "adm:broadcast")
async def cb_broadcast(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Отправьте сообщение для рассылки всем пользователям:", reply_markup=inline.admin_back_kb())
    await state.set_state(AdminState.broadcast)

@router.message(AdminState.broadcast)
async def process_broadcast(m: Message, state: FSMContext):
    users = await crud.get_all_users()
    count = 0
    for u in users:
        try:
            await m.copy_to(u.user_id)
            count += 1
        except Exception:
            pass
    await m.answer(f"✅ Рассылка завершена! Отправлено: {count} пользователям.", reply_markup=inline.admin_menu_kb())
    await state.clear()

# --- Referral Setup ---
@router.callback_query(F.data == "adm:ref_setup")
async def cb_ref_setup(c: CallbackQuery):
    await c.message.edit_text("⚙️ <b>Настройка рефералов</b>\n\nУстановите награды:", reply_markup=inline.admin_ref_setup_kb(db_settings))

@router.callback_query(F.data == "adm:set_ref_start")
async def cb_set_ref_start(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Отправьте количество дней, которое получат оба юзера при регистрации реферала:", reply_markup=inline.admin_back_kb())
    await state.set_state(AdminSettingsState.wait_for_ref_start)

@router.message(AdminSettingsState.wait_for_ref_start)
async def process_set_ref_start(m: Message, state: FSMContext):
    if not m.text.isdigit():
        return
    await crud.set_setting("ref_reward_start", m.text)
    db_settings["ref_reward_start"] = m.text
    await m.answer("✅ Настройка сохранена!", reply_markup=inline.admin_menu_kb())
    await state.clear()

@router.callback_query(F.data == "adm:set_ref_lvl1")
async def cb_set_ref_lvl1(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Отправьте процент кэшбэка для рефералов 1 уровня (например, 10):", reply_markup=inline.admin_back_kb())
    await state.set_state(AdminSettingsState.wait_for_ref_lvl1)

@router.message(AdminSettingsState.wait_for_ref_lvl1)
async def process_set_ref_lvl1(m: Message, state: FSMContext):
    if not m.text.isdigit():
        return
    await crud.set_setting("ref_percent_lvl1", m.text)
    db_settings["ref_percent_lvl1"] = m.text
    await m.answer("✅ Настройка сохранена!", reply_markup=inline.admin_menu_kb())
    await state.clear()

@router.callback_query(F.data == "adm:set_ref_lvl2")
async def cb_set_ref_lvl2(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Отправьте процент кэшбэка для рефералов 2 уровня (например, 5):", reply_markup=inline.admin_back_kb())
    await state.set_state(AdminSettingsState.wait_for_ref_lvl2)

@router.message(AdminSettingsState.wait_for_ref_lvl2)
async def process_set_ref_lvl2(m: Message, state: FSMContext):
    if not m.text.isdigit():
        return
    await crud.set_setting("ref_percent_lvl2", m.text)
    db_settings["ref_percent_lvl2"] = m.text
    await m.answer("✅ Настройка сохранена!", reply_markup=inline.admin_menu_kb())
    await state.clear()

# --- Admins Management ---
@router.callback_query(F.data == "adm:admins")
async def cb_adm_admins(c: CallbackQuery):
    admins = await crud.get_admins()
    await c.message.edit_text("👥 <b>Администраторы</b>\n\nВы можете удалять существующих и добавлять новых:", reply_markup=inline.admin_list_kb(admins))

@router.callback_query(F.data.startswith("adm:del_admin:"))
async def cb_del_admin(c: CallbackQuery):
    adm_id = int(c.data.split(":")[2])
    await crud.remove_admin(adm_id)
    await c.answer("✅ Администратор удален!")
    admins = await crud.get_admins()
    await c.message.edit_reply_markup(reply_markup=inline.admin_list_kb(admins))

@router.callback_query(F.data == "adm:add_admin")
async def cb_add_admin(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Отправьте Telegram ID или юзернейм (@username) нового администратора:", reply_markup=inline.admin_back_kb())
    await state.set_state(AdminSettingsState.wait_for_admin_id)

@router.message(AdminSettingsState.wait_for_admin_id)
async def process_add_admin(m: Message, state: FSMContext):
    u = await crud.get_user_by_id_or_username(m.text)
    if u:
        user_id = u.user_id
    elif m.text.isdigit() or (m.text.startswith('-') and m.text[1:].isdigit()):
        user_id = int(m.text)
    else:
        await m.answer("❌ Пользователь не найден. Он должен хотя бы раз запустить бота.", reply_markup=inline.admin_back_kb())
        return
        
    await crud.add_admin(user_id)
    await m.answer("✅ Администратор добавлен!", reply_markup=inline.admin_menu_kb())
    await state.clear()

# --- Plans Management ---
@router.callback_query(F.data == "adm:plans")
async def cb_adm_plans(c: CallbackQuery):
    plans = await crud.get_all_plans()
    await c.message.edit_text("📋 <b>Тарифы</b>\n\nСписок текущих тарифов:", reply_markup=inline.plans_list_kb(plans))

@router.callback_query(F.data.startswith("adm:del_plan:"))
async def cb_del_plan(c: CallbackQuery):
    plan_id = c.data.split(":")[2]
    await crud.delete_plan(plan_id)
    await c.answer("✅ Тариф удален!")
    plans = await crud.get_all_plans()
    await c.message.edit_reply_markup(reply_markup=inline.plans_list_kb(plans))

@router.callback_query(F.data == "adm:add_plan")
async def cb_add_plan(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Придумайте ID для тарифа (на английском, например '6m' или '1y'):", reply_markup=inline.admin_back_kb())
    await state.set_state(AdminSettingsState.wait_for_plan_id)

@router.message(AdminSettingsState.wait_for_plan_id)
async def process_add_plan_id(m: Message, state: FSMContext):
    await state.update_data(plan_id=m.text)
    await m.answer("Отправьте название тарифа (например, '6 месяцев'):")
    await state.set_state(AdminSettingsState.wait_for_plan_title)

@router.message(AdminSettingsState.wait_for_plan_title)
async def process_add_plan_title(m: Message, state: FSMContext):
    await state.update_data(title=m.text)
    await m.answer("Отправьте длительность в ДНЯХ (например, '180'):")
    await state.set_state(AdminSettingsState.wait_for_plan_days)

@router.message(AdminSettingsState.wait_for_plan_days)
async def process_add_plan_days(m: Message, state: FSMContext):
    if not m.text.isdigit():
        return
    await state.update_data(days=int(m.text))
    await m.answer("Отправьте стоимость в РУБЛЯХ (например, '800'):")
    await state.set_state(AdminSettingsState.wait_for_plan_price)

@router.message(AdminSettingsState.wait_for_plan_price)
async def process_add_plan_price(m: Message, state: FSMContext):
    try:
        price = float(m.text)
        data = await state.get_data()
        await crud.create_plan(data['plan_id'], data['title'], data['days'], price)
        await m.answer("✅ Новый тариф успешно добавлен!", reply_markup=inline.admin_menu_kb())
        await state.clear()
    except ValueError:
        await m.answer("Стоимость должна быть числом!")

# --- Promos Management ---
@router.callback_query(F.data == "adm:promos")
async def cb_adm_promos(c: CallbackQuery):
    promos = await crud.get_all_promocodes()
    await c.message.edit_text("🎟 <b>Промокоды</b>\n\nСписок текущих промокодов:", reply_markup=inline.promos_list_kb(promos))

@router.callback_query(F.data.startswith("adm:del_promo:"))
async def cb_del_promo(c: CallbackQuery):
    code = c.data.split(":")[2]
    await crud.delete_promocode(code)
    await c.answer("✅ Промокод удален!")
    promos = await crud.get_all_promocodes()
    await c.message.edit_reply_markup(reply_markup=inline.promos_list_kb(promos))

@router.callback_query(F.data.startswith("adm:pay_setup:"))
async def cb_adm_pay_setup(c: CallbackQuery, state: FSMContext):
    system = c.data.split(":")[2]
    
    if system == "balance":
        from ..config import db_settings
        current = db_settings.get("balance_pay_enabled", "1")
        new_val = "0" if current == "1" else "1"
        await crud.update_setting("balance_pay_enabled", new_val)
        from ..config import db_settings
        db_settings["balance_pay_enabled"] = new_val
        await c.message.edit_reply_markup(reply_markup=inline.admin_payments_kb(db_settings))
        return await c.answer("Настройка оплаты с баланса обновлена.")
        
    elif system == "stars":
        from ..config import db_settings
        current = db_settings.get("stars_enabled", "0")
        new_val = "0" if current == "1" else "1"
        await crud.update_setting("stars_enabled", new_val)
        from ..config import db_settings
        db_settings["stars_enabled"] = new_val
        await c.message.edit_reply_markup(reply_markup=inline.admin_payments_kb(db_settings))
        return await c.answer("Настройка Telegram Stars обновлена.")

@router.callback_query(F.data == "adm:add_promo")
async def cb_add_promo(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Придумайте код (без пробелов, например 'SALE20'):", reply_markup=inline.admin_back_kb())
    await state.set_state(AdminSettingsState.wait_for_promo_code)

@router.message(AdminSettingsState.wait_for_promo_code)
async def process_add_promo_code(m: Message, state: FSMContext):
    await state.update_data(code=m.text)
    await m.answer("Выберите тип промокода:", reply_markup=inline.promo_type_kb())
    await state.set_state(AdminSettingsState.wait_for_promo_type)

@router.callback_query(F.data.startswith("adm:promo_type:"))
async def cb_promo_type(c: CallbackQuery, state: FSMContext):
    p_type = c.data.split(":")[2]
    await state.update_data(promo_type=p_type)
    if p_type == "discount":
        await c.message.edit_text("Введите размер скидки в ПРОЦЕНТАХ (например, '20'):", reply_markup=inline.admin_back_kb())
    else:
        await c.message.edit_text("Введите количество бесплатных ДНЕЙ (например, '5'):", reply_markup=inline.admin_back_kb())
    await state.set_state(AdminSettingsState.wait_for_promo_value)

@router.message(AdminSettingsState.wait_for_promo_value)
async def process_promo_value(m: Message, state: FSMContext):
    try:
        val = float(m.text)
        await state.update_data(value=val)
        await m.answer("Введите лимит использований (0 - безлимит):", reply_markup=inline.admin_back_kb())
        await state.set_state(AdminSettingsState.wait_for_promo_uses)
    except ValueError:
        pass

@router.message(AdminSettingsState.wait_for_promo_uses)
async def process_promo_uses(m: Message, state: FSMContext):
    if not m.text.isdigit():
        return
    data = await state.get_data()
    await crud.create_promocode(data['code'], data['promo_type'], data['value'], int(m.text))
    await m.answer("✅ Промокод успешно создан!", reply_markup=inline.admin_menu_kb())
    await state.clear()

# --- Test & Limits Setup ---
@router.callback_query(F.data == "adm:test_setup")
async def cb_test_setup(c: CallbackQuery):
    await c.message.edit_text("🎁 <b>Настройка Теста и Лимитов</b>", reply_markup=inline.admin_test_setup_kb(db_settings))

@router.callback_query(F.data == "adm:toggle_test")
async def cb_toggle_test(c: CallbackQuery):
    current = db_settings.get("test_enabled", "0")
    new_val = "1" if current == "0" else "0"
    await crud.set_setting("test_enabled", new_val)
    db_settings["test_enabled"] = new_val
    await c.message.edit_reply_markup(reply_markup=inline.admin_test_setup_kb(db_settings))

@router.callback_query(F.data == "adm:set_test_days")
async def cb_set_test_days(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Введите количество дней для бесплатного теста:", reply_markup=inline.admin_back_kb())
    await state.set_state(AdminSettingsState.wait_for_test_days)

@router.message(AdminSettingsState.wait_for_test_days)
async def process_set_test_days(m: Message, state: FSMContext):
    if not m.text.isdigit():
        return
    await crud.set_setting("test_days", m.text)
    db_settings["test_days"] = m.text
    await m.answer("✅ Сохранено!", reply_markup=inline.admin_menu_kb())
    await state.clear()

@router.callback_query(F.data == "adm:set_limit")
async def cb_set_limit(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Введите лимит трафика в ГБ по умолчанию (0 = безлимит):", reply_markup=inline.admin_back_kb())
    await state.set_state(AdminSettingsState.wait_for_limit_gb)

@router.message(AdminSettingsState.wait_for_limit_gb)
async def process_set_limit(m: Message, state: FSMContext):
    if not m.text.isdigit():
        return
    await crud.set_setting("default_limit_gb", m.text)
    db_settings["default_limit_gb"] = m.text
    await m.answer("✅ Лимит по умолчанию сохранен!", reply_markup=inline.admin_menu_kb())
    await state.clear()

# --- Channel Setup ---
@router.callback_query(F.data == "adm:channels_setup")
async def cb_channels_setup(c: CallbackQuery):
    await c.message.edit_text("⚙️ <b>Настройки каналов</b>\nВыберите, какой канал настроить:", reply_markup=inline.admin_channels_setup_kb())

@router.callback_query(F.data == "adm:set_main_channel")
async def cb_set_main_channel(c: CallbackQuery, state: FSMContext):
    bot_me = await c.bot.me()
    await c.message.edit_text(
        "📢 <b>Настройка основного канала (Обяз. подписка)</b>\n\n"
        "Отправьте пересланное сообщение из вашего канала.\n"
        "⚠️ <b>Обязательно:</b> Бот должен быть администратором в этом канале с правом приглашать пользователей.\n"
        "Для удобства нажмите кнопку ниже, добавьте бота в канал, а затем перешлите сюда любое сообщение оттуда.\n\n"
        "Отправьте 0, чтобы отключить обязательную подписку.",
        reply_markup=inline.admin_channel_setup_kb(bot_me.username)
    )
    await state.set_state(AdminSettingsState.wait_for_main_channel)

@router.message(AdminSettingsState.wait_for_main_channel)
async def process_main_channel(m: Message, state: FSMContext):
    if m.text and m.text.strip() == "0":
        await crud.set_setting("main_channel_id", None)
        await crud.set_setting("main_channel_url", None)
        db_settings["main_channel_id"] = None
        db_settings["main_channel_url"] = None
        await m.answer("✅ Обязательная подписка отключена!", reply_markup=inline.admin_menu_kb())
        await state.clear()
        return

    if not m.forward_from_chat or m.forward_from_chat.type != "channel":
        await m.answer("❌ Это не пересланное сообщение из канала. Попробуйте еще раз или отправьте 0 для отмены.")
        return
        
    chat_id = m.forward_from_chat.id
    try:
        invite_link = await m.bot.export_chat_invite_link(chat_id)
        await crud.set_setting("main_channel_id", str(chat_id))
        await crud.set_setting("main_channel_url", invite_link)
        db_settings["main_channel_id"] = str(chat_id)
        db_settings["main_channel_url"] = invite_link
        await m.answer("✅ Основной канал успешно установлен!", reply_markup=inline.admin_menu_kb())
        await state.clear()
    except Exception as e:
        await m.answer(f"❌ Ошибка. Убедитесь, что бот является администратором канала. Детали: {e}")

@router.callback_query(F.data == "adm:set_pay_channel")
async def cb_set_paychannel(c: CallbackQuery, state: FSMContext):
    bot_me = await c.bot.me()
    await c.message.edit_text(
        "🔔 <b>Настройка канала уведомлений (Логи покупок)</b>\n\n"
        "Отправьте пересланное сообщение из вашего канала.\n"
        "⚠️ <b>Обязательно:</b> Бот должен быть администратором в этом канале с правом публикации сообщений.\n"
        "Для удобства можете нажать кнопку ниже, чтобы добавить бота в свой канал.\n\n"
        "Отправьте 0, чтобы отключить уведомления.",
        reply_markup=inline.admin_channel_setup_kb(bot_me.username)
    )
    await state.set_state(AdminSettingsState.wait_for_payment_channel)

@router.message(AdminSettingsState.wait_for_payment_channel)
async def process_paychannel(m: Message, state: FSMContext):
    if m.text and m.text.strip() == "0":
        await crud.set_setting("payment_channel_id", None)
        db_settings["payment_channel_id"] = None
        await m.answer("✅ Канал для уведомлений отключен!", reply_markup=inline.admin_menu_kb())
        await state.clear()
        return
        
    if m.forward_from_chat and m.forward_from_chat.type == "channel":
        val = str(m.forward_from_chat.id)
    else:
        val = m.text.strip()
        
    await crud.set_setting("payment_channel_id", val)
    db_settings["payment_channel_id"] = val
    await m.answer("✅ Канал для уведомлений обновлен!", reply_markup=inline.admin_menu_kb())
    await state.clear()

# --- Support Reply ---
from ..states import SupportState

@router.callback_query(F.data.startswith("support_reply:"))
async def cb_support_reply(c: CallbackQuery, state: FSMContext):
    user_id = c.data.split(":")[1]
    await state.update_data(reply_to_user=user_id)
    await c.message.answer(f"Введите ответ для пользователя {user_id}:", reply_markup=inline.admin_back_kb())
    await state.set_state(SupportState.wait_for_reply)
    await c.answer()

@router.message(SupportState.wait_for_reply)
async def process_support_reply(m: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("reply_to_user")
    if user_id:
        try:
            await m.copy_to(int(user_id))
            await m.bot.send_message(int(user_id), "🎧 <b>Ответ от поддержки</b> ↑")
            await m.answer("✅ Ответ отправлен!", reply_markup=inline.admin_menu_kb())
        except Exception:
            await m.answer("❌ Не удалось отправить ответ.")
    await state.clear()

# --- Withdrawals Processing ---
@router.callback_query(F.data.startswith("adm:w_approve:"))
async def cb_w_approve(c: CallbackQuery):
    w_id = int(c.data.split(":")[2])
    w = await crud.get_withdrawal(w_id)
    if not w or w.status != "pending":
        return await c.answer("Уже обработано или не найдено", show_alert=True)
        
    await crud.update_withdrawal_status(w_id, "paid")
    await c.message.edit_text(c.message.text + "\n\n✅ <b>ВЫПЛАЧЕНО</b>")
    
    # Notify user
    try:
        await c.bot.send_message(w.user_id, f"💸 <b>Ваша заявка на вывод средств одобрена!</b>\nСумма {w.amount} ₽ успешно отправлена.")
    except Exception:
        pass

@router.callback_query(F.data.startswith("adm:w_reject:"))
async def cb_w_reject(c: CallbackQuery):
    w_id = int(c.data.split(":")[2])
    w = await crud.get_withdrawal(w_id)
    if not w or w.status != "pending":
        return await c.answer("Уже обработано или не найдено", show_alert=True)
        
    await crud.update_withdrawal_status(w_id, "rejected")
    # Return balance
    await crud.add_user_balance(w.user_id, w.amount)
    
    await c.message.edit_text(c.message.text + "\n\n❌ <b>ОТКАЗАНО</b> (средства возвращены на баланс)")
    
    # Notify user
    try:
        await c.bot.send_message(w.user_id, f"❌ <b>Отказ в выплате</b>\nВаша заявка на вывод {w.amount} ₽ была отклонена администратором. Средства возвращены на ваш баланс.")
    except Exception:
        pass
