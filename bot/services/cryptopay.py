from aiocryptopay import AioCryptoPay, Networks
from ..config import db_settings

_crypto = None
_crypto_token = None

def get_crypto() -> AioCryptoPay | None:
    global _crypto, _crypto_token
    current_token = db_settings.get("crypto_pay_token")
    if not current_token:
        return None
    
    if _crypto is None or _crypto_token != current_token:
        _crypto = AioCryptoPay(
            token=current_token,
            network=Networks.MAIN_NET,
        )
        _crypto_token = current_token
    return _crypto

async def create_crypto_invoice(amount: float, description: str, payload: str) -> tuple[str, str] | None:
    """Returns (invoice_id, pay_url)"""
    try:
        crypto = get_crypto()
        if not crypto:
            return None
        invoice = await crypto.create_invoice(
            currency_type="fiat",
            fiat="USD",
            amount=round(amount * 0.0125, 2),
            description=description,
            payload=payload,
            expires_in=1800,
        )
        return str(invoice.invoice_id), invoice.bot_invoice_url
    except Exception as e:
        import logging
        logging.error(f"CryptoPay create error: {e}")
        return None

async def get_crypto_invoice_status(invoice_id: str) -> str:
    """Returns status of invoice: active, paid, expired"""
    try:
        crypto = get_crypto()
        if not crypto:
            return "active"
        invoices = await crypto.get_invoices(invoice_ids=[int(invoice_id)])
        if not invoices:
            return "active"
        inv = invoices[0] if isinstance(invoices, list) else invoices
        return inv.status
    except Exception:
        return "active"
