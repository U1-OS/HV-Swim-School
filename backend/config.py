from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "hv_swim.db"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("HV_APP_ENV", "development")
    session_secret: str = os.getenv("HV_SESSION_SECRET", "local-demo-secret-change-before-production")
    public_url: str = os.getenv("HV_PUBLIC_URL", "http://localhost:8765").rstrip("/")
    xero_client_id: str = os.getenv("XERO_CLIENT_ID", "")
    xero_client_secret: str = os.getenv("XERO_CLIENT_SECRET", "")
    xero_redirect_uri: str = os.getenv("XERO_REDIRECT_URI", "http://localhost:8765/api/integrations/xero/callback")
    xero_sync_enabled: bool = os.getenv("XERO_SYNC_ENABLED", "false").lower() == "true"
    xero_earnings_rate_id: str = os.getenv("XERO_EARNINGS_RATE_ID", "")
    shopify_store_domain: str = os.getenv("SHOPIFY_STORE_DOMAIN", "").replace("https://", "").rstrip("/")
    shopify_storefront_token: str = os.getenv("SHOPIFY_STOREFRONT_TOKEN", "")
    shopify_api_version: str = os.getenv("SHOPIFY_API_VERSION", "2026-04")
    printify_api_token: str = os.getenv("PRINTIFY_API_TOKEN", "")
    printify_shop_id: str = os.getenv("PRINTIFY_SHOP_ID", "")
    pool_sensor_url: str = os.getenv("POOL_SENSOR_URL", "")
    pool_sensor_token: str = os.getenv("POOL_SENSOR_TOKEN", "")
    email_provider: str = os.getenv("EMAIL_PROVIDER", "")
    email_api_key: str = os.getenv("EMAIL_API_KEY", "")
    sms_provider: str = os.getenv("SMS_PROVIDER", "")
    sms_api_key: str = os.getenv("SMS_API_KEY", "")
    web_push_public_key: str = os.getenv("WEB_PUSH_PUBLIC_KEY", "")
    web_push_private_key: str = os.getenv("WEB_PUSH_PRIVATE_KEY", "")

    @property
    def production(self) -> bool:
        return self.app_env.lower() == "production"


settings = Settings()
DATA_DIR.mkdir(parents=True, exist_ok=True)
