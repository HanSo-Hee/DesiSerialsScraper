# github.com/MrAbhi2k3

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId
from app.database.mongodb import MongoDB
from app.database.models import EpisodeModel, EpisodeStatus, ShowModel

logger = logging.getLogger(__name__)


def _doc_to_episode(doc: Dict[str, Any]) -> EpisodeModel:
    doc_copy = dict(doc)
    doc_copy["id"] = str(doc_copy.pop("_id"))
    if "status" in doc_copy and isinstance(doc_copy["status"], str):
        doc_copy["status"] = EpisodeStatus(doc_copy["status"])
    return EpisodeModel(**doc_copy)


def _episode_to_doc(ep: EpisodeModel) -> Dict[str, Any]:
    doc = {
        "show_name": ep.show_name,
        "normalized_show_name": ep.normalized_show_name,
        "episode_number": ep.episode_number,
        "episode_title": ep.episode_title,
        "episode_date": ep.episode_date,
        "source_url": ep.source_url,
        "poster_url": ep.poster_url,
        "media_url": ep.media_url,
        "source": ep.source,
        "canonical_id": ep.canonical_id,
        "status": ep.status.value if isinstance(ep.status, EpisodeStatus) else ep.status,
        "telegram_main_message_id": ep.telegram_main_message_id,
        "telegram_archive_message_id": ep.telegram_archive_message_id,
        "telegram_history_message_id": ep.telegram_history_message_id,
        "telegram_file_id": ep.telegram_file_id,
        "telegram_file_unique_id": ep.telegram_file_unique_id,
        "media_type": ep.media_type,
        "file_name": ep.file_name,
        "file_size": ep.file_size,
        "duration": ep.duration,
        "uploaded_at": ep.uploaded_at,
        "archive_due_at": ep.archive_due_at,
        "archived_at": ep.archived_at,
        "deleted_at": ep.deleted_at,
        "retry_count": ep.retry_count,
        "last_error": ep.last_error,
        "created_at": ep.created_at,
        "updated_at": ep.updated_at,
    }
    return doc


class EpisodeRepository:
    @staticmethod
    def collection():
        return MongoDB.get_db().episodes

    @classmethod
    async def find_by_url(cls, source_url: str) -> Optional[EpisodeModel]:
        doc = await cls.collection().find_one({"source_url": source_url})
        return _doc_to_episode(doc) if doc else None

    @classmethod
    async def find_by_canonical(cls, canonical_id: str) -> Optional[EpisodeModel]:
        doc = await cls.collection().find_one({"canonical_id": canonical_id})
        return _doc_to_episode(doc) if doc else None

    @classmethod
    async def find_by_id(cls, episode_id: str) -> Optional[EpisodeModel]:
        try:
            doc = await cls.collection().find_one({"_id": ObjectId(episode_id)})
            return _doc_to_episode(doc) if doc else None
        except Exception:
            return None

    @classmethod
    async def find_duplicate(cls, source_url: str, canonical_id: str) -> Optional[EpisodeModel]:
        doc = await cls.collection().find_one({
            "$or": [
                {"source_url": source_url},
                {"canonical_id": canonical_id}
            ]
        })
        return _doc_to_episode(doc) if doc else None

    @classmethod
    async def insert(cls, episode: EpisodeModel) -> EpisodeModel:
        doc = _episode_to_doc(episode)
        result = await cls.collection().insert_one(doc)
        episode.id = str(result.inserted_id)
        return episode

    @classmethod
    async def try_acquire_lock(cls, episode_id: str, current_status: EpisodeStatus, target_status: EpisodeStatus) -> bool:
        """Atomic state transition lock to prevent race conditions across workers."""
        now = datetime.now(timezone.utc)
        result = await cls.collection().update_one(
            {
                "_id": ObjectId(episode_id),
                "status": current_status.value
            },
            {
                "$set": {
                    "status": target_status.value,
                    "updated_at": now
                }
            }
        )
        return result.modified_count > 0

    @classmethod
    async def update_status(cls, episode_id: str, status: EpisodeStatus, **kwargs) -> bool:
        now = datetime.now(timezone.utc)
        update_doc = {"status": status.value, "updated_at": now}
        for k, v in kwargs.items():
            update_doc[k] = v

        result = await cls.collection().update_one(
            {"_id": ObjectId(episode_id)},
            {"$set": update_doc}
        )
        return result.modified_count > 0

    @classmethod
    async def record_error(cls, episode_id: str, error_msg: str, status: EpisodeStatus = EpisodeStatus.FAILED):
        now = datetime.now(timezone.utc)
        await cls.collection().update_one(
            {"_id": ObjectId(episode_id)},
            {
                "$set": {
                    "status": status.value,
                    "last_error": error_msg,
                    "updated_at": now
                },
                "$inc": {"retry_count": 1}
            }
        )

    @classmethod
    async def get_due_for_archive(cls, now: datetime) -> List[EpisodeModel]:
        cursor = cls.collection().find({
            "status": EpisodeStatus.ARCHIVE_PENDING.value,
            "archive_due_at": {"$lte": now}
        })
        episodes = []
        async for doc in cursor:
            episodes.append(_doc_to_episode(doc))
        return episodes

    @classmethod
    async def get_by_status(cls, status: EpisodeStatus, limit: int = 100) -> List[EpisodeModel]:
        cursor = cls.collection().find({"status": status.value}).limit(limit)
        episodes = []
        async for doc in cursor:
            episodes.append(_doc_to_episode(doc))
        return episodes

    @classmethod
    async def get_failed_episodes(cls, max_retries: int = 3) -> List[EpisodeModel]:
        cursor = cls.collection().find({
            "status": EpisodeStatus.FAILED.value,
            "retry_count": {"$lt": max_retries}
        })
        episodes = []
        async for doc in cursor:
            episodes.append(_doc_to_episode(doc))
        return episodes

    @classmethod
    async def count_by_status(cls) -> Dict[str, int]:
        pipeline = [
            {"$group": {"_id": "$status", "count": {"$sum": 1}}}
        ]
        counts = {}
        cursor = cls.collection().aggregate(pipeline)
        async for doc in cursor:
            counts[doc["_id"]] = doc["count"]
        return counts

    @classmethod
    async def search(cls, query_text: str, limit: int = 20) -> List[EpisodeModel]:
        regex_pattern = {"$regex": query_text, "$options": "i"}
        cursor = cls.collection().find({
            "$or": [
                {"show_name": regex_pattern},
                {"episode_title": regex_pattern},
                {"episode_number": regex_pattern}
            ]
        }).limit(limit)
        episodes = []
        async for doc in cursor:
            episodes.append(_doc_to_episode(doc))
        return episodes


