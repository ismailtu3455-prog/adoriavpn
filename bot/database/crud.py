from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select, update, func, text, delete
from .models import Base, User, Invoice, Setting, Plan, Promocode, Admin
from ..config import settings
import datetime

engine = create_async_engine(f"sqlite+aiosqlite:///{settings.db_path}", echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN referrer_id BIGINT"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN test_taken BOOLEAN DEFAULT 0"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN active_promo VARCHAR"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN last_reminded_expiry BIGINT"))
            await conn.execute(text("ALTER TABLE users ADD COLUMN last_reminded_milestone INTEGER"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN balance FLOAT DEFAULT 0.0"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN referrer_type VARCHAR"))
        except Exception: pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN ref_bonus_invited INTEGER DEFAULT 0"))
        except Exception: pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN ref_bonus_days INTEGER DEFAULT 0"))
        except Exception: pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN ref_partner_invited INTEGER DEFAULT 0"))
        except Exception: pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN ref_partner_cash_total FLOAT DEFAULT 0.0"))
        except Exception: pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN ref_partner_cash_month FLOAT DEFAULT 0.0"))
        except Exception: pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN ref_partner_month_reset DATETIME DEFAULT '2000-01-01 00:00:00'"))
        except Exception: pass
        try:
            await conn.execute(text("ALTER TABLE invoices ADD COLUMN is_gift BOOLEAN DEFAULT 0"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN last_reissue DATETIME"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN tos_accepted BOOLEAN DEFAULT 0"))
        except Exception:
            pass
            
    # Default plans if empty
    async with AsyncSessionLocal() as session:
        count = await session.scalar(select(func.count(Plan.id)))
        if count == 0:
            default_plans = [
                Plan(id="7d", title="7 дней", days=7, price=50.0),
                Plan(id="1m", title="1 месяц", days=30, price=100.0),
                Plan(id="3m", title="3 месяца", days=90, price=250.0)
            ]
            session.add_all(default_plans)
            await session.commit()

