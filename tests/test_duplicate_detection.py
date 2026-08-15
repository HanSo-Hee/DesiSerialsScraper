# github.com/MrAbhi2k3

import pytest
from app.scraper.models import ScrapedEpisode


def test_canonical_id_generation():
    ep1 = ScrapedEpisode(
        show_name="Anupama ",
        episode_number="2105",
        episode_title="Anupama Ep 2105",
        episode_date="14 August 2026",
        episode_url="https://desiserials.com.co/ep1"
    )

    ep2 = ScrapedEpisode(
        show_name="anupama",
        episode_number="2105",
        episode_title="Anupama Ep 2105 HD",
        episode_date="14 August 2026",
        episode_url="https://desiserials.com.co/ep2"
    )

    assert ep1.normalized_show_name == "anupama"
    assert ep1.canonical_id == ep2.canonical_id
    assert ep1.canonical_id == "anupama:2105:14 august 2026"
