"""
Configuration Management for N-CIIA

Centralized configuration with environment variable support,
validation, and secure handling of sensitive values.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration."""

    model_config = SettingsConfigDict(env_prefix="NCIIA_DB_")

    path: str = "data/db/nciia.db"
    echo: bool = False
    pool_size: int = 5


class APISettings(BaseSettings):
    """API server configuration."""

    model_config = SettingsConfigDict(env_prefix="NCIIA_API_")

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    # In production set this to your exact frontend origin, e.g.:
    # NCIIA_API_CORS_ORIGINS='["https://nciia.yourdomain.com"]'
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",   # Vite dev server
            "http://localhost:3000",   # Create-React-App dev server
            "http://127.0.0.1:5173",
        ]
    )
    # Optional API key — leave unset for open access in development
    api_key: Optional[str] = None
    # Sliding-window rate limit (requests per minute per IP)
    rate_limit: int = 100
    # Rate limit window in seconds
    rate_window: int = 60


class OSINTSettings(BaseSettings):
    """OSINT collection configuration."""

    model_config = SettingsConfigDict(env_prefix="NCIIA_OSINT_")

    enabled_sources: list[str] = Field(
        default_factory=lambda: ["web_search", "paste_sites", "forum"]
    )
    default_interval_seconds: int = 300  # 5 minutes
    max_concurrent_watchers: int = 10
    rate_limit_per_source: int = 10  # Requests per minute per source
    respect_robots_txt: bool = True
    user_agent: str = "N-CIIA OSINT Collector/1.0.0 (Research)"
    request_timeout: int = 30


class MLSettings(BaseSettings):
    """Machine learning configuration."""

    model_config = SettingsConfigDict(env_prefix="NCIIA_ML_")

    models_dir: str = "models"
    use_gpu: bool = False  # Explicitly CPU-only
    max_batch_size: int = 32
    inference_threads: int = 4

    # Confidence thresholds
    min_confidence_for_alert: float = 0.7
    min_confidence_for_action: float = 0.85


class LLMSettings(BaseSettings):
    """LLM integration configuration."""

    model_config = SettingsConfigDict(env_prefix="NCIIA_LLM_")

    provider: str = "ollama"  # ollama, openai, anthropic, groq
    model_name: str = "llama2"
    api_base: str = "http://localhost:11434"
    api_key: Optional[str] = None
    max_tokens: int = 2048
    temperature: float = 0.1  # Low temperature for deterministic responses
    timeout: int = 60


class LoggingSettings(BaseSettings):
    """Logging configuration."""

    model_config = SettingsConfigDict(env_prefix="NCIIA_LOG_")

    level: str = "INFO"
    format: str = "json"  # json or console
    file_path: Optional[str] = "logs/nciia.log"
    max_size_mb: int = 100
    backup_count: int = 5
    include_timestamp: bool = True


class SecuritySettings(BaseSettings):
    """Security configuration."""

    model_config = SettingsConfigDict(env_prefix="NCIIA_SECURITY_")

    enable_audit_log: bool = True
    session_timeout_minutes: int = 60
    max_failed_attempts: int = 5
    hash_algorithm: str = "sha256"


class Settings(BaseSettings):
    """Root configuration container."""

    model_config = SettingsConfigDict(
        env_prefix="NCIIA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application info
    app_name: str = "N-CIIA"
    version: str = "1.0.0"
    environment: str = "development"  # development, staging, production

    # Sub-configurations
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    api: APISettings = Field(default_factory=APISettings)
    osint: OSINTSettings = Field(default_factory=OSINTSettings)
    ml: MLSettings = Field(default_factory=MLSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)

    # Paths
    data_dir: str = "data"
    cache_dir: str = "data/cache"
    exports_dir: str = "data/exports"

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v

    def ensure_directories(self) -> None:
        """Create necessary directories."""
        dirs = [
            self.data_dir,
            self.cache_dir,
            self.exports_dir,
            Path(self.database.path).parent,
        ]
        if self.logging.file_path:
            dirs.append(Path(self.logging.file_path).parent)

        for d in dirs:
            Path(d).mkdir(parents=True, exist_ok=True)


def load_yaml_config(config_path: str | Path) -> dict[str, Any]:
    """Load configuration from YAML file."""
    path = Path(config_path)
    if not path.exists():
        return {}

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings singleton.

    Settings are loaded from (in priority order — highest wins):
    1. Environment variables
    2. .env file
    3. config/system.yaml
    4. Default values
    """
    yaml_config = load_yaml_config("config/system.yaml")
    settings = Settings(**yaml_config)
    settings.ensure_directories()
    return settings


def reload_settings() -> Settings:
    """Force reload settings (clears cache). Use in tests or after .env changes."""
    get_settings.cache_clear()
    return get_settings()
