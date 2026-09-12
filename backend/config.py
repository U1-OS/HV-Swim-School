from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


if os.getenv("HV_LOAD_DOTENV", "true").lower() == "true":
    load_dotenv(ROOT / ".env")

DATA_DIR = Path(os.getenv("HV_DATA_DIR", str(ROOT / "data"))).expanduser().resolve()
DB_PATH = DATA_DIR / "hv_swim.db"


def integer_env(name: str, default: int, *, minimum: int, maximum: int) -> int:
    """Read an integer setting without making the whole application fail at import."""
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def resolved_app_environment() -> str:
    """Accept the old variable safely, but make conflicting deployment config fatal."""
    current = os.getenv("HV_APP_ENV")
    legacy = os.getenv("HV_ENVIRONMENT")
    if current and legacy and current.lower() != legacy.lower():
        raise RuntimeError("HV_APP_ENV and legacy HV_ENVIRONMENT disagree")
    return current or legacy or "development"


@dataclass(frozen=True)
class Settings:
    app_env: str = resolved_app_environment()
    # Only the existing SQLite storage adapter is implemented. A cloud DATABASE_URL
    # must not be silently ignored and leave private records on an unintended disk.
    database_url: str = os.getenv("HV_DATABASE_URL", os.getenv("DATABASE_URL", "")).strip()
    session_secret: str = os.getenv("HV_SESSION_SECRET", "local-demo-secret-change-before-production")
    data_encryption_key: str = os.getenv("HV_DATA_ENCRYPTION_KEY", "")
    public_url: str = os.getenv("HV_PUBLIC_URL", "http://localhost:8765").rstrip("/")
    bootstrap_admin_email: str = os.getenv("HV_BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    bootstrap_admin_password: str = os.getenv("HV_BOOTSTRAP_ADMIN_PASSWORD", "")
    bootstrap_admin_name: str = os.getenv("HV_BOOTSTRAP_ADMIN_NAME", "HV Swim Admin").strip()
    xero_client_id: str = os.getenv("XERO_CLIENT_ID", "")
    xero_client_secret: str = os.getenv("XERO_CLIENT_SECRET", "")
    xero_redirect_uri: str = os.getenv("XERO_REDIRECT_URI", "http://localhost:8765/api/integrations/xero/callback")
    xero_sync_enabled: bool = os.getenv("XERO_SYNC_ENABLED", "false").lower() == "true"
    xero_earnings_rate_id: str = os.getenv("XERO_EARNINGS_RATE_ID", "")
    xero_lesson_account_code: str = os.getenv("XERO_LESSON_ACCOUNT_CODE", "").strip()
    xero_lesson_tax_type: str = os.getenv("XERO_LESSON_TAX_TYPE", "").strip()
    xero_line_amount_type: str = os.getenv("XERO_LINE_AMOUNT_TYPE", "").strip()
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    google_redirect_uri: str = os.getenv("GOOGLE_REDIRECT_URI", "").strip()
    apple_client_id: str = os.getenv("APPLE_CLIENT_ID", "").strip()
    apple_client_secret: str = os.getenv("APPLE_CLIENT_SECRET", "").strip()
    apple_redirect_uri: str = os.getenv("APPLE_REDIRECT_URI", "").strip()
    shopify_store_domain: str = os.getenv("SHOPIFY_STORE_DOMAIN", "").replace("https://", "").rstrip("/")
    shopify_storefront_token: str = os.getenv("SHOPIFY_STOREFRONT_TOKEN", "")
    shopify_api_version: str = os.getenv("SHOPIFY_API_VERSION", "2026-04")
    shopify_cache_seconds: int = integer_env("SHOPIFY_CACHE_SECONDS", 300, minimum=60, maximum=1800)
    printify_api_token: str = os.getenv("PRINTIFY_API_TOKEN", "")
    printify_shop_id: str = os.getenv("PRINTIFY_SHOP_ID", "")
    pool_sensor_url: str = os.getenv("POOL_SENSOR_URL", "")
    pool_sensor_token: str = os.getenv("POOL_SENSOR_TOKEN", "")
    weather_api_key: str = os.getenv("OPEN_METEO_API_KEY", "")
    weather_cache_seconds: int = integer_env("WEATHER_CACHE_SECONDS", 600, minimum=60, maximum=3600)
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
