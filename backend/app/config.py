import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://agencydesk:agencydesk@localhost:5432/agencydesk",
    )
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret-change-me")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24
    upload_dir: str = os.getenv("UPLOAD_DIR", "./uploads")

    class Config:
        env_file = ".env"


settings = Settings()
