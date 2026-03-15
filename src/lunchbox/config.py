from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://lunchbox:lunchbox@localhost:5432/lunchbox"
    secret_key: str = "dev-secret-key-change-in-production"
    base_url: str = "http://localhost:8000"

    google_client_id: str = ""
    google_client_secret: str = ""

    otel_exporter_otlp_endpoint: str = ""
    otel_exporter_otlp_headers: str = ""
    otel_service_name: str = "lunchbox"

    # Sync defaults
    days_to_fetch: int = 7
    skip_weekends: bool = True
    sync_hour: int = 6
    sync_minute: int = 0
    timezone: str = "America/Denver"

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
