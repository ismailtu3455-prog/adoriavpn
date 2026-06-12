from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    bot_token: str
    admin_ids: str = ""

    @property
    def get_admin_ids(self) -> set[int]:
        return {int(x) for x in self.admin_ids.replace(" ", "").split(",") if x}

    db_path: str = "bot.db"

    vpn_api_url: str
    vpn_api_token: str

    price_7d: float = 50.0
    price_1m: float = 100.0
    price_3m: float = 250.0

    crypto_currency: str = "USDT"

    stars_rate: float = 1.35 # 1 XTR = ~1.35 RUB

    # Old static config variables removed in favor of db_settings
    # crypto_pay_token, yookassa_shop_id, yookassa_secret_key

    proxy_url: str | None = None  # Например: http://user:pass@ip:port

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()

# Dynamic settings from DB
db_settings = {
    "crypto_pay_token": None,
    "stars_enabled": "0",
    "tome_shop_id": None,
    "tome_secret_key": None,
    "ref_reward_start": "3",
    "ref_percent_lvl1": "10",
    "ref_percent_lvl2": "5"
}
