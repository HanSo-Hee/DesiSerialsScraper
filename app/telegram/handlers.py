# github.com/MrAbhi2k3

import logging
from urllib.parse import urlparse
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from app.config import get_settings
from app.database.repositories import EpisodeRepository, SettingsRepository
from app.telegram.filters import admin_filter
from app.telegram.script import Script

logger = logging.getLogger(__name__)

_latest_cache = {}


def register_handlers(app: Client):

    @app.on_message(filters.command("start") & filters.private & ~admin_filter())
    async def user_start_handler(client: Client, message: Message):
        from app.telegram.forcesub import ForceSubManager
        joined, missing = await ForceSubManager.check_user_joined(client, message.from_user.id)
        
        args = message.command
        cb_data = f"verify_{args[1]}" if len(args) > 1 else "verify_start"
        
        if not joined:
            kb = ForceSubManager.build_fsub_keyboard(missing, callback_data=cb_data)
            await message.reply_text("⚠️ **Force Channel Subscription Required!**\n\nPlease join our update channels to use this bot and retrieve episodes:", reply_markup=kb)
            return

        if len(args) > 1 and args[1].startswith("get_"):
            ep_id = args[1].replace("get_", "")
            await send_file_to_user(client, message.chat.id, ep_id)
            return

        await message.reply_text(Script.USER_START_TXT)

    @app.on_callback_query(filters.regex(r"^verify_(.+)"))
    async def verify_fsub_callback(client: Client, callback_query: CallbackQuery):
        from app.telegram.forcesub import ForceSubManager
        joined, missing = await ForceSubManager.check_user_joined(client, callback_query.from_user.id)
        target = callback_query.matches[0].group(1)

        if not joined:
            await callback_query.answer("❌ You have not joined all required channels yet!", show_alert=True)
            return

        await callback_query.answer("✅ Verification successful!", show_alert=False)
        await callback_query.message.delete()

        if target.startswith("get_"):
            ep_id = target.replace("get_", "")
            await send_file_to_user(client, callback_query.from_user.id, ep_id)
        else:
            await client.send_message(callback_query.from_user.id, Script.USER_START_TXT)

    @app.on_message(filters.command("help") & ~admin_filter())
    async def user_help_handler(client: Client, message: Message):
        from app.telegram.forcesub import ForceSubManager
        joined, missing = await ForceSubManager.check_user_joined(client, message.from_user.id)
        if not joined:
            kb = ForceSubManager.build_fsub_keyboard(missing, callback_data="verify_start")
            await message.reply_text("⚠️ **Force Channel Subscription Required!**\n\nPlease join our update channels:", reply_markup=kb)
            return
        await message.reply_text(Script.USER_HELP_TXT)

    @app.on_callback_query(filters.regex(r"^get_ep:(.+)"))
    async def get_file_callback_handler(client: Client, callback_query: CallbackQuery):
        from app.telegram.forcesub import ForceSubManager
        joined, missing = await ForceSubManager.check_user_joined(client, callback_query.from_user.id)
        ep_id = callback_query.matches[0].group(1)

        if not joined:
            kb = ForceSubManager.build_fsub_keyboard(missing, callback_data=f"verify_get_{ep_id}")
            await callback_query.message.reply_text("⚠️ **Force Channel Subscription Required!**\n\nPlease join our update channels:", reply_markup=kb)
            return

        await callback_query.answer("Retrieving file...", show_alert=False)
        await send_file_to_user(client, callback_query.from_user.id, ep_id)

    async def send_file_to_user(client: Client, chat_id: int, episode_id: str):
        episode = await EpisodeRepository.find_by_id(episode_id)
        if not episode:
            await client.send_message(chat_id, "❌ Episode not found or link has expired.")
            return

        if episode.telegram_file_id:
            try:
                caption = f"📺 **{episode.show_name}** - Ep {episode.episode_number}\n📅 {episode.episode_date}"
                await client.send_video(
                    chat_id=chat_id,
                    video=episode.telegram_file_id,
                    caption=caption
                )
            except Exception as e:
                logger.error(f"Error sending file to user {chat_id}: {e}")
                await client.send_message(chat_id, "❌ Error retrieving archived file.")
        else:
            await client.send_message(chat_id, f"📺 Episode info: **{episode.show_name}** - Ep {episode.episode_number}\n❌ Media file is not currently available.")

    @app.on_message(filters.text & filters.regex(r"https?://[^\s]+") & ~filters.command(["start", "help", "status", "scan", "recheck", "pause", "resume", "retry", "cleanup", "stats", "search"]))
    async def url_ingest_handler(client: Client, message: Message):
        settings = get_settings()
        url = message.text.strip()

        msg_domain = urlparse(url).netloc.lower()
        allowed_domains = [d.lower() for d in settings.TARGET_DOMAINS]

        if not any(dom in msg_domain for dom in allowed_domains):
            await message.reply_text(f"❌ Only `desi-serials.to` links are supported.")
            return

        status_msg = await message.reply_text("🔍 Fetching episode info...")

        try:
            from app.scraper.client import ScraperClient
            from app.scraper.parser import ScraperParser
            from app.services.episode_service import EpisodeService
            from app.database.repositories import EpisodeRepository, ShowRepository
            from app.database.models import EpisodeModel, EpisodeStatus

            client_http = ScraperClient()
            html = await client_http.fetch_html(url)
            await client_http.close()

            scraped = ScraperParser.parse_episode_page(html, url)
            if not scraped or not scraped.media_url:
                await status_msg.edit_text("❌ Could not extract episode data from the URL.")
                return

            existing = await EpisodeRepository.find_duplicate(source_url=scraped.episode_url, canonical_id=scraped.canonical_id)
            if existing and existing.telegram_file_id:
                await status_msg.edit_text(f"⚠️ Already uploaded: **{existing.show_name}** Ep {existing.episode_number}")
                await client.send_video(
                    chat_id=message.chat.id,
                    video=existing.telegram_file_id,
                    caption=f"📺 **{existing.show_name}** - Ep {existing.episode_number}\n📅 {existing.episode_date}"
                )
                return

            show = await ShowRepository.get_or_create(
                name=scraped.show_name,
                normalized_name=scraped.normalized_show_name,
                poster_url=scraped.poster_url
            )
            ep_model = EpisodeModel(
                show_name=scraped.show_name,
                normalized_show_name=scraped.normalized_show_name,
                episode_number=scraped.episode_number,
                episode_title=scraped.episode_title,
                episode_date=scraped.episode_date,
                source_url=scraped.episode_url,
                poster_url=scraped.poster_url or show.poster_url,
                media_url=scraped.media_url,
                source=scraped.source,
                canonical_id=scraped.canonical_id,
                status=EpisodeStatus.DETECTED
            )

            inserted = await EpisodeRepository.insert(ep_model)
            await status_msg.edit_text(
                f"✅ Found: **{inserted.show_name}** Ep {inserted.episode_number}\n⏳ Downloading & uploading..."
            )

            service = EpisodeService()
            updated_ep = await service.process_single_episode(
                inserted,
                status_message=status_msg,
                reply_to_user_chat=message.chat.id
            )

            if updated_ep and updated_ep.telegram_file_id:
                await status_msg.edit_text(f"🎉 Done! **{inserted.show_name}** has been sent to you above.")
            else:
                await status_msg.edit_text("❌ Could not resolve or download the video stream. Episode marked as failed.")

        except Exception as e:
            logger.error(f"Error processing user URL {url}: {e}", exc_info=True)
            await status_msg.edit_text(f"❌ Error: {e}")



    admin_commands = ["status", "scan", "recheck", "pause", "resume", "retry", "cleanup", "stats", "search", "latest"]

    @app.on_message(filters.command(admin_commands) & ~admin_filter())
    async def unauthorized_admin_handler(client: Client, message: Message):
        await message.reply_text(Script.UNAUTHORIZED_TXT)

    @app.on_message(filters.command("latest") & admin_filter())
    async def latest_episodes_handler(client: Client, message: Message):
        msg = await message.reply_text("🔄 Scraping and uploading latest episodes from `https://www.desi-serials.to/latest-episodes/`...")
        try:
            from app.services.episode_service import EpisodeService
            service = EpisodeService()
            count = await service.run_scraper_pipeline()
            await msg.edit_text(f"🎉 Scraping complete! **{count}** new episodes ingested and uploaded.")
        except Exception as e:
            logger.error(f"Error executing /latest command: {e}", exc_info=True)
            await msg.edit_text(f"❌ Error fetching latest episodes: {e}")

    @app.on_callback_query(filters.regex(r"^up_one:(\d+)") & admin_filter())
    async def upload_single_latest_callback(client: Client, callback_query: CallbackQuery):
        idx = int(callback_query.matches[0].group(1))
        user_id = callback_query.from_user.id
        from app.telegram.handlers import _latest_cache

        episodes = _latest_cache.get(user_id)
        if not episodes or idx >= len(episodes):
            await callback_query.answer("❌ Session expired. Please run /latest again.", show_alert=True)
            return

        item = episodes[idx]
        await callback_query.answer(f"Processing {item.show_name}...", show_alert=False)
        status_msg = await callback_query.message.reply_text(f"🔄 Ingesting & uploading **{item.show_name}**...")

        try:
            from app.database.repositories import EpisodeRepository, ShowRepository
            from app.database.models import EpisodeModel, EpisodeStatus
            from app.services.episode_service import EpisodeService

            existing = await EpisodeRepository.find_duplicate(source_url=item.episode_url, canonical_id=item.canonical_id)
            if existing:
                await status_msg.edit_text(f"⚠️ **{existing.show_name}** - Ep {existing.episode_number} already exists in DB.")
                if existing.telegram_file_id:
                    await client.send_video(
                        chat_id=callback_query.message.chat.id,
                        video=existing.telegram_file_id,
                        caption=f"📺 **{existing.show_name}** - Ep {existing.episode_number}\n📅 {existing.episode_date}"
                    )
                return

            show = await ShowRepository.get_or_create(name=item.show_name, normalized_name=item.normalized_show_name, poster_url=item.poster_url)
            ep_model = EpisodeModel(
                show_name=item.show_name,
                normalized_show_name=item.normalized_show_name,
                episode_number=item.episode_number,
                episode_title=item.episode_title,
                episode_date=item.episode_date,
                source_url=item.episode_url,
                poster_url=item.poster_url or show.poster_url,
                media_url=item.media_url,
                source=item.source,
                canonical_id=item.canonical_id,
                status=EpisodeStatus.DETECTED
            )

            inserted = await EpisodeRepository.insert(ep_model)
            service = EpisodeService()
            await service.process_single_episode(inserted, status_message=status_msg)

            updated_ep = await EpisodeRepository.find_by_id(inserted.id)
            if updated_ep and updated_ep.telegram_file_id:
                await client.send_video(
                    chat_id=callback_query.message.chat.id,
                    video=updated_ep.telegram_file_id,
                    caption=format_main_caption(
                        show_name=updated_ep.show_name,
                        episode_number=updated_ep.episode_number,
                        episode_date=updated_ep.episode_date
                    )
                )
                await status_msg.edit_text(f"🎉 **Download & Upload Complete!**\n\n**{inserted.show_name}** has been delivered above. 🚀")
            else:
                await status_msg.edit_text(f"✅ Successfully processed **{inserted.show_name}** - Ep {inserted.episode_number}!")
        except Exception as e:
            logger.error(f"Error processing single latest episode: {e}", exc_info=True)
            await status_msg.edit_text(f"❌ Upload failed: {e}")

    @app.on_callback_query(filters.regex(r"^up_all$") & admin_filter())
    async def upload_all_latest_callback(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        from app.telegram.handlers import _latest_cache

        episodes = _latest_cache.get(user_id)
        if not episodes:
            await callback_query.answer("❌ Session expired. Please run /latest again.", show_alert=True)
            return

        await callback_query.answer("Starting batch upload of all latest episodes...", show_alert=False)
        status_msg = await callback_query.message.reply_text(f"🚀 Batch uploading {len(episodes)} latest episodes...")

        from app.database.repositories import EpisodeRepository, ShowRepository
        from app.database.models import EpisodeModel, EpisodeStatus
        from app.services.episode_service import EpisodeService

        service = EpisodeService()
        success_count = 0

        for item in episodes:
            try:
                existing = await EpisodeRepository.find_duplicate(source_url=item.episode_url, canonical_id=item.canonical_id)
                if existing:
                    continue

                show = await ShowRepository.get_or_create(name=item.show_name, normalized_name=item.normalized_show_name, poster_url=item.poster_url)
                ep_model = EpisodeModel(
                    show_name=item.show_name,
                    normalized_show_name=item.normalized_show_name,
                    episode_number=item.episode_number,
                    episode_title=item.episode_title,
                    episode_date=item.episode_date,
                    source_url=item.episode_url,
                    poster_url=item.poster_url or show.poster_url,
                    media_url=item.media_url,
                    source=item.source,
                    canonical_id=item.canonical_id,
                    status=EpisodeStatus.DETECTED
                )

                inserted = await EpisodeRepository.insert(ep_model)
                await service.process_single_episode(inserted)
                success_count += 1
            except Exception as e:
                logger.error(f"Batch upload error for {item.show_name}: {e}")

        await status_msg.edit_text(f"✅ Batch upload completed! Successfully uploaded {success_count} new episodes.")

    @app.on_message(filters.command("start") & admin_filter())
    async def admin_start_handler(client: Client, message: Message):
        args = message.command
        if len(args) > 1 and args[1].startswith("get_"):
            ep_id = args[1].replace("get_", "")
            await send_file_to_user(client, message.chat.id, ep_id)
            return

        await message.reply_text(Script.ADMIN_START_TXT)

    @app.on_message(filters.command("help") & admin_filter())
    async def admin_help_handler(client: Client, message: Message):
        await admin_start_handler(client, message)

    @app.on_message(filters.command("status") & admin_filter())
    async def status_handler(client: Client, message: Message):
        counts = await EpisodeRepository.count_by_status()
        scraper_enabled = await SettingsRepository.get_setting("scraper_enabled", True)
        
        status_text = (
            "📊 **System Status**\n\n"
            f"• Scraper Status: {'🟢 ENABLED' if scraper_enabled else '🔴 PAUSED'}\n"
            f"• Detected Episodes: {counts.get('DETECTED', 0)}\n"
            f"• Downloading: {counts.get('DOWNLOADING', 0)}\n"
            f"• Uploaded (Main): {counts.get('UPLOADED', 0)}\n"
            f"• Pending Archive: {counts.get('ARCHIVE_PENDING', 0)}\n"
            f"• Archived: {counts.get('ARCHIVED', 0)}\n"
            f"• Deleted from Main: {counts.get('DELETED_FROM_MAIN', 0)}\n"
            f"• Failed: {counts.get('FAILED', 0)}\n"
        )
        await message.reply_text(status_text)

    @app.on_message(filters.command("scan") & admin_filter())
    async def scan_handler(client: Client, message: Message):
        msg = await message.reply_text("🔄 Initiating manual scraper scan...")
        from app.services.episode_service import EpisodeService
        service = EpisodeService()
        new_count = await service.run_scraper_pipeline()
        await msg.edit_text(f"✅ Scan completed. Ingested {new_count} new episodes.")

    @app.on_message(filters.command("recheck") & admin_filter())
    async def recheck_handler(client: Client, message: Message):
        msg = await message.reply_text("🔄 Re-checking missing episodes and processing pipeline...")
        from app.services.episode_service import EpisodeService
        service = EpisodeService()
        await service.process_detected_episodes()
        await msg.edit_text("✅ Pipeline re-check completed.")

    @app.on_message(filters.command("pause") & admin_filter())
    async def pause_handler(client: Client, message: Message):
        await SettingsRepository.set_setting("scraper_enabled", False)
        await message.reply_text("⏸ Automatic scraping and processing PAUSED.")

    @app.on_message(filters.command("resume") & admin_filter())
    async def resume_handler(client: Client, message: Message):
        await SettingsRepository.set_setting("scraper_enabled", True)
        await message.reply_text("▶️ Automatic scraping and processing RESUMED.")

    @app.on_message(filters.command("retry") & admin_filter())
    async def retry_handler(client: Client, message: Message):
        msg = await message.reply_text("🔄 Retrying failed episodes...")
        from app.services.retry_service import RetryService
        count = await RetryService.retry_failed_episodes()
        await msg.edit_text(f"✅ Retried {count} failed episodes.")

    @app.on_message(filters.command("cleanup") & admin_filter())
    async def cleanup_command_handler(client: Client, message: Message):
        from app.media.cleanup import cleanup_directory
        removed = cleanup_directory()
        await message.reply_text(f"🧹 Temporary storage cleaned. Removed {removed} files.")

    @app.on_message(filters.command("stats") & admin_filter())
    async def stats_handler(client: Client, message: Message):
        counts = await EpisodeRepository.count_by_status()
        total = sum(counts.values())
        stats_text = "📈 **MongoDB Database Statistics**\n\n"
        stats_text += f"Total Episodes Recorded: {total}\n"
        for status_val, cnt in counts.items():
            stats_text += f"• {status_val}: {cnt}\n"
        await message.reply_text(stats_text)

    @app.on_message(filters.command("search") & admin_filter())
    async def search_handler(client: Client, message: Message):
        args = message.command
        if len(args) < 2:
            await message.reply_text("Usage: `/search <show or title>`")
            return

        query_text = " ".join(args[1:])
        episodes = await EpisodeRepository.search(query_text, limit=10)

        if not episodes:
            await message.reply_text(f"🔍 No episodes found matching `{query_text}`.")
            return

        res_text = f"🔍 **Search Results for:** `{query_text}`\n\n"
        for ep in episodes:
            res_text += f"• **{ep.show_name}** - Ep {ep.episode_number} ({ep.episode_date}) [{ep.status.value}]\n"
        await message.reply_text(res_text)
