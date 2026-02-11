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
        active_ids = await self.get_all_active_video_ids()
        if exclude_ids:
            active_ids = [vid for vid in active_ids if vid not in exclude_ids]
        if not active_ids:
            return []
        sampled = random.sample(active_ids, min(count, len(active_ids)))
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

    async def get_all_active_video_ids(self) -> list[str]:
        query = self.db.collection("feed_pool").where("active", "==", True).select([])
        docs = await query.get()
        return [doc.id for doc in docs]

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
