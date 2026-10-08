from functools import lru_cache
from typing import Literal
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    app_name: str = 'Imperial Pack API'
    environment: str = 'development'
    api_prefix: str = '/api'
    database_url: str | None = None
    secret_key: str | None = None
    access_token_minutes: int = 30
    refresh_token_days: int = 14
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None
    google_authorized_emails: str = ''
    initial_admin_email: str | None = None
    cookie_samesite: Literal['lax', 'none'] = 'lax'
    cookie_secure: bool | None = None
    frontend_origins: str = 'http://localhost:5173'

    @model_validator(mode='after')
    def validate_cookie_settings(self):
        if self.cookie_samesite == 'none' and self.cookie_secure is False:
            raise ValueError('COOKIE_SECURE must be true when COOKIE_SAMESITE is none.')
        if self.environment.lower() == 'production':
            if not self.secret_key or len(self.secret_key.encode('utf-8')) < 32:
                raise ValueError('SECRET_KEY must contain at least 32 bytes in production.')
            if self.cookie_secure is False:
                raise ValueError('COOKIE_SECURE must be true in production.')
        return self

    @property
    def secure_cookies(self) -> bool:
        return self.cookie_secure if self.cookie_secure is not None else self.environment.lower() == 'production' or self.cookie_samesite == 'none'

    @property
    def bootstrap_admin_email(self) -> str | None:
        return self.initial_admin_email.strip().lower() if self.initial_admin_email and self.initial_admin_email.strip() else None

    @property
    def allowed_emails(self) -> set[str]:
        return {value.strip().lower() for value in self.google_authorized_emails.split(',') if value.strip()}

    @property
    def cors_origins(self) -> list[str]:
        return [value.strip() for value in self.frontend_origins.split(',') if value.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
