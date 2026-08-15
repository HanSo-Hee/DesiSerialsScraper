# github.com/MrAbhi2k3

import os
import re
import urllib.parse
from pathlib import Path


def sanitize_filename(name: str) -> str:
    """Sanitize strings to prevent path traversal or invalid OS file names."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    clean = clean.replace(" ", "_").strip("._")
    return clean or "file"


def get_safe_filepath(download_dir: str, filename: str) -> str:
    """Generates absolute path inside download directory and prevents directory traversal."""
    base_dir = Path(download_dir).resolve()
    base_dir.mkdir(parents=True, exist_ok=True)
    
    clean_name = sanitize_filename(filename)
    file_path = (base_dir / clean_name).resolve()

    if not str(file_path).startswith(str(base_dir)):
        raise ValueError(f"Path traversal detected: {filename}")

    return str(file_path)


def get_filename_from_url(url: str, default_name: str = "episode.mp4") -> str:
    parsed = urllib.parse.urlparse(url)
    path_name = os.path.basename(parsed.path)
    if path_name and "." in path_name:
        return path_name
    return default_name
