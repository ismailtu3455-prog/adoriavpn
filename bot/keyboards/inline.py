from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from ..config import settings, db_settings
from ..texts import texts

def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💳 Купить", callback_data="buy"))
    builder.row(InlineKeyboardButton(text="🎁 Взять тестовый период", callback_data="take_test"))
    builder.row(
        InlineKeyboardButton(text="👤 Профиль", callback_data="my"),
        InlineKeyboardButton(text="👥 Рефералы", callback_data="referrals")
    )
    builder.row(
        InlineKeyboardButton(text="🎧 Поддержка", callback_data="support"),
        InlineKeyboardButton(text="📖 Инструкция", callback_data="help")
    )
    if is_admin:
        builder.row(InlineKeyboardButton(text="⚙️ Админка", callback_data="adm:home"))
    return builder.as_markup()

def back_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Назад", callback_data="back"))
    return builder.as_markup()

def plans_kb(plans: list, has_promo: bool = False, prefix: str = "plan") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for p in plans:
        builder.row(InlineKeyboardButton(text=f"{p.title} - {p.price} ₽", callback_data=f"{prefix}:{p.id}"))
        
    if not has_promo:
        builder.row(InlineKeyboardButton(text="🎟 Ввести промокод", callback_data="enter_promo"))
        
    if prefix == "plan":
        builder.row(InlineKeyboardButton(text="🎁 Купить в подарок", callback_data="buy_gift"))
    else:
        builder.row(InlineKeyboardButton(text="💳 Купить себе", callback_data="buy"))
        
    builder.row(InlineKeyboardButton(text="Назад", callback_data="back"))
    return builder.as_markup()

