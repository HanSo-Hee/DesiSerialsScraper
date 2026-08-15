# github.com/MrAbhi2k3

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class EpisodeStatus(str, Enum):
    DETECTED = "DETECTED"
    DOWNLOADING = "DOWNLOADING"
    UPLOADING = "UPLOADING"
    UPLOADED = "UPLOADED"
    ARCHIVE_PENDING = "ARCHIVE_PENDING"
    ARCHIVED = "ARCHIVED"
    DELETED_FROM_MAIN = "DELETED_FROM_MAIN"
    FAILED = "FAILED"


@dataclass
class EpisodeModel:
    show_name: str
    episode_number: str
    episode_title: str
    episode_date: str
    source_url: str
    poster_url: Optional[str] = None
    media_url: Optional[str] = None
    source: str = "DesiSerials"
    normalized_show_name: Optional[str] = None
    canonical_id: Optional[str] = None

    status: EpisodeStatus = EpisodeStatus.DETECTED
    telegram_main_message_id: Optional[int] = None
    telegram_archive_message_id: Optional[int] = None
    telegram_history_message_id: Optional[int] = None

    telegram_file_id: Optional[str] = None
    telegram_file_unique_id: Optional[str] = None

    media_type: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    duration: Optional[int] = None

    uploaded_at: Optional[datetime] = None
    archive_due_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    retry_count: int = 0
    last_error: Optional[str] = None

    id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ShowModel:
    name: str
    normalized_name: str
    poster_url: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    id: Optional[str] = None
