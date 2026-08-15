# github.com/MrAbhi2k3

import logging
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import get_settings

logger = logging.getLogger(__name__)


class MongoDB:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None

    @classmethod
    async def connect(cls, uri: Optional[str] = None, db_name: Optional[str] = None):
        settings = get_settings()
        uri = uri or settings.MONGO_URI
        db_name = db_name or settings.MONGO_DB_NAME

        logger.info(f"Connecting to MongoDB database: {db_name}")
        cls.client = AsyncIOMotorClient(uri)
        cls.db = cls.client[db_name]

        # Ping database to confirm connection
        await cls.client.admin.command('ping')
        logger.info("MongoDB connected successfully.")

        await cls._create_indexes()

    @classmethod
    async def _create_indexes(cls):
        if cls.db is None:
            return

        # Indexes for episodes collection
        episodes = cls.db.episodes
        await episodes.create_index("source_url", unique=True)
        await episodes.create_index("canonical_id", unique=True, sparse=True)
        await episodes.create_index([("normalized_show_name", 1), ("episode_number", 1), ("episode_date", 1)])
        await episodes.create_index("status")
        await episodes.create_index("archive_due_at")
        await episodes.create_index("telegram_file_unique_id", sparse=True)
        await episodes.create_index("created_at")

        # Indexes for shows collection
        shows = cls.db.shows
        await shows.create_index("normalized_name", unique=True)

        # Indexes for settings and logs collections
        settings_col = cls.db.settings
        await settings_col.create_index("key", unique=True)

        logs_col = cls.db.logs
        await logs_col.create_index("created_at")

        logger.info("MongoDB indexes created/verified successfully.")

    @classmethod
    async def close(cls):
        if cls.client:
            cls.client.close()
            cls.client = None
            cls.db = None
            logger.info("MongoDB connection closed.")

    @classmethod
    def get_db(cls) -> AsyncIOMotorDatabase:
        if cls.db is None:
            raise RuntimeError("Database not initialized. Call MongoDB.connect() first.")
        return cls.db
