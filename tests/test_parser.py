# github.com/MrAbhi2k3

import pytest
from app.scraper.parser import ScraperParser

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Anupama - 14th August 2026 Episode 2105 Watch Online</title></head>
<body>
    <article class="post">
        <h1 class="entry-title">Anupama - 14th August 2026 Episode 2105 Full Episode</h1>
        <img class="poster" src="https://example.com/poster.jpg" />
        <video src="https://example.com/video.mp4"></video>
    </article>
</body>
</html>
"""


def test_parser_show_name_extraction():
    title = "Anupama - 14th August 2026 Episode 2105 Watch Online HD"
    show_name = ScraperParser.extract_show_name(title)
    assert show_name == "Anupama"


def test_parser_episode_number_extraction():
    title = "Anupama - Episode 2105 Full Episode"
    ep_num = ScraperParser.extract_episode_number(title)
    assert ep_num == "2105"


def test_parser_episode_date_extraction():
    title = "Anupama 14th August 2026 Episode 2105"
    ep_date = ScraperParser.extract_episode_date(title, SAMPLE_HTML)
    assert ep_date == "14th August 2026"


def test_parse_episode_page():
    ep = ScraperParser.parse_episode_page(SAMPLE_HTML, "https://desiserials.com.co/anupama-ep-2105")
    assert ep is not None
    assert ep.show_name == "Anupama"
    assert ep.episode_number == "2105"
    assert ep.episode_date == "14th August 2026"
    assert ep.media_url == "https://example.com/video.mp4"
    assert ep.poster_url == "https://example.com/poster.jpg"
