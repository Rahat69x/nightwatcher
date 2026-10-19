"""NightWatcher — Central configuration loaded from .env"""
from __future__ import annotations
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8",
        case_sensitive=False, extra="ignore",
    )

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    secret_key: str = "change_me_in_production"
    debug: bool = True
    base_url: str = "http://localhost:8000"

    # Database
    database_url: str = "sqlite+aiosqlite:///./nightwatcher.db"

    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    alert_from_email: str = ""
    alert_to_emails: str = ""

    @property
    def alert_to_email_list(self) -> List[str]:
        return [e.strip() for e in self.alert_to_emails.split(",") if e.strip()]

    # Telegram
    telegram_bot_token: str = ""
    telegram_admin_chat_ids: str = ""

    @property
    def telegram_chat_id_list(self) -> List[int]:
        return [int(i.strip()) for i in self.telegram_admin_chat_ids.split(",") if i.strip()]

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    twilio_to_numbers: str = ""

    @property
    def twilio_to_number_list(self) -> List[str]:
        return [n.strip() for n in self.twilio_to_numbers.split(",") if n.strip()]

    # APIs
    abuseipdb_api_key: str = ""
    hibp_api_key: str = ""
    safe_browsing_api_key: str = ""
    gemini_api_key: str = ""

    # Escalation (seconds)
    escalation_tier1_seconds: int = 180
    escalation_tier2_seconds: int = 300

    # Login Watcher
    login_log_file: str = "./demo/sample_logs/auth.log"
    brute_force_threshold: int = 5
    brute_force_window_seconds: int = 60
    auto_block_duration_minutes: int = 60

    # Website Watcher
    uptime_check_interval_minutes: int = 5
    ssl_check_interval_hours: int = 24
    website_urls: str = ""

    @property
    def website_url_list(self) -> List[str]:
        return [u.strip() for u in self.website_urls.split(",") if u.strip()]

    # Breach Watcher
    watched_emails: str = ""

    @property
    def watched_email_list(self) -> List[str]:
        return [e.strip() for e in self.watched_emails.split(",") if e.strip()]

    # Quiet Hours
    quiet_hours_start: int = 23
    quiet_hours_end: int = 7
    quiet_hours_enabled: bool = False

    # Dedupe window
    dedupe_window_minutes: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
