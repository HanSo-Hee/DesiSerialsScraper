# github.com/MrAbhi2k3

import os
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class MediaMetadataInfo:
    file_name: str
    file_size: int
    duration: Optional[int] = None
    media_type: str = "video"


def extract_media_metadata(filepath: str) -> MediaMetadataInfo:
    """Extracts size and basic media metadata from a downloaded file."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    size = os.path.getsize(filepath)
    name = os.path.basename(filepath)

    ext = os.path.splitext(name)[1].lower()
    media_type = "photo" if ext in [".jpg", ".jpeg", ".png", ".webp"] else "video"

    return MediaMetadataInfo(
        file_name=name,
        file_size=size,
        duration=None,
        media_type=media_type
    )
