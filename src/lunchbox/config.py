from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://lunchbox:lunchbox@localhost:5432/lunchbox"
    secret_key: str
    base_url: str = "http://localhost:8000"

    google_client_id: str = ""
    google_client_secret: str = ""

    otel_exporter_otlp_endpoint: str = ""
    otel_exporter_otlp_headers: str = ""
    otel_service_name: str = "lunchbox"

    # Sync defaults
    days_to_fetch: int = 7
    skip_weekends: bool = True

    # Vercel Cron auth
    cron_secret: str = ""

    # Guardrails
    max_syncs_per_day: int = 10
    max_subscriptions_per_user: int = 5
    max_subscriptions_global: int = 20
    max_menu_items: int = 50000

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
