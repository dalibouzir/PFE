from pathlib import Path
import os
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


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
    
    # Database configuration - required Supabase/PostgreSQL URL
    database_url: str
    
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
    seed_super_admin_email: str = "superadmin@weefarm.local"
    seed_super_admin_password: str = "SuperAdmin123!"
    seed_institution_admin_email: str = "institution.admin@weefarm.local"
    seed_institution_admin_password: str = "InstitutionAdmin123!"
    seed_institution_name: str = "Institution Demo WeeFarm"
    seed_manager_email: str = "manager@weefarm.local"
    seed_manager_password: str = "Manager123!"

    uploads_dir: str = str(BACKEND_DIR / "uploads")

    # Environment parity properties
    @property
    def audit_mode(self) -> Optional[str]:
        """Get audit mode from environment (dynamically checked).
        
        None/empty = normal runtime
        "supabase_readonly" = pytest readonly mode on Supabase
        """
        return os.getenv("AUDIT_MODE", None)
    
    @property
    def is_supabase_mode(self) -> bool:
        """Check if running in Supabase readonly audit mode."""
        return self.audit_mode == "supabase_readonly"
    
    @property
    def is_normal_mode(self) -> bool:
        """Check if running in normal (non-audit) mode."""
        return self.audit_mode is None

    @property
    def db_dialect(self) -> str:
        """Get database dialect."""
        return "postgresql" if self.effective_database_url.startswith("postgresql") else "unknown"

    @property
    def effective_database_url(self) -> str:
        """Get effective database URL (PostgreSQL/Supabase only)."""
        url = os.getenv("DATABASE_URL", self.database_url).strip()
        if not url:
            raise ValueError("DATABASE_URL is required.")
        if not url.startswith("postgresql"):
            raise ValueError("Only PostgreSQL/Supabase DATABASE_URL is supported.")
        return url

    @property
    def has_pgvector(self) -> bool:
        """Check if pgvector can be used."""
        return True

    @property
    def masked_database_url(self) -> str:
        """Return masked database URL for logging."""
        url = self.effective_database_url
        if "@" in url:
            # PostgreSQL format: dialect+driver://user:password@host:port/db
            return url.split("@")[-1]
        return url

    def get_environment_metadata(self) -> dict:
        """Get comprehensive environment metadata for audits."""
        return {
            "audit_mode": self.audit_mode,
            "database_provider": "Supabase PostgreSQL",
            "database_dialect": self.db_dialect,
            "database_url_masked": self.masked_database_url,
            "rag_source": "Supabase pgvector",
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
