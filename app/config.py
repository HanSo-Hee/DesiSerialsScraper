# github.com/MrAbhi2k3

import os
from typing import List, Optional, Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    API_ID: int
    API_HASH: str
    BOT_TOKEN: str

    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "serial_bot"

    MAIN_CHANNEL_ID: int
    FILE_CHANNEL_ID: int
    HISTORY_CHANNEL_ID: int
    LOG_CHANNEL_ID: Optional[int] = None

    ADMIN_IDS: Any = Field(default_factory=list)
    FORCE_SUB_CHANNELS: Any = Field(default_factory=lambda: [-1001259499812])

    SOURCE_URL: str = "https://www.desi-serials.to/latest-episodes/"
    TARGET_DOMAINS: Any = Field(default_factory=lambda: ["www.desi-serials.to", "desi-serials.to"])
    SCRAPE_INTERVAL: int = 1800

    DELETE_AFTER_HOURS: float = 12.0

    DOWNLOAD_DIR: str = "downloads"
    DOWNLOAD_TIMEOUT: int = 1800

    MAX_CONCURRENT_DOWNLOADS: int = 2
    MAX_CONCURRENT_UPLOADS: int = 1

    CAPTION_TEMPLATE: str = (
        "📺 **{show_name}**\n\n"
        "🎬 **Episode {episode_number}**\n"
        "📅 **{episode_date}**\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📢 **Uploaded by:** @tellyfun_official"
    )

    LOG_LEVEL: str = "INFO"
    TIMEZONE: str = "UTC"

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, (int, list)):
            if isinstance(v, int):
                return [v]
            return v
        return []

    @field_validator("FORCE_SUB_CHANNELS", mode="before")
    @classmethod
    def parse_force_sub_channels(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, (int, list)):
            if isinstance(v, int):
                return [v]
            return v
        return [-1001259499812]

    @field_validator("TARGET_DOMAINS", mode="before")
    @classmethod
    def parse_target_domains(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return ["www.desi-serials.to", "desi-serials.to"]
            return [x.strip().lower() for x in v.split(",") if x.strip()]
        if isinstance(v, list):
            return v
        return ["www.desi-serials.to", "desi-serials.to"]

    @field_validator("SOURCE_URL")
    @classmethod
    def ensure_trailing_slash(cls, v: str) -> str:
        if v and not v.endswith("/"):
            return v + "/"
        return v


settings: Optional[Settings] = None


def get_settings() -> Settings:
    global settings
    if settings is None:
        settings = Settings()
    return settings
