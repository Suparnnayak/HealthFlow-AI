from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration."""

    # JWT / auth
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def strip_secret_key_quotes(cls, v: str) -> str:
        """
        Strip surrounding quotes that users sometimes copy-paste from .env
        into Vercel / cloud dashboards.  Literal quotes in a JWT secret
        confuse python-jose's key detection (it tries JWK parsing).
        """
        if isinstance(v, str) and len(v) >= 2:
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()



