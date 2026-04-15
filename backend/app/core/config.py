from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_PATH = (BACKEND_DIR / "weefarm.db").resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "WeeFarm Backend API"
    app_env: str = "development"
    database_url: str = f"sqlite:///{DEFAULT_SQLITE_PATH}"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 24
    anomaly_loss_threshold: float = 18.0
    step_loss_threshold: float = 12.0

    seed_admin_email: str = "admin@weefarm.local"
    seed_admin_password: str = "Admin123!"
    seed_manager_email: str = "manager@weefarm.local"
    seed_manager_password: str = "Manager123!"


settings = Settings()
