import aiohttp
from ..config import db_settings
import logging

log = logging.getLogger(__name__)

async def create_tome_invoice(amount: float, description: str) -> tuple[str, str] | None:
    # 4% commission
    amount = round(amount * 1.04, 2)
    
    shop_id = db_settings.get("tome_shop_id")
    secret_key = db_settings.get("tome_secret_key")
    if not shop_id or not secret_key:
        return None
        
    try:
        # TODO: Implement actual tome.ge API call when docs are available.
        # This is a dummy implementation to avoid crashing and simulate invoice creation.
        # It just returns a dummy pay_url.
        invoice_id = "tome_dummy_id"
        pay_url = "https://tome.ge/"
        
        # log.warning(f"Tome.ge API is a stub. Invoice created for {amount} RUB")
        
        return invoice_id, pay_url
    except Exception as e:
        log.error(f"Tome create error: {e}")
        return None

async def get_tome_invoice_status(invoice_id: str) -> str:
    # TODO: Implement actual check
    return "active"
