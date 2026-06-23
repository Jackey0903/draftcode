from functools import lru_cache
import os

from pydantic import BaseModel


class Settings(BaseModel):
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/nbadraft",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
