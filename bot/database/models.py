import datetime
from sqlalchemy import BigInteger, String, Float, DateTime, func, ForeignKey, Boolean, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncAttrs

class Base(AsyncAttrs, DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    first_name: Mapped[str | None] = mapped_column(String, nullable=True)
    last_name: Mapped[str | None] = mapped_column(String, nullable=True)
    vpn_name: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    referrer_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    referrer_type: Mapped[str | None] = mapped_column(String, nullable=True) # "bonus" or "partner"
    
    ref_bonus_invited: Mapped[int] = mapped_column(Integer, default=0)
    ref_bonus_days: Mapped[int] = mapped_column(Integer, default=0)
    
    ref_partner_invited: Mapped[int] = mapped_column(Integer, default=0)
    ref_partner_cash_total: Mapped[float] = mapped_column(Float, default=0.0)
    ref_partner_cash_month: Mapped[float] = mapped_column(Float, default=0.0)
    ref_partner_month_reset: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    
    test_taken: Mapped[bool] = mapped_column(Boolean, default=False)
    active_promo: Mapped[str | None] = mapped_column(String, nullable=True)
    
    last_reminded_expiry: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_reminded_milestone: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    last_reissue: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    tos_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str | None] = mapped_column(String, nullable=True)

class Invoice(Base):
    __tablename__ = "invoices"

    invoice_id: Mapped[str] = mapped_column(String, primary_key=True) # UUID or numeric ID from gateways
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    plan: Mapped[str] = mapped_column(String, nullable=False)
    days: Mapped[int] = mapped_column(nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    asset: Mapped[str] = mapped_column(String, nullable=False)
    gateway: Mapped[str] = mapped_column(String, nullable=False) # 'cryptopay', 'h1stars', 'yookassa'
    is_gift: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String, default="active") # active, paid, canceled
    
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    paid_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    canceled_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="invoices")

class Admin(Base):
    __tablename__ = "admins"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

class Plan(Base):
    __tablename__ = "plans"
    id: Mapped[str] = mapped_column(String, primary_key=True) # e.g. "7d", "1m"
    title: Mapped[str] = mapped_column(String, nullable=False)
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)

class Promocode(Base):
    __tablename__ = "promocodes"
    code: Mapped[str] = mapped_column(String, primary_key=True)
    promo_type: Mapped[str] = mapped_column(String, nullable=False) # "discount", "days"
    value: Mapped[float] = mapped_column(Float, nullable=False)
    max_uses: Mapped[int] = mapped_column(Integer, default=0) # 0 = unlimited
    current_uses: Mapped[int] = mapped_column(Integer, default=0)

class WithdrawalRequest(Base):
    __tablename__ = "withdrawals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    details: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending") # pending, paid, rejected
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

class GiftCard(Base):
    __tablename__ = "giftcards"
    code: Mapped[str] = mapped_column(String, primary_key=True)
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
