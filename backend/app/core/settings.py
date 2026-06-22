from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://agentworks:agentworks_dev@localhost:5432/agentworks"
    redis_url: str = "redis://localhost:6379/0"

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    deepseek_api_key: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/oauth/google/callback"

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    auth_disabled_for_tests: bool = False

    voyage_api_key: str = ""
    stripe_secret_key: str = ""

    agent_secret_key: str = ""

    default_model: str = "deepseek-chat"
    default_max_tokens_per_run: int = 50_000

    media_root: str = "/app/media"
    ollama_url: str = "http://172.17.0.1:11434"
    ollama_model: str = "qwen2.5:3b"

    # Öffentliche Basis-URL für Links in Benachrichtigungen.
    public_base_url: str = "http://localhost:3000"

    # Interne SearXNG-Instanz für die Web-Suche der Agenten (kein Public, kein Key).
    searxng_url: str = "http://searxng:8080"

    # Zeitzone für vom Agenten geplante Aufgaben ("um 8" o.ä.) bis es ein Nutzer-TZ-Feld gibt.
    default_timezone: str = "Europe/Berlin"

    # E-Mail-Versand (Gmail-SMTP o.ä.). Leere Werte → E-Mail-Kanal wird übersprungen.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = ""

    # Telegram-Bot. Leerer Token → Telegram-Kanal + Poller deaktiviert.
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""

    # Billing
    # Optionaler Konfig-Fallback für den Systemadmin (per E-Mail). Standard leer:
    # der Systemadmin ist der ERSTE installierende Nutzer (User.is_system_admin).
    admin_email: str = ""
    pricing_source_url: str = ""  # JSON-Quelle für "Preise abrufen" (leer => nur manuell)


@lru_cache
def get_settings() -> Settings:
    return Settings()
