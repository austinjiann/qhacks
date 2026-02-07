import asyncio
import base64
import json
import time
from typing import Optional

import aiohttp
import firebase_admin
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from firebase_admin import credentials, firestore
from openai import AsyncOpenAI

from utils.env import settings

KALSHI_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

if not firebase_admin._apps:
    cred = credentials.Certificate("qhacks-486618-firebase-adminsdk-fbsvc-6ae4974082.json")
    firebase_admin.initialize_app(cred)

SPORTS_CRYPTO_SERIES = {
    "bitcoin": "KXBTC", "btc": "KXBTC", "crypto": "KXBTC",
    "ethereum": "KXETH", "eth": "KXETH",
    "xrp": "KXXRP",
    "super bowl": "KXSB", "superbowl": "KXSB",
    "nfl": "KXSB", "patriots": "KXSB", "chiefs": "KXSB", "eagles": "KXSB", "seahawks": "KXSB",
    "nba": "KXNBAGAME", "basketball": "KXNBAGAME",
    "lakers": "KXNBAGAME", "celtics": "KXNBAGAME", "warriors": "KXNBAGAME",
    "mlb": "KXMLBGAME", "baseball": "KXMLBGAME",
    "nhl": "KXNHLGAME", "hockey": "KXNHLGAME",
    "world cup": "KXWCGAME", "fifa": "KXWCGAME", "soccer": "KXWCGAME",
    "s&p": "KXINX", "nasdaq": "KXINX", "dow": "KXINX",
}


