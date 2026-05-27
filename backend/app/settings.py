import os
from dataclasses import dataclass


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str
    debug: bool
    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    company_domain: str
    cors_allowed_origins: list[str]
    enable_seed_endpoint: bool
    create_schema_on_startup: bool
    max_request_body_bytes: int
    rate_limit_requests_per_minute: int
    rate_limit_window_seconds: int

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


def get_settings() -> Settings:
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    if app_env not in {"development", "test", "production"}:
        raise RuntimeError("APP_ENV must be one of: development, test, production")

    jwt_secret_key = os.getenv("JWT_SECRET_KEY", "local-dev-secret-key")
    if app_env == "production" and (not jwt_secret_key or jwt_secret_key == "local-dev-secret-key"):
        raise RuntimeError("JWT_SECRET_KEY must be set to a non-default value in production")

    default_db = "sqlite:///./silo.db"
    database_url = os.getenv("DATABASE_URL", default_db).strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL cannot be empty")

    cors_origins_raw = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
    cors_allowed_origins = [origin.strip() for origin in cors_origins_raw.split(",") if origin.strip()]

    return Settings(
        app_env=app_env,
        debug=_parse_bool(os.getenv("APP_DEBUG"), app_env != "production"),
        database_url=database_url,
        jwt_secret_key=jwt_secret_key,
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")),
        company_domain=os.getenv("COMPANY_DOMAIN", "company.com").strip().lower(),
        cors_allowed_origins=cors_allowed_origins,
        enable_seed_endpoint=_parse_bool(os.getenv("ENABLE_SEED_ENDPOINT"), app_env != "production"),
        create_schema_on_startup=_parse_bool(os.getenv("CREATE_SCHEMA_ON_STARTUP"), app_env != "production"),
        max_request_body_bytes=int(os.getenv("MAX_REQUEST_BODY_BYTES", str(1024 * 1024))),
        rate_limit_requests_per_minute=int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "120")),
        rate_limit_window_seconds=int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")),
    )


settings = get_settings()
