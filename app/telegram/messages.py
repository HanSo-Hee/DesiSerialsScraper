# github.com/MrAbhi2k3

from app.config import get_settings


def format_main_caption(show_name: str, episode_number: str, episode_date: str) -> str:
    settings = get_settings()
    template = settings.CAPTION_TEMPLATE
    return template.format(
        show_name=show_name,
        episode_number=episode_number,
        episode_date=episode_date
    )


def format_history_caption(show_name: str, episode_number: str, episode_date: str) -> str:
    return (
        f"📺 {show_name}\n\n"
        f"🎬 Episode {episode_number}\n"
        f"📅 {episode_date}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"📁 File available\n\n"
        f"Tap the button below to get the episode."
    )
