import random
from datetime import datetime, timezone, timedelta
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore_async
from google.cloud.firestore_v1 import AsyncClient
from google.cloud.firestore_v1 import query as firestore_query


class FirestoreService:
    def __init__(self) -> None:
        if not firebase_admin._apps:
            import os
            cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            if cred_path and os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
            else:
                firebase_admin.initialize_app()
        self.db: AsyncClient = firestore_async.client()

    # ── feed_pool CRUD ──

    async def get_random_feed_items(self, count: int = 10, exclude_ids: Optional[set[str]] = None) -> list[dict]:
        active_items = await self._get_all_active_ids_with_channel()
        if exclude_ids:
            active_items = [(vid, ch) for vid, ch in active_items if vid not in exclude_ids]
        if not active_items:
            return []

        # Group by channel for diversity sampling
        by_channel: dict[str, list[str]] = {}
        for vid, channel in active_items:
            by_channel.setdefault(channel, []).append(vid)

        # Shuffle within each channel group
        for ids in by_channel.values():
            random.shuffle(ids)

        # Round-robin across channels
        sampled: list[str] = []
        channels = list(by_channel.keys())
        random.shuffle(channels)
        while len(sampled) < count and channels:
            next_channels = []
            for ch in channels:
                if len(sampled) >= count:
                    break
                ids = by_channel[ch]
                if ids:
                    sampled.append(ids.pop())
                if ids:
                    next_channels.append(ch)
            channels = next_channels

        if not sampled:
            return []

        items: list[dict] = []
        # Firestore 'in' queries max 30 per batch
        for i in range(0, len(sampled), 30):
            batch_ids = sampled[i : i + 30]
            docs = await self.db.collection("feed_pool").where("__name__", "in",
                [self.db.collection("feed_pool").document(vid) for vid in batch_ids]
            ).get()
            for doc in docs:
                data = doc.to_dict()
                data["_doc_id"] = doc.id
                items.append(data)

        # Preserve the round-robin ordering
        order = {vid: idx for idx, vid in enumerate(sampled)}
        items.sort(key=lambda d: order.get(d.get("_doc_id", ""), len(sampled)))
        return items

    async def upsert_feed_item(self, video_id: str, data: dict) -> None:
        ref = self.db.collection("feed_pool").document(video_id)
        await ref.set({**data, "active": True}, merge=True)

    async def deactivate_stale_items(self, max_age_hours: int = 24) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        query = (
            self.db.collection("feed_pool")
            .where("active", "==", True)
            .where("crawled_at", "<", cutoff)
        )
        docs = await query.get()
        count = 0
        for doc in docs:
            await doc.reference.update({"active": False})
            count += 1
        return count

    async def reactivate_all_items(self) -> int:
        query = self.db.collection("feed_pool").where("active", "==", False)
        docs = await query.get()
        count = 0
        for doc in docs:
            await doc.reference.update({"active": True})
            count += 1
        return count

    async def purge_all_items(self) -> int:
        docs = await self.db.collection("feed_pool").select([]).get()
        count = 0
        for doc in docs:
            await doc.reference.delete()
            count += 1
        return count

    async def deactivate_by_keywords(self, match_keywords: list[str]) -> int:
        """Deactivate all active feed items whose keywords overlap with match_keywords."""
        match_lower = {k.lower() for k in match_keywords}
        query = self.db.collection("feed_pool").where("active", "==", True)
        docs = await query.get()
        count = 0
        for doc in docs:
            data = doc.to_dict() or {}
            item_keywords = [k.lower() for k in data.get("keywords", [])]
            if any(k in match_lower for k in item_keywords):
                await doc.reference.update({"active": False})
                count += 1
        return count

    async def deactivate_feed_item(self, video_id: str) -> bool:
        ref = self.db.collection("feed_pool").document(video_id)
        doc = await ref.get()
        if not doc.exists:
            return False
        await ref.update({"active": False})
        return True

    async def get_all_active_video_ids(self) -> list[str]:
        query = self.db.collection("feed_pool").where("active", "==", True).select([])
        docs = await query.get()
        return [doc.id for doc in docs]

    async def _get_all_active_ids_with_channel(self) -> list[tuple[str, str]]:
        query = self.db.collection("feed_pool").where("active", "==", True).select(["channel"])
        docs = await query.get()
        return [(doc.id, (doc.to_dict() or {}).get("channel", "")) for doc in docs]

    # ── generated_videos CRUD ──

    async def store_generated_video(self, job_id: str, data: dict) -> None:
        ref = self.db.collection("generated_videos").document(job_id)
        await ref.set({**data, "job_id": job_id, "consumed": False, "created_at": datetime.now(timezone.utc)})

    async def get_unconsumed_generated_videos(self) -> list[dict]:
        query = (
            self.db.collection("generated_videos")
            .where("consumed", "==", False)
            .order_by("created_at")
            .limit(20)
        )
        docs = await query.get()
        return [{"_doc_id": doc.id, **doc.to_dict()} for doc in docs]

    async def mark_consumed(self, job_id: str) -> None:
        ref = self.db.collection("generated_videos").document(job_id)
        await ref.update({"consumed": True})

    # ── crawler_state ──

    async def update_crawler_state(self, status: str, videos_added: int = 0) -> None:
        ref = self.db.collection("crawler_state").document("latest")
        await ref.set({
            "last_run_at": datetime.now(timezone.utc),
            "videos_added": videos_added,
            "status": status,
        })

    async def get_crawler_state(self) -> Optional[dict]:
        ref = self.db.collection("crawler_state").document("latest")
        doc = await ref.get()
        return doc.to_dict() if doc.exists else None

    # ── stats ──

    async def get_pool_stats(self) -> dict:
        active_ids = await self.get_all_active_video_ids()
        crawler_state = await self.get_crawler_state()
        unconsumed = await self.get_unconsumed_generated_videos()
        return {
            "pool_size": len(active_ids),
            "generated_pending": len(unconsumed),
            "crawler": crawler_state,
        }

    # ── list pool items ──

    async def list_pool_items(self, limit: int = 50) -> list[dict]:
        query = (
            self.db.collection("feed_pool")
            .where("active", "==", True)
            .order_by("crawled_at", direction=firestore_query.Query.DESCENDING)
            .limit(limit)
        )
        docs = await query.get()
        items = []
        for doc in docs:
            data = doc.to_dict()
            data["video_id"] = doc.id
            items.append(data)
        return items
