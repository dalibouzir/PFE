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
    cors_origins: str = ",".join(
        [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
        ]
    )
    database_url: str = f"sqlite:///{DEFAULT_SQLITE_PATH}"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 24
    anomaly_loss_threshold: float = 18.0
    step_loss_threshold: float = 12.0
    ml_artifacts_path: str = "./artifacts"
    ml_min_rows: int = 120
    ml_rolling_window: int = 5
    ml_holdout_ratio: float = 0.2
    ml_feedback_min_rows: int = 200
    ml_confidence_high_threshold: float = 0.8
    ml_confidence_medium_threshold: float = 0.6
    ml_data_drift_zscore_threshold: float = 2.5
    ml_data_drift_feature_count_threshold: int = 3
    ml_calibration_drift_threshold: float = 0.08
    ml_recommendation_confidence_threshold: float = 0.55
    ml_harmful_probability_threshold: float = 0.35

    llm_provider: str = "openrouter"
    llm_model: str = "openai/gpt-4o-mini"
    llm_timeout_seconds: float = 30.0
    llm_max_tokens: int = 280
    openrouter_api_key: str = ""
    groq_api_key: str = ""
    openai_api_key: str = ""

    rag_enabled: bool = True
    rag_embedding_provider: str = "openrouter"
    rag_embedding_model: str = "openai/text-embedding-3-small"
    rag_embedding_base_url: str = ""
    rag_embedding_api_key: str = ""
    rag_embedding_dimensions: int = 1536
    rag_chunk_size: int = 900
    rag_chunk_overlap: int = 180
    rag_retrieval_top_k: int = 5

    seed_admin_email: str = "admin@weefarm.local"
    seed_admin_password: str = "Admin123!"
    seed_manager_email: str = "manager@weefarm.local"
    seed_manager_password: str = "Manager123!"


settings = Settings()
