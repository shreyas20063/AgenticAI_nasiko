"""
Application configuration with environment variable loading.
All secrets come from env vars - never hardcoded.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "nasiko-hr-platform"
    app_env: str = "development"
    app_port: int = 8000
    app_secret_key: str = "change-me"
    app_debug: bool = True

    # Database
    database_url: str = "sqlite+aiosqlite:///./hr_platform.db"

    # LLM
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.3

    # Vector Store
    chroma_persist_dir: str = "./chroma_data"
    chroma_collection_name: str = "hr_knowledge_base"
    embedding_model: str = "text-embedding-3-small"

    # JWT
    jwt_secret_key: str = "change-me-jwt"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_name: str = "HR Platform"

    # Nasiko
    nasiko_agent_id: str = "hr-automation-agent"
    nasiko_api_endpoint: str = ""
    nasiko_agent_token: str = ""


@lru_cache()
def get_settings() -> Settings:
    return Settings()
