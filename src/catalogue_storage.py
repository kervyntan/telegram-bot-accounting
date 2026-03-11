"""MongoDB storage for catalogue listings (public card search bot)."""

import re
from datetime import datetime
from typing import Any

from pymongo import MongoClient, TEXT
from pymongo.collection import Collection
from pymongo.database import Database

# Status detection patterns
_SOLD_RE = re.compile(r"\b(sold|gone)\b", re.IGNORECASE)
_RESERVED_RE = re.compile(r"\b(claimed|reserved|pending|taken)\b", re.IGNORECASE)


def _detect_status(text: str) -> str:
    """Infer listing status from message text."""
    if _SOLD_RE.search(text):
        return "sold"
    if _RESERVED_RE.search(text):
        return "reserved"
    return "available"


class CatalogueStorage:
    """Store and search card listing messages indexed from group chats."""

    def __init__(self, mongo_uri: str, database_name: str = "telegram_bot") -> None:
        self.client = MongoClient(mongo_uri)
        self.db: Database = self.client[database_name]
        self.listings: Collection = self.db["catalogue_listings"]
        self.searches: Collection = self.db["catalogue_searches"]

        # Full-text search index on listing text
        self.listings.create_index([("text", TEXT)])
        # Unique index so upsert matches correctly
        self.listings.create_index(
            [("chat_id", 1), ("message_id", 1)], unique=True
        )
        self.listings.create_index("status")

    def upsert_listing(
        self,
        chat_id: int,
        message_id: int,
        sender_id: int,
        sender_name: str,
        text: str,
    ) -> None:
        """Insert or update a listing from a group message."""
        status = _detect_status(text)
        now = datetime.utcnow()
        self.listings.update_one(
            {"chat_id": chat_id, "message_id": message_id},
            {
                "$set": {
                    "sender_id": sender_id,
                    "sender_name": sender_name,
                    "text": text,
                    "status": status,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    def mark_edited(self, chat_id: int, message_id: int, new_text: str) -> None:
        """Re-detect status after a message edit."""
        status = _detect_status(new_text)
        self.listings.update_one(
            {"chat_id": chat_id, "message_id": message_id},
            {
                "$set": {
                    "text": new_text,
                    "status": status,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Full-text search over available listings, ranked by relevance."""
        cursor = (
            self.listings.find(
                {"$text": {"$search": query}, "status": "available"},
                {"score": {"$meta": "textScore"}},
            )
            .sort([("score", {"$meta": "textScore"})])
            .limit(limit)
        )
        return list(cursor)

    def log_search(self, user_id: int, user_name: str, query: str) -> None:
        """Record every search for owner analytics."""
        self.searches.insert_one(
            {
                "user_id": user_id,
                "user_name": user_name,
                "query": query,
                "timestamp": datetime.utcnow(),
            }
        )
