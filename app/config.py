from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central app configuration, loaded from environment variables / .env.

    DATABASE_URL is deliberately backend-agnostic (SQLAlchemy dialect prefix
    decides the driver). Defaults to a local SQLite file so the project runs
    with zero external setup; docker-compose overrides it to PostgreSQL.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./eve_diagnostics.db"

    jwt_secret_key: str = "change-this-secret-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Shared-secret used to authenticate the simulated payment provider's
    # webhook calls. In a real integration this would be a signature check
    # (e.g. HMAC of the payload) rather than a bare shared secret.
    webhook_shared_secret: str = "dev-webhook-secret"


settings = Settings()
