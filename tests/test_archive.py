# github.com/MrAbhi2k3

import pytest
from datetime import datetime, timedelta, timezone
from app.config import Settings
from app.database.models import EpisodeModel, EpisodeStatus


def test_12_hour_archive_calculation():
    now = datetime.now(timezone.utc)
    delete_hours = 12.0
    archive_due = now + timedelta(hours=delete_hours)

    assert archive_due > now
    assert (archive_due - now).total_seconds() == 12 * 3600


def test_admin_ids_parser():
    settings = Settings(
        API_ID=123,
        API_HASH="abc",
        BOT_TOKEN="123:abc",
        MAIN_CHANNEL_ID=-1,
        FILE_CHANNEL_ID=-2,
        HISTORY_CHANNEL_ID=-3,
        ADMIN_IDS="100, 200, 300"
    )

    assert settings.ADMIN_IDS == [100, 200, 300]