class ShowRepository:
    @staticmethod
    def collection():
        return MongoDB.get_db().shows

    @classmethod
    async def get_or_create(cls, name: str, normalized_name: str, poster_url: Optional[str] = None) -> ShowModel:
        now = datetime.now(timezone.utc)
        doc = await cls.collection().find_one({"normalized_name": normalized_name})
        if doc:
            if poster_url and not doc.get("poster_url"):
                await cls.collection().update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"poster_url": poster_url, "updated_at": now}}
                )
                doc["poster_url"] = poster_url
            doc_copy = dict(doc)
            doc_copy["id"] = str(doc_copy.pop("_id"))
            return ShowModel(**doc_copy)

        new_show = ShowModel(
            name=name,
            normalized_name=normalized_name,
            poster_url=poster_url,
            created_at=now,
            updated_at=now
        )
        insert_doc = {
            "name": new_show.name,
            "normalized_name": new_show.normalized_name,
            "poster_url": new_show.poster_url,
            "created_at": new_show.created_at,
            "updated_at": new_show.updated_at
        }
        res = await cls.collection().insert_one(insert_doc)
        new_show.id = str(res.inserted_id)
        return new_show


class SettingsRepository:
    @staticmethod
    def collection():
        return MongoDB.get_db().settings

    @classmethod
    async def get_setting(cls, key: str, default: Any = None) -> Any:
        doc = await cls.collection().find_one({"key": key})
        if doc:
            return doc.get("value", default)
        return default

    @classmethod
    async def set_setting(cls, key: str, value: Any):
        await cls.collection().update_one(
            {"key": key},
            {"$set": {"key": key, "value": value, "updated_at": datetime.now(timezone.utc)}},
            upsert=True
        )


class LogRepository:
    @staticmethod
    def collection():
        return MongoDB.get_db().logs

    @classmethod
    async def log_event(cls, event: str, message: str, episode_id: Optional[str] = None, level: str = "INFO"):
        doc = {
            "event": event,
            "message": message,
            "episode_id": episode_id,
            "level": level,
            "created_at": datetime.now(timezone.utc)
        }
        await cls.collection().insert_one(doc)
