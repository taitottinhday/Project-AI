from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "VinUni Admissions Assistant"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173"

    # LLM
    openai_api_key: str = ""
    model_name: str = "gpt-4o-mini"
    eval_judge_model: str = "gpt-4o-mini"
    llm_temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    llm_timeout_seconds: float = Field(default=25.0, gt=0.0, le=120.0)
    llm_max_retries: int = Field(default=1, ge=0, le=3)

    # Database
    database_url: str = "sqlite:///./data/app.db"

    # Vector Store
    chroma_persist_dir: str = "./data/chroma"

    # Accuracy-first RAG. Paths are resolved from the repository root.
    knowledge_base_dir: str = "./metadata"
    retrieval_top_k: int = Field(default=6, ge=1, le=12)
    retrieval_min_score: float = Field(default=2.2, ge=0.0)
    max_context_chars: int = Field(default=18000, ge=2000, le=50000)
    require_llm_for_answers: bool = False
    knowledge_max_age_days: int = Field(default=30, ge=1, le=365)

    # Safe response cache. Only first-turn, grounded answers are cached and the
    # knowledge dataset identity is part of the cache key.
    response_cache_enabled: bool = True
    response_cache_ttl_seconds: int = Field(default=900, ge=30, le=86400)
    response_cache_max_entries: int = Field(default=500, ge=10, le=10000)

    # Session and handover
    session_ttl_minutes: int = Field(default=1440, ge=5, le=10080)
    session_max_turns: int = Field(default=8, ge=1, le=30)
    staff_api_token: str = ""
    staff_tokens: dict[str, str] = Field(default_factory=dict)
    # Admin identities are deliberately separate from staff identities. They
    # can manage teams and routing, but never need to share a staff secret.
    admin_tokens: dict[str, str] = Field(default_factory=dict)
    rate_limit_per_minute: int = Field(default=30, ge=1, le=600)

    # Applicant authentication: Google OAuth and email OTP registration.
    frontend_url: str = "http://localhost:3000"
    auth_secret: str = "change-me-in-production"
    auth_session_ttl_hours: int = Field(default=168, ge=1, le=8760)
    otp_ttl_minutes: int = Field(default=10, ge=1, le=30)
    otp_max_attempts: int = Field(default=5, ge=1, le=10)
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "VinUni Guide"
    smtp_starttls: bool = True
    # Railway Free/Trial/Hobby plans block outbound SMTP. When a Resend key is
    # present, the HTTPS email API is preferred automatically.
    resend_api_key: str = ""
    resend_from_email: str = ""
    resend_api_url: str = "https://api.resend.com/emails"

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    @property
    def resolved_knowledge_base_dir(self) -> Path:
        path = Path(self.knowledge_base_dir)
        return path if path.is_absolute() else (self.project_root / path).resolve()

    @property
    def sqlite_path(self) -> Path:
        prefix = "sqlite:///"
        raw_path = self.database_url[len(prefix) :] if self.database_url.startswith(prefix) else "./data/app.db"
        path = Path(raw_path)
        return path if path.is_absolute() else (self.project_root / path).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
