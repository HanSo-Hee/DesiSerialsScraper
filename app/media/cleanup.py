# github.com/MrAbhi2k3

import os
import glob
import logging
from pathlib import Path
from app.config import get_settings

logger = logging.getLogger(__name__)


def cleanup_file(filepath: str) -> bool:
    """Removes a single file safely if it exists."""
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            logger.debug(f"Cleaned temporary file: {filepath}")
            return True
    except Exception as e:
        logger.warning(f"Failed to remove file {filepath}: {e}")
    return False


def cleanup_directory(dir_path: Optional[str] = None) -> int:
    """Cleans all temporary downloaded files inside download directory."""
    settings = get_settings()
    target_dir = Path(dir_path or settings.DOWNLOAD_DIR).resolve()

    if not target_dir.exists():
        return 0

    removed_count = 0
    for item in target_dir.iterdir():
        if item.is_file() and item.name != ".gitkeep":
            try:
                item.unlink()
                removed_count += 1
            except Exception as e:
                logger.warning(f"Error removing {item}: {e}")

    logger.info(f"Cleanup finished. Removed {removed_count} temporary files.")
    return removed_count
