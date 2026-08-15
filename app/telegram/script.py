# github.com/MrAbhi2k3

class Script:
    USER_START_TXT = (
        "👋 **Welcome to Serial Auto Uploader Bot!**\n\n"
        "I automatically monitor, fetch, and deliver television serial episodes.\n\n"
        "• Click channel buttons to retrieve archived episodes.\n"
        "• Paste supported serial links directly to ingest episodes instantly."
    )

    USER_HELP_TXT = (
        "❓ **User Assistance**\n\n"
        "• **Get Files**: Tap `📥 GET FILE` in the channel or use the start link.\n"
        "• **Direct Link**: Send any valid episode link from the target site."
    )

    ADMIN_START_TXT = (
        "👑 **Admin Control Panel**\n\n"
        "Available Commands:\n"
        "• /status - System health & counters\n"
        "• /scan - Immediate scraper scan\n"
        "• /recheck - Pipeline re-check\n"
        "• /pause - Pause automatic scraping\n"
        "• /resume - Resume automatic scraping\n"
        "• /retry - Retry failed uploads\n"
        "• /cleanup - Clean temporary files\n"
        "• /stats - MongoDB statistics\n"
        "• /search `<query>` - Search database"
    )

    UNAUTHORIZED_TXT = "❌ You are not authorized to execute administrative commands."

    URL_DOMAIN_MISMATCH_TXT = "❌ URL domain `{msg_domain}` does not match configured domain `{source_domain}`."
    URL_INSPECTING_TXT = "🔎 Inspecting and scraping URL episode..."
    URL_FAILED_PARSE_TXT = "❌ Could not extract episode metadata from the provided URL."
    URL_ALREADY_EXISTS_TXT = "⚠️ Episode already ingested: **{show_name}** - Ep {episode_number} (Status: {status})"
    URL_INGEST_SUCCESS_TXT = (
        "✅ Extracted & Ingested:\n"
        "📺 **{show_name}** - Ep {episode_number}\n"
        "📅 {episode_date}\n\n"
        "⚙️ Initiating Telegram processing pipeline..."
    )
    URL_PIPELINE_COMPLETE_TXT = "🚀 Episode pipeline processing complete!"