async def register_user(user_id: int, username: str | None, first_name: str | None, last_name: str | None, referrer_id: int | None = None, referrer_type: str | None = None) -> bool:
    """Returns True if user was just created, False if already exists."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()
        
        is_new = False
        if not user:
            is_new = True
            user = User(user_id=user_id, username=username, first_name=first_name, last_name=last_name, referrer_id=referrer_id, referrer_type=referrer_type)
            session.add(user)
            
            if referrer_id and referrer_type:
                result_ref = await session.execute(select(User).where(User.user_id == referrer_id))
                ref_user = result_ref.scalar_one_or_none()
                if ref_user:
                    if referrer_type == "bonus":
                        ref_user.ref_bonus_invited += 1
                    elif referrer_type == "partner":
                        ref_user.ref_partner_invited += 1
        else:
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            user.last_seen = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            
        await session.commit()
        return is_new

async def delete_user(user_id: int):
    async with AsyncSessionLocal() as session:
        await session.execute(delete(User).where(User.user_id == user_id))
        await session.commit()

async def get_user(user_id: int) -> User | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.user_id == user_id))
        return result.scalar_one_or_none()

async def get_user_by_id_or_username(identifier: str) -> User | None:
    identifier = identifier.strip()
    if identifier.isdigit() or (identifier.startswith('-') and identifier[1:].isdigit()):
        return await get_user(int(identifier))
    else:
        username = identifier.lstrip("@").lower()
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(func.lower(User.username) == username))
            return result.scalar_one_or_none()

async def get_all_users() -> list[User]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User))
        return list(result.scalars().all())

async def get_setting(key: str) -> str | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Setting).where(Setting.key == key))
        setting = result.scalar_one_or_none()
        return setting.value if setting else None

async def set_setting(key: str, value: str | None):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Setting).where(Setting.key == key))
        setting = result.scalar_one_or_none()
        if not setting:
            if value is not None:
                session.add(Setting(key=key, value=value))
        else:
            if value is None:
                await session.delete(setting)
            else:
                setting.value = value
        await session.commit()

async def set_vpn_name(user_id: int, vpn_name: str | None):
    async with AsyncSessionLocal() as session:
        await session.execute(update(User).where(User.user_id == user_id).values(vpn_name=vpn_name))
        await session.commit()

async def create_invoice(invoice_id: str, user_id: int, plan: str, days: int, amount: float, asset: str, gateway: str, status: str = "active", is_gift: bool = False):
    async with AsyncSessionLocal() as session:
        invoice = Invoice(
            invoice_id=invoice_id,
            user_id=user_id,
            plan=plan,
            days=days,
            amount=amount,
            asset=asset,
            gateway=gateway,
            status=status,
            is_gift=is_gift
        )
        session.add(invoice)
        await session.commit()

async def get_invoice(invoice_id: str) -> Invoice | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Invoice).where(Invoice.invoice_id == invoice_id))
        return result.scalar_one_or_none()

async def update_invoice_status(invoice_id: str, status: str) -> Invoice | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Invoice).where(Invoice.invoice_id == invoice_id))
        invoice = result.scalar_one_or_none()
        if invoice:
            invoice.status = status
            if status == "paid":
                invoice.paid_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            elif status == "canceled":
                invoice.canceled_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            await session.commit()
            return invoice
        return None

async def get_active_invoices(gateway: str | None = None) -> list[Invoice]:
    async with AsyncSessionLocal() as session:
        stmt = select(Invoice).where(Invoice.status == "active")
        if gateway:
            stmt = stmt.where(Invoice.gateway == gateway)
        result = await session.execute(stmt)
        return list(result.scalars().all())

async def get_active_invoices_filtered(sort_mode: str = "time_desc", search_user_id: int | None = None) -> list[Invoice]:
    async with AsyncSessionLocal() as session:
        stmt = select(Invoice).where(Invoice.status == "active")
        if search_user_id:
            stmt = stmt.where(Invoice.user_id == search_user_id)
            
        if sort_mode == "time_desc":
            stmt = stmt.order_by(Invoice.created_at.desc())
        elif sort_mode == "time_asc":
            stmt = stmt.order_by(Invoice.created_at.asc())
        elif sort_mode == "price_desc":
            stmt = stmt.order_by(Invoice.amount.desc())
        elif sort_mode == "price_asc":
            stmt = stmt.order_by(Invoice.amount.asc())
            
        result = await session.execute(stmt)
        return list(result.scalars().all())

async def get_dashboard_stats() -> dict:
    async with AsyncSessionLocal() as session:
        users_count = await session.scalar(select(func.count(User.user_id)))
        users_vpn = await session.scalar(select(func.count(User.user_id)).where(User.vpn_name.is_not(None)))
        
        inv_total = await session.scalar(select(func.count(Invoice.invoice_id)))
        inv_paid = await session.scalar(select(func.count(Invoice.invoice_id)).where(Invoice.status == 'paid'))
        inv_active = await session.scalar(select(func.count(Invoice.invoice_id)).where(Invoice.status == 'active'))
        
        return {
            "users": {"total": users_count, "with_vpn": users_vpn},
            "invoices": {"total": inv_total, "paid": inv_paid, "active": inv_active}
        }

async def get_referrals_count(user_id: int) -> int:
    async with AsyncSessionLocal() as session:
        return await session.scalar(select(func.count(User.user_id)).where(User.referrer_id == user_id)) or 0

async def get_paid_invoices_count(user_id: int) -> int:
    async with AsyncSessionLocal() as session:
        return await session.scalar(select(func.count(Invoice.invoice_id)).where(Invoice.user_id == user_id, Invoice.status == "paid")) or 0

# --- Admin Management ---
async def get_admins() -> list[int]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Admin.user_id))
        return list(result.scalars().all())

async def add_admin(user_id: int):
    async with AsyncSessionLocal() as session:
        if not await session.scalar(select(Admin).where(Admin.user_id == user_id)):
            session.add(Admin(user_id=user_id))
            await session.commit()

async def remove_admin(user_id: int):
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Admin).where(Admin.user_id == user_id))
        await session.commit()

# --- Plans Management ---
async def get_all_plans() -> list[Plan]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Plan).order_by(Plan.days))
        return list(result.scalars().all())

async def get_plan(plan_id: str) -> Plan | None:
    async with AsyncSessionLocal() as session:
        return await session.scalar(select(Plan).where(Plan.id == plan_id))

async def create_plan(plan_id: str, title: str, days: int, price: float):
    async with AsyncSessionLocal() as session:
        session.add(Plan(id=plan_id, title=title, days=days, price=price))
        await session.commit()

async def delete_plan(plan_id: str):
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Plan).where(Plan.id == plan_id))
        await session.commit()

# --- Promo Management ---
async def get_promocode(code: str) -> Promocode | None:
    async with AsyncSessionLocal() as session:
        return await session.scalar(select(Promocode).where(Promocode.code == code))

async def create_promocode(code: str, promo_type: str, value: float, max_uses: int):
    async with AsyncSessionLocal() as session:
        session.add(Promocode(code=code, promo_type=promo_type, value=value, max_uses=max_uses))
        await session.commit()

async def increment_promo_uses(code: str):
    async with AsyncSessionLocal() as session:
        promo = await session.scalar(select(Promocode).where(Promocode.code == code))
        if promo:
            promo.current_uses += 1
            await session.commit()

async def get_all_promocodes() -> list[Promocode]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Promocode))
        return list(result.scalars().all())

async def delete_promocode(code: str):
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Promocode).where(Promocode.code == code))
        await session.commit()

async def update_user_promo(user_id: int, code: str | None):
    async with AsyncSessionLocal() as session:
        await session.execute(update(User).where(User.user_id == user_id).values(active_promo=code))
        await session.commit()

async def update_user_test_taken(user_id: int, taken: bool = True):
    async with AsyncSessionLocal() as session:
        await session.execute(update(User).where(User.user_id == user_id).values(test_taken=taken))
        await session.commit()

async def update_user_reminders(user_id: int, expiry: int, milestone: int):
    async with AsyncSessionLocal() as session:
        await session.execute(update(User).where(User.user_id == user_id).values(last_reminded_expiry=expiry, last_reminded_milestone=milestone))
        await session.commit()

async def update_user_tos_accepted(user_id: int, accepted: bool = True):
    async with AsyncSessionLocal() as session:
        await session.execute(update(User).where(User.user_id == user_id).values(tos_accepted=accepted))
        await session.commit()

async def add_user_balance(user_id: int, amount: float):
    async with AsyncSessionLocal() as session:
        await session.execute(update(User).where(User.user_id == user_id).values(balance=User.balance + amount))
        await session.commit()

async def process_referral_bonus(bot, buyer_id: int, amount: float):
    buyer = await get_user(buyer_id)
    if not buyer or not buyer.referrer_id or buyer.referrer_type != "partner":
        return
        
    lvl1_id = buyer.referrer_id
    
    async with AsyncSessionLocal() as session:
        result1 = await session.execute(select(User).where(User.user_id == lvl1_id))
        lvl1_user = result1.scalar_one_or_none()
        if not lvl1_user:
            return
            
        from ..config import db_settings
        p1 = float(db_settings.get("ref_percent_lvl1", "10"))
        p2 = float(db_settings.get("ref_percent_lvl2", "5"))
        
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        
        if p1 > 0:
            bonus1 = round(amount * (p1 / 100.0), 2)
            lvl1_user.balance += bonus1
            
            if lvl1_user.ref_partner_month_reset.month != now.month or lvl1_user.ref_partner_month_reset.year != now.year:
                lvl1_user.ref_partner_cash_month = 0.0
                lvl1_user.ref_partner_month_reset = now
                
            lvl1_user.ref_partner_cash_total += bonus1
            lvl1_user.ref_partner_cash_month += bonus1
            
            try:
                await bot.send_message(lvl1_id, f"💸 <b>Партнёрский бонус!</b>\nВаш приглашенный приобрел подписку.\nНачислено: {bonus1} ₽")
            except Exception:
                pass
                
        if lvl1_user.referrer_id and lvl1_user.referrer_type == "partner" and p2 > 0:
            lvl2_id = lvl1_user.referrer_id
            result2 = await session.execute(select(User).where(User.user_id == lvl2_id))
            lvl2_user = result2.scalar_one_or_none()
            if lvl2_user:
                bonus2 = round(amount * (p2 / 100.0), 2)
                lvl2_user.balance += bonus2
                
                if lvl2_user.ref_partner_month_reset.month != now.month or lvl2_user.ref_partner_month_reset.year != now.year:
                    lvl2_user.ref_partner_cash_month = 0.0
                    lvl2_user.ref_partner_month_reset = now
                    
                lvl2_user.ref_partner_cash_total += bonus2
                lvl2_user.ref_partner_cash_month += bonus2
                
                try:
                    await bot.send_message(lvl2_id, f"💸 <b>Партнёрский бонус!</b>\nВаш реферал 2-го уровня приобрел подписку.\nНачислено: {bonus2} ₽")
                except Exception:
                    pass
                    
        await session.commit()

async def add_bonus_days_stat(user_id: int, days: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()
        if user:
            user.ref_bonus_days += days
            await session.commit()

async def create_withdrawal(user_id: int, amount: float, details: str) -> int:
    from .models import WithdrawalRequest
    async with AsyncSessionLocal() as session:
        w = WithdrawalRequest(user_id=user_id, amount=amount, details=details)
        session.add(w)
        await session.commit()
        return w.id

async def update_withdrawal_status(w_id: int, status: str):
    from .models import WithdrawalRequest
    async with AsyncSessionLocal() as session:
        await session.execute(update(WithdrawalRequest).where(WithdrawalRequest.id == w_id).values(status=status))
        await session.commit()

async def get_withdrawal(w_id: int):
    from .models import WithdrawalRequest
    async with AsyncSessionLocal() as session:
        return await session.scalar(select(WithdrawalRequest).where(WithdrawalRequest.id == w_id))

async def create_gift_card(code: str, days: int):
    from .models import GiftCard
    async with AsyncSessionLocal() as session:
        session.add(GiftCard(code=code, days=days))
        await session.commit()

async def use_gift_card(code: str) -> int | None:
    from .models import GiftCard
    async with AsyncSessionLocal() as session:
        card = await session.scalar(select(GiftCard).where(GiftCard.code == code, GiftCard.is_used == False))
        if card:
            card.is_used = True
            await session.commit()
            return card.days
        return None