class FeedService:
    def __init__(self):
        self.openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.youtube_api_key = settings.YOUTUBE_API_KEY
        self.kalshi_api_key = settings.KALSHI_API_KEY
        self.kalshi_private_key = self._load_private_key()
        self.db = firestore.client()
        self.cache_collection = self.db.collection("video_matches")

    def _load_private_key(self):
        with open(settings.KALSHI_PRIVATE_KEY_PATH, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)

    def _sign_kalshi_request(self, method: str, path: str, timestamp_ms: int) -> str:
        message = f"{timestamp_ms}{method}{path}"
        signature = self.kalshi_private_key.sign(
            message.encode("utf-8"),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode("utf-8")

    def _get_kalshi_headers(self, method: str, path: str) -> dict:
        timestamp_ms = int(time.time() * 1000)
        signature = self._sign_kalshi_request(method, path, timestamp_ms)
        return {
            "KALSHI-ACCESS-KEY": self.kalshi_api_key,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": str(timestamp_ms),
            "Content-Type": "application/json",
        }

    async def _get_events(self, status: str = "open", limit: int = 200) -> list[dict]:
        path = "/trade-api/v2/events"
        params = {"status": status, "limit": limit, "with_nested_markets": "true"}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{KALSHI_BASE_URL}/events",
                params=params,
                headers=self._get_kalshi_headers("GET", path),
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("events", [])

    async def _get_markets_for_event(
        self, event_ticker: str, status: str = "open", limit: int = 50
    ) -> list[dict]:
        path = "/trade-api/v2/markets"
        params = {"status": status, "limit": limit, "event_ticker": event_ticker}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{KALSHI_BASE_URL}/markets",
                params=params,
                headers=self._get_kalshi_headers("GET", path),
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("markets", [])

    async def _get_markets_by_series(
        self, series_ticker: str, status: str = "open", limit: int = 50
    ) -> list[dict]:
        path = "/trade-api/v2/markets"
        params = {"status": status, "limit": limit, "series_ticker": series_ticker}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{KALSHI_BASE_URL}/markets",
                params=params,
                headers=self._get_kalshi_headers("GET", path),
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("markets", [])

    def _detect_series_from_keywords(self, keywords: list[str]) -> Optional[str]:
        keywords_lower = " ".join(keywords).lower()
        priority_terms = ["world cup", "fifa", "soccer", "super bowl", "bitcoin", "btc", "crypto"]
        for term in priority_terms:
            if term in keywords_lower and term in SPORTS_CRYPTO_SERIES:
                return SPORTS_CRYPTO_SERIES[term]
        for term, series in SPORTS_CRYPTO_SERIES.items():
            if term in keywords_lower:
                return series
        return None

    async def _get_event(self, event_ticker: str) -> dict:
        path = f"/trade-api/v2/events/{event_ticker}"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{KALSHI_BASE_URL}/events/{event_ticker}",
                headers=self._get_kalshi_headers("GET", path),
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("event", {})

    async def get_video_metadata(self, video_id: str) -> dict:
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {"part": "snippet", "id": video_id, "key": self.youtube_api_key}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()

        if not data.get("items"):
            return {"title": "", "description": "", "channel": "", "thumbnail": ""}

        snippet = data["items"][0]["snippet"]
        return {
            "title": snippet.get("title", ""),
            "description": snippet.get("description", "")[:500],
            "channel": snippet.get("channelTitle", ""),
            "thumbnail": (
                snippet.get("thumbnails", {}).get("maxres", {}).get("url")
                or snippet.get("thumbnails", {}).get("high", {}).get("url", "")
            ),
        }

    async def _extract_keywords(self, title: str, description: str) -> list[str]:
        prompt = f"""Extract 3-5 keywords from this YouTube video that could match prediction market bets.
Focus on: sports teams/players, political figures, companies, events, weather phenomena, cryptocurrency.
Return ONLY comma-separated keywords, no explanation.

Title: {title}
Description: {description[:500]}"""

        response = await self.openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        keywords_str = response.choices[0].message.content.strip()
        return [k.strip() for k in keywords_str.split(",") if k.strip()]

    async def _match_keywords_to_events(
        self, keywords: list[str], events: list[dict]
    ) -> Optional[int]:
        event_titles = [
            f"{i}: {e.get('title', 'Unknown')}"
            for i, e in enumerate(events)
        ]
        event_list = "\n".join(event_titles)
        keywords_str = ", ".join(keywords)

        prompt = f"""Match video keywords to the BEST prediction market event.

Video keywords: {keywords_str}

Available events:
{event_list}

Return ONLY a single integer index (0-based) of the best matching event.
Pick the event most closely related to the video topic.
If nothing matches well, return 0.

Return ONLY the number, nothing else."""

        response = await self.openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        try:
            result = response.choices[0].message.content.strip()
            return int(result)
        except (ValueError, TypeError):
            return 0

    async def _format_market_display(
        self, market: dict, event: dict, keywords: list[str]
    ) -> dict:
        event_title = event.get("title", "")
        yes_sub_title = market.get("yes_sub_title", "")
        rules = market.get("rules_primary", "")
        keywords_str = ", ".join(keywords)

        prompt = f"""Format this Kalshi prediction market for display.

Event: {event_title}
Outcome text: {yes_sub_title}
Rules: {rules}
Video keywords: {keywords_str}

Create a clean, user-friendly bet display:
1. "question": A clear, concise yes/no question about this bet (e.g., "Will Arsenal win today?")
2. "outcome": The single most relevant team/item/subject from the outcome text based on the video keywords (e.g., "Arsenal"). Just the name, no "yes" prefix.

Return JSON only: {{"question": "...", "outcome": "..."}}"""

        try:
            response = await self.openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content)
        except Exception:
            return {
                "question": event_title or yes_sub_title,
                "outcome": yes_sub_title.split(",")[0].replace("yes ", "") if yes_sub_title else "",
            }

    def _get_cached(self, video_id: str) -> Optional[dict]:
        try:
            doc = self.cache_collection.document(video_id).get()
            if doc.exists:
                return doc.to_dict()
        except Exception as e:
            print(f"[{video_id}] Cache read error: {e}")
        return None

    def _set_cached(self, video_id: str, data: dict) -> None:
        try:
            self.cache_collection.document(video_id).set(data)
        except Exception as e:
            print(f"[{video_id}] Cache write error: {e}")

    async def match_video(self, video_id: str) -> Optional[dict]:
        cached = self._get_cached(video_id)
        if cached:
            print(f"[{video_id}] Cache hit")
            return cached

        print(f"[{video_id}] Starting match...")
        metadata = await self.get_video_metadata(video_id)
        print(f"[{video_id}] Title: {metadata.get('title', 'No title')}")
        
        keywords = await self._extract_keywords(metadata["title"], metadata["description"])
        print(f"[{video_id}] Keywords: {keywords}")

        if not keywords:
            print(f"[{video_id}] FAILED: No keywords extracted")
            return None

        series = self._detect_series_from_keywords(keywords)
        best_event = {}
        
        if series:
            print(f"[{video_id}] Detected series: {series}")
            markets = await self._get_markets_by_series(series, limit=50)
            print(f"[{video_id}] Markets from series: {len(markets)}")
            if markets:
                best_market = markets[0]
                event_ticker = best_market.get("event_ticker", "")
                if event_ticker:
                    try:
                        best_event = await self._get_event(event_ticker)
                    except Exception:
                        pass
                print(f"[{video_id}] SUCCESS (series) - Market: {best_market.get('ticker')}")
                formatted = await self._format_market_display(best_market, best_event, keywords)
                result = {
                    "youtube": {
                        "video_id": video_id,
                        "title": metadata["title"],
                        "thumbnail": metadata["thumbnail"],
                        "channel": metadata["channel"],
                    },
                    "kalshi": {
                        "ticker": best_market.get("ticker"),
                        "question": formatted.get("question", ""),
                        "outcome": formatted.get("outcome", ""),
                        "yes_price": best_market.get("yes_bid", 0),
                        "no_price": best_market.get("no_bid", 0),
                        "volume": best_market.get("volume", 0),
                    },
                    "keywords": keywords,
                }
                self._set_cached(video_id, result)
                return result

        events = await self._get_events(status="open", limit=200)
        print(f"[{video_id}] Events fetched: {len(events)}")
        
        if not events:
            print(f"[{video_id}] FAILED: No events returned")
            return None

        event_idx = await self._match_keywords_to_events(keywords, events)
        print(f"[{video_id}] Matched event index: {event_idx}")
        
        if event_idx is None or event_idx >= len(events):
            event_idx = 0
        
        best_event = events[event_idx]
        print(f"[{video_id}] Matched event: {best_event.get('title', 'Unknown')}")
        
        markets = best_event.get("markets", [])
        if not markets:
            markets = await self._get_markets_for_event(best_event.get("event_ticker", ""))
        
        if not markets:
            print(f"[{video_id}] FAILED: No markets for event")
            return None
        
        best_market = markets[0]
        print(f"[{video_id}] SUCCESS (event) - Market: {best_market.get('ticker')}")
        formatted = await self._format_market_display(best_market, best_event, keywords)

        result = {
            "youtube": {
                "video_id": video_id,
                "title": metadata["title"],
                "thumbnail": metadata["thumbnail"],
                "channel": metadata["channel"],
            },
            "kalshi": {
                "ticker": best_market.get("ticker"),
                "question": formatted.get("question", ""),
                "outcome": formatted.get("outcome", ""),
                "yes_price": best_market.get("yes_bid", 0),
                "no_price": best_market.get("no_bid", 0),
                "volume": best_market.get("volume", 0),
            },
            "keywords": keywords,
        }
        self._set_cached(video_id, result)
        return result

    async def get_feed(self, video_ids: list[str]) -> list[dict]:
        tasks = [self.match_video(vid) for vid in video_ids]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r]