def payment_methods_kb(plan: str, balance: float = 0, price: float = 0, is_gift: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    prefix = "giftpay" if is_gift else "pay"
    if db_settings.get("balance_pay_enabled", "1") == "1":
        if balance >= price and price > 0:
            builder.row(InlineKeyboardButton(text="💳 Оплатить с баланса", callback_data=f"{prefix}:{plan}:balance"))
    if db_settings.get("crypto_pay_token"):
        builder.row(InlineKeyboardButton(text=f"CryptoBot", callback_data=f"{prefix}:{plan}:cryptopay"))
    
    if settings.stars_rate:
        builder.row(InlineKeyboardButton(text=f"Telegram Stars", callback_data=f"{prefix}:{plan}:stars"))
    
    tome_token = db_settings.get("tome_token")
    if tome_token and tome_token.strip():
        builder.row(InlineKeyboardButton(text=f"СБП / Карта (РФ)", callback_data=f"{prefix}:{plan}:tome"))
        
    builder.row(InlineKeyboardButton(text="Отмена", callback_data="buy"))
    return builder.as_markup()

def invoice_kb(pay_url: str, invoice_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Оплатить", url=pay_url))
    builder.row(InlineKeyboardButton(text="Я оплатил", callback_data=f"check:{invoice_id}"))
    builder.row(InlineKeyboardButton(text="Отменить", callback_data=f"cancel:{invoice_id}"))
    return builder.as_markup()

def client_kb(balance: float = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Продлить", callback_data="buy"))
    builder.row(InlineKeyboardButton(text="🎁 Купить в подарок", callback_data="buy_gift"))
    if balance > 0:
        builder.row(InlineKeyboardButton(text="💸 Вывод средств", callback_data="withdraw"))
    builder.row(InlineKeyboardButton(text="Инструкция", callback_data="help"))
    builder.row(InlineKeyboardButton(text="В меню", callback_data="back"))
    return builder.as_markup()

def no_client_kb(balance: float = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💳 Купить VPN", callback_data="buy"))
    builder.row(InlineKeyboardButton(text="🎁 Купить в подарок", callback_data="buy_gift"))
    if balance > 0:
        builder.row(InlineKeyboardButton(text="💸 Вывод средств", callback_data="withdraw"))
    builder.row(InlineKeyboardButton(text="Назад", callback_data="back"))
    return builder.as_markup()

def admin_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📊 Статистика", callback_data="adm:stats"))
    builder.row(InlineKeyboardButton(text="⚙️ Управление", callback_data="adm:manage"))
    builder.row(InlineKeyboardButton(text="💳 Системы оплат", callback_data="adm:payments"))
    builder.row(InlineKeyboardButton(text="В меню бота", callback_data="back"))
    return builder.as_markup()

def admin_manage_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔍 Поиск юзера", callback_data="adm:find_user"),
                InlineKeyboardButton(text="🎁 Выдать VPN", callback_data="adm:grant_vpn"))
    builder.row(InlineKeyboardButton(text="💳 Одобрить счет", callback_data="adm:payinvoice"),
                InlineKeyboardButton(text="📢 Рассылка", callback_data="adm:broadcast"))
    
    builder.row(InlineKeyboardButton(text="⚙️ Рефералы", callback_data="adm:ref_setup"),
                InlineKeyboardButton(text="⚙️ Тест и Лимиты", callback_data="adm:test_setup"))
                
    builder.row(InlineKeyboardButton(text="🎁 Создать Gift Card", callback_data="adm:gift_create"))
                
    builder.row(InlineKeyboardButton(text="👥 Админы", callback_data="adm:admins"),
                InlineKeyboardButton(text="📋 Тарифы", callback_data="adm:plans"),
                InlineKeyboardButton(text="🎟 Промо", callback_data="adm:promos"))
    
    builder.row(InlineKeyboardButton(text="🔔 Канал уведомлений", callback_data="adm:paychannel"))
    builder.row(InlineKeyboardButton(text="Назад", callback_data="adm:home"))
    return builder.as_markup()

def admin_list_kb(admins: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for a in admins:
        builder.row(InlineKeyboardButton(text=f"Удалить {a}", callback_data=f"adm:del_admin:{a}"))
    builder.row(InlineKeyboardButton(text="➕ Добавить админа", callback_data="adm:add_admin"))
    builder.row(InlineKeyboardButton(text="Назад", callback_data="adm:manage"))
    return builder.as_markup()

def plans_list_kb(plans: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for p in plans:
        builder.row(InlineKeyboardButton(text=f"Удалить: {p.title}", callback_data=f"adm:del_plan:{p.id}"))
    builder.row(InlineKeyboardButton(text="➕ Добавить тариф", callback_data="adm:add_plan"))
    builder.row(InlineKeyboardButton(text="Назад", callback_data="adm:manage"))
    return builder.as_markup()

def promos_list_kb(promos: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for p in promos:
        builder.row(InlineKeyboardButton(text=f"Удалить: {p.code}", callback_data=f"adm:del_promo:{p.code}"))
    builder.row(InlineKeyboardButton(text="➕ Добавить промокод", callback_data="adm:add_promo"))
    builder.row(InlineKeyboardButton(text="Назад", callback_data="adm:manage"))
    return builder.as_markup()

def admin_test_setup_kb(db_settings: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    d = db_settings.get("test_days", "1")
    enabled = "ВКЛ" if db_settings.get("test_enabled") == "1" else "ВЫКЛ"
    l = db_settings.get("default_limit_gb", "0")
    
    builder.row(InlineKeyboardButton(text=f"Тест: {enabled}", callback_data="adm:toggle_test"))
    builder.row(InlineKeyboardButton(text=f"Дней теста: {d}", callback_data="adm:set_test_days"))
    builder.row(InlineKeyboardButton(text=f"Лимит трафика: {l} ГБ", callback_data="adm:set_limit"))
    builder.row(InlineKeyboardButton(text="Назад", callback_data="adm:manage"))
    return builder.as_markup()

def promo_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💰 Скидка (%)", callback_data="adm:promo_type:discount"))
    builder.row(InlineKeyboardButton(text="🎁 Бесплатные дни", callback_data="adm:promo_type:days"))
    return builder.as_markup()

def admin_ref_setup_kb(db_settings: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    s = db_settings.get("ref_reward_start", "3")
    l1 = db_settings.get("ref_percent_lvl1", "10")
    l2 = db_settings.get("ref_percent_lvl2", "5")
    
    builder.row(InlineKeyboardButton(text=f"🎁 За старт: {s} дн.", callback_data="adm:set_ref_start"))
    builder.row(InlineKeyboardButton(text=f"💸 Кэшбэк 1 ур: {l1}%", callback_data="adm:set_ref_lvl1"))
    builder.row(InlineKeyboardButton(text=f"💸 Кэшбэк 2 ур: {l2}%", callback_data="adm:set_ref_lvl2"))
    builder.row(InlineKeyboardButton(text="Назад", callback_data="adm:manage"))
    return builder.as_markup()

def back_to_buy_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardBuilder().row(InlineKeyboardButton(text="Отмена", callback_data="buy")).as_markup()

def admin_payments_kb(db_settings: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    crypto_status = "✅" if db_settings.get("crypto_pay_token") else "❌"
    stars_status = "✅" if db_settings.get("stars_enabled") == "1" else "❌"
    tome_status = "✅" if db_settings.get("tome_shop_id") else "❌"
    balance_status = "✅" if db_settings.get("balance_pay_enabled", "1") == "1" else "❌"
    
    builder.row(InlineKeyboardButton(text=f"Оплата с баланса {balance_status}", callback_data="adm:pay_setup:balance"))
    builder.row(InlineKeyboardButton(text=f"CryptoBot {crypto_status}", callback_data="adm:pay_setup:crypto"))
    builder.row(InlineKeyboardButton(text=f"Telegram Stars {stars_status}", callback_data="adm:pay_setup:stars"))
    builder.row(InlineKeyboardButton(text=f"СБП / tome.ge {tome_status}", callback_data="adm:pay_setup:tome"))
    builder.row(InlineKeyboardButton(text="Назад", callback_data="adm:home"))
    return builder.as_markup()

def admin_back_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Назад в админку", callback_data="adm:home"))
    return builder.as_markup()

def user_manage_kb(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💰 Выдать баланс", callback_data=f"adm:add_balance:{user_id}"))
    builder.row(InlineKeyboardButton(text="🗑 Удалить из БД (для тестов)", callback_data=f"adm:del_user:{user_id}"))
    builder.row(InlineKeyboardButton(text="Назад", callback_data="adm:manage"))
    return builder.as_markup()

def withdrawal_decision_kb(w_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Выплачено", callback_data=f"adm:w_approve:{w_id}"))
    builder.row(InlineKeyboardButton(text="❌ Отказ", callback_data=f"adm:w_reject:{w_id}"))
    return builder.as_markup()

def share_gift_kb(gift_code: str, days: int, bot_username: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    gift_link = f"https://t.me/{bot_username}?start={gift_code}"
    
    text = (
        f"🎁 Премиум VPN уже доступен для тебя\n\n"
        f"На {days} дней — бесплатно.\n\n"
        f"🔥 Что внутри:\n"
        f"• Без блокировок и ограничений\n"
        f"• Стабильный быстрый канал\n"
        f"• Полная защита трафика\n\n"
        f"👉 Забрать доступ:"
    )
    import urllib.parse
    encoded_text = urllib.parse.quote(text)
    builder.row(InlineKeyboardButton(text="Отправить 🎁", url=f"https://t.me/share/url?url={gift_link}&text={encoded_text}"))
    builder.row(InlineKeyboardButton(text="В меню", callback_data="back"))
    return builder.as_markup()

def invoices_list_kb(invoices: list, page: int, sort_mode: str, has_search: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    start = page * 5
    end = start + 5
    page_items = invoices[start:end]
    
    for inv in page_items:
        text = f"Одобрить {inv.amount} {inv.asset} ({inv.user_id})"
        builder.row(InlineKeyboardButton(text=text, callback_data=f"adm:inv:approve:{inv.invoice_id}"))
        
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"adm:inv:page:{page-1}"))
    if end < len(invoices):
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"adm:inv:page:{page+1}"))
        
    if nav_row:
        builder.row(*nav_row)
        
    sort_text = {
        "time_desc": "Сначала новые",
        "time_asc": "Сначала старые",
        "price_desc": "Сначала дорогие",
        "price_asc": "Сначала дешевые"
    }.get(sort_mode, "Сортировка")
    
    builder.row(InlineKeyboardButton(text=f"🔄 Фильтр: {sort_text}", callback_data="adm:inv:sort"))
    
    if has_search:
        builder.row(InlineKeyboardButton(text="❌ Сбросить поиск", callback_data="adm:inv:clear_search"))
    else:
        builder.row(InlineKeyboardButton(text="🔍 Поиск по юзеру", callback_data="adm:inv:search"))
        
    builder.row(InlineKeyboardButton(text="Назад", callback_data="adm:manage"))
    return builder.as_markup()

def admin_channel_setup_kb(bot_username: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить бота в канал", url=f"https://t.me/{bot_username}?startchannel=true&admin=post_messages"))
    builder.row(InlineKeyboardButton(text="Назад", callback_data="adm:manage"))
    return builder.as_markup()
