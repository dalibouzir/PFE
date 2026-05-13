from pathlib import Path
import os
from typing import Optional

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
    
    # Database configuration - loaded from .env or defaults
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
    ml_risk_low_threshold: float = 6.0
    ml_risk_high_threshold: float = 12.0
    ml_expected_feature_schema_version: str = "phase4-v1"
    ml_max_false_low_high_risk_rate: float = 0.35
    ml_production_min_rows: int = 3000
    ml_monitoring_low_data_rows: int = 2000
    ml_distribution_shift_threshold: float = 0.2

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

    # Environment parity properties
    @property
    def audit_mode(self) -> Optional[str]:
        """Get audit mode from environment (dynamically checked).
        
        None/empty = normal runtime (use database_url from .env, typically Supabase)
        "local_test" = pytest local test mode (use SQLite)
        "supabase_readonly" = pytest supabase readonly mode (use DATABASE_URL env var)
        """
        return os.getenv("AUDIT_MODE", None)
    
    @property
    def is_supabase_mode(self) -> bool:
        """Check if running in Supabase readonly audit mode."""
        return self.audit_mode == "supabase_readonly"
    
    @property
    def is_local_test_mode(self) -> bool:
        """Check if running in local test audit mode."""
        return self.audit_mode == "local_test"
    
    @property
    def is_normal_mode(self) -> bool:
        """Check if running in normal (non-audit) mode."""
        return self.audit_mode is None

    @property
    def db_dialect(self) -> str:
        """Get database dialect (sqlite, postgresql)."""
        if self.is_supabase_mode:
            return "postgresql"
        if self.is_local_test_mode:
            return "sqlite"
        # Normal mode: detect from database_url
        if self.database_url.startswith("postgresql"):
            return "postgresql"
        return "sqlite"

    @property
    def effective_database_url(self) -> str:
        """Get effective database URL based on audit mode.
        
        Audit modes:
        - None (normal): Use database_url (should be Supabase PostgreSQL in .env)
        - "local_test": Use SQLite for pytest
        - "supabase_readonly": Use DATABASE_URL env var for pytest Supabase access
        """
        if self.is_local_test_mode:
            # Pytest local test mode: use SQLite
            return f"sqlite:///{DEFAULT_SQLITE_PATH}"
        elif self.is_supabase_mode:
            # Pytest Supabase readonly mode: use DATABASE_URL env var
            env_url = os.getenv("DATABASE_URL", self.database_url)
            if not env_url or env_url.startswith("sqlite"):
                # If no valid Supabase URL, return the one from .env or raise later
                return self.database_url
            return env_url
        else:
            # Normal mode: use configured database_url (typically Supabase from .env)
            return self.database_url

    @property
    def has_pgvector(self) -> bool:
        """Check if pgvector is available (Supabase mode only)."""
        return self.is_supabase_mode

    @property
    def masked_database_url(self) -> str:
        """Return masked database URL for logging."""
        url = self.effective_database_url
        if "@" in url:
            # PostgreSQL format: dialect+driver://user:password@host:port/db
            return url.split("@")[-1]
        # SQLite format
        return url.split("/")[-1]

    def get_environment_metadata(self) -> dict:
        """Get comprehensive environment metadata for audits."""
        return {
            "audit_mode": self.audit_mode,
            "database_provider": "Supabase PostgreSQL" if self.is_supabase_mode else "SQLite",
            "database_dialect": self.db_dialect,
            "database_url_masked": self.masked_database_url,
            "rag_source": "Supabase pgvector" if self.is_supabase_mode else "SQLite (no pgvector)",
            "pgvector_enabled": self.has_pgvector,
            "read_only_mode": self.is_supabase_mode,
        }

    def log_environment_parity(self, context: str = ""):
        """Log environment parity information."""
        metadata = self.get_environment_metadata()
        print("\n" + "=" * 70)
        print(f"ENVIRONMENT PARITY CHECK {context}".ljust(70, "="))
        print("=" * 70)
        for key, value in metadata.items():
            print(f"  {key:.<25} {value}")
        print("=" * 70 + "\n")


settings = Settings()
