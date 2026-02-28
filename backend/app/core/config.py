from typing import List, Union, Dict, Any
from pydantic import AnyHttpUrl, validator
from pydantic_settings import BaseSettings
from app.core.config_loader import app_config

class Settings(BaseSettings):
    APP_NAME: str = "TLS Supervision"
    APP_SHORTNAME: str = "TLS"
    PROJECT_NAME: str = "TLS Supervision"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "production" # production | development
    DEFAULT_DISPLAY_TIMEZONE: str = "Europe/Paris"
    PROFILE_SOURCE_MODE: str = "DB_FALLBACK_YAML" # DB_ONLY | DB_FALLBACK_YAML
    
    # Admin Seed Configuration
    DEFAULT_ADMIN_EMAIL: str = "admin@supervision.local"
    DEFAULT_ADMIN_PASSWORD: str | None = None
    AUTO_SEED_ADMIN: bool = True
    
    # BACKEND_CORS_ORIGINS is a JSON-formatted list of origins
    # e.g: '["http://localhost", "http://localhost:4200", "http://localhost:3000"]'
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = ["http://localhost:3000"]

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)


    @validator("DEFAULT_ADMIN_PASSWORD", pre=True, always=True)
    def validate_admin_password(cls, v: str | None, values: dict) -> str | None:
        env = values.get("ENVIRONMENT", "production")
        if env == "production" and not v:
            # En prod, on ne met pas de valeur par défaut
            return None
        if not v and env == "development":
            return "SuperSecurePassword123"
        return v

    POSTGRES_SERVER: str = "db"
    POSTGRES_USER: str = "admin"
    POSTGRES_PASSWORD: str = "admin_password_secure_change_me"
    POSTGRES_DB: str = "supervision"
    
    ARCHIVE_PATH: str = "/app/data/archive"
    UPLOAD_PATH: str = "/app/data/uploads"

    SQLALCHEMY_DATABASE_URI: str | None = None

    @validator("SQLALCHEMY_DATABASE_URI", pre=True)
    def assemble_db_connection(cls, v: str | None, values: dict) -> str:
        if isinstance(v, str):
            return v
        return f"postgresql+asyncpg://{values.get('POSTGRES_USER')}:{values.get('POSTGRES_PASSWORD')}@{values.get('POSTGRES_SERVER')}/{values.get('POSTGRES_DB')}"

    # Usage of app_config directly for field defaults
    INGESTION: Dict[str, Any] = app_config.get('ingestion', {})
    ANTI_NOISE: Dict[str, Any] = app_config.get('anti_noise', {})
    ZONING: Dict[str, Any] = app_config.get('zoning', {})
    NORMALIZATION: Dict[str, Any] = app_config.get('normalization', {})
    BUSINESS_RULES: Dict[str, Any] = app_config.get('business_rules', {})

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
