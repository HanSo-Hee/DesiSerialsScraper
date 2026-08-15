# github.com/MrAbhi2k3

from dataclasses import dataclass
from typing import Optional


@dataclass
class ScrapedEpisode:
    show_name: str
    episode_number: str
    episode_title: str
    episode_date: str
    episode_url: str
    poster_url: Optional[str] = None
    media_url: Optional[str] = None
    source: str = "DesiSerials"

    @property
    def normalized_show_name(self) -> str:
        if not self.show_name:
            return ""
        return " ".join(self.show_name.lower().strip().split())

    @property
    def canonical_id(self) -> str:
        """Returns normalized identifier: normalized_show_name:episode_number:episode_date"""
        norm_show = self.normalized_show_name
        norm_ep = (self.episode_number or "0").strip().lower()
        norm_date = (self.episode_date or "unknown").strip().lower()
        return f"{norm_show}:{norm_ep}:{norm_date}"
