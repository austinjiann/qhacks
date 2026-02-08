import asyncio
import base64
import json
import re
import time
from datetime import datetime, timezone
from typing import Optional

import aiohttp
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from openai import AsyncOpenAI

from utils.env import settings

KALSHI_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

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
        self._kalshi_semaphore = asyncio.Semaphore(5)
        self._session: aiohttp.ClientSession | None = None

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

    @staticmethod
    def _to_float(value: object) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _to_cents(cls, cents_value: object = None, dollars_value: object = None) -> Optional[float]:
        cents = cls._to_float(cents_value)
        if cents is not None:
            return cents
        dollars = cls._to_float(dollars_value)
        if dollars is None:
            return None
        return dollars * 100

    @classmethod
    def _extract_candle_close_cents(cls, candle: dict) -> Optional[float]:
        for key in ("price", "yes_bid"):
            payload = candle.get(key, {})
            if isinstance(payload, dict):
                close_cents = cls._to_cents(payload.get("close"), payload.get("close_dollars"))
                if close_cents is not None:
                    return close_cents

        synthetic_previous = cls._to_cents(
            candle.get("previous_price"), candle.get("previous_price_dollars")
        )
        if synthetic_previous is not None:
            return synthetic_previous

        price_payload = candle.get("price", {})
        if isinstance(price_payload, dict):
            previous = cls._to_cents(
                price_payload.get("previous"), price_payload.get("previous_dollars")
            )
            if previous is not None:
                return previous

        return None

    @staticmethod
    def _parse_iso_timestamp(value: object) -> Optional[int]:
        if value is None:
            return None

        if isinstance(value, (int, float)):
            numeric = float(value)
            if numeric <= 0:
                return None
            return int(numeric / 1000) if numeric > 10_000_000_000 else int(numeric)

        if not isinstance(value, str):
            return None

        raw = value.strip()
        if not raw:
            return None

        if raw.isdigit():
            numeric = int(raw)
            return int(numeric / 1000) if numeric > 10_000_000_000 else numeric

        if raw.endswith("Z"):
            raw = f"{raw[:-1]}+00:00"

        # Normalize fractional seconds to microseconds for Python's parser.
        iso_match = re.match(
            r"^(?P<base>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?P<fraction>\.\d+)?(?P<tz>[+-]\d{2}:\d{2})?$",
            raw,
        )
        if iso_match:
            base = iso_match.group("base")
            fraction = iso_match.group("fraction") or ""
            tz = iso_match.group("tz") or "+00:00"
            if fraction:
                fraction_digits = fraction[1:7].ljust(6, "0")
                raw = f"{base}.{fraction_digits}{tz}"
            else:
                raw = f"{base}{tz}"

        try:
            parsed = datetime.fromisoformat(raw)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return int(parsed.timestamp())
        except ValueError:
            return None

    @classmethod
    def _get_market_start_ts(cls, market: dict) -> Optional[int]:
        for field in ("created_time", "open_time"):
            ts = cls._parse_iso_timestamp(market.get(field))
            if ts is not None:
                return ts
        return None

    async def _kalshi_get(self, path: str, url: str, params: dict | None = None) -> dict:
        """Single chokepoint for all Kalshi GET requests with semaphore + retry."""
        headers = self._get_kalshi_headers("GET", path)
        for attempt in range(4):
            async with self._kalshi_semaphore:
                async with self._session.get(url, params=params, headers=headers) as response:
                    if response.status == 429 and attempt < 3:
                        pass  # will sleep after releasing semaphore
                    else:
                        response.raise_for_status()
                        return await response.json()
            # Sleep OUTSIDE semaphore so other requests can proceed
            delay = 1.0 * (2 ** attempt)
            print(f"[kalshi] 429 on {path}, retry {attempt+1} in {delay}s")
            await asyncio.sleep(delay)
            headers = self._get_kalshi_headers("GET", path)
        return {}

    async def _get_events(self, status: str = "open", limit: int = 200) -> list[dict]:
        path = "/trade-api/v2/events"
        params = {"status": status, "limit": limit, "with_nested_markets": "true"}
        data = await self._kalshi_get(path, f"{KALSHI_BASE_URL}/events", params)
        return data.get("events", [])

    async def _get_markets_for_event(
        self, event_ticker: str, status: str = "open", limit: int = 50
    ) -> list[dict]:
        path = "/trade-api/v2/markets"
        params = {"status": status, "limit": limit, "event_ticker": event_ticker}
        data = await self._kalshi_get(path, f"{KALSHI_BASE_URL}/markets", params)
        return data.get("markets", [])

    async def _get_markets_by_series(
        self, series_ticker: str, status: str = "open", limit: int = 50
    ) -> list[dict]:
        path = "/trade-api/v2/markets"
        params = {"status": status, "limit": limit, "series_ticker": series_ticker}
        data = await self._kalshi_get(path, f"{KALSHI_BASE_URL}/markets", params)
        return data.get("markets", [])

    async def _get_market(self, ticker: str) -> dict:
        path = f"/trade-api/v2/markets/{ticker}"
        data = await self._kalshi_get(path, f"{KALSHI_BASE_URL}/markets/{ticker}")
        return data.get("market", {})

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
        data = await self._kalshi_get(path, f"{KALSHI_BASE_URL}/events/{event_ticker}")
        return data.get("event", {})

    async def _get_event_metadata(self, event_ticker: str) -> dict:
        path = f"/trade-api/v2/events/{event_ticker}/metadata"
        try:
            data = await self._kalshi_get(path, f"{KALSHI_BASE_URL}/events/{event_ticker}/metadata")
        except Exception as e:
            print(f"[metadata] Failed to get metadata for {event_ticker}: {e}")
            return {}
        print(f"[metadata] Raw response for {event_ticker}: {data}")
        if "event_metadata" in data:
            return data["event_metadata"]
        return data

    async def _resolve_market_image(
        self, event_ticker: str, market_ticker: str, event: dict | None = None
    ) -> str:
        """Resolve the best available image URL for a market."""
        if not event_ticker:
            return ""

        event_metadata = {}
        try:
            event_metadata = await self._get_event_metadata(event_ticker)
            print(f"[image] Event metadata for {event_ticker}: {event_metadata}")
        except Exception as e:
            print(f"[image] Failed to get metadata for {event_ticker}: {e}")
            return ""

        def to_full_url(path: str) -> str:
            if not path:
                return ""
            if path.startswith("/"):
                return f"https://kalshi.com{path}"
            return path

        def is_fallback(url: str) -> bool:
            return "structured_icons/" in url

        best_fallback = ""

        # 1. Series-level image (the event page image: trophy, logo, etc.)
        img = to_full_url(event_metadata.get("image_url", ""))
        if img and not is_fallback(img):
            return img
        if img and not best_fallback:
            best_fallback = img

        # 2. Market-specific image (exact ticker match), skip fallback icons
        first_non_fallback_market_image = ""
        for md in event_metadata.get("market_details", []):
            img = to_full_url(md.get("image_url", ""))
            if not img:
                continue
            if is_fallback(img):
                if not best_fallback:
                    best_fallback = img
                continue
            if not first_non_fallback_market_image:
                first_non_fallback_market_image = img
            if md.get("market_ticker") == market_ticker:
                return img

        # 3. Featured image
        img = to_full_url(event_metadata.get("featured_image_url", ""))
        if img and not is_fallback(img):
            return img
        if img and not best_fallback:
            best_fallback = img

        # 4. First non-fallback market_details image
        if first_non_fallback_market_image:
            return first_non_fallback_market_image

        # 5. Event object fallback
        if event:
            img = to_full_url(event.get("image_url", ""))
            if img and not is_fallback(img):
                return img
            if img and not best_fallback:
                best_fallback = img

        # 6. Last resort: use the fallback icon (better than nothing)
        return best_fallback

    async def get_candlesticks(
        self,
        series_ticker: str,
        ticker: str,
        period_interval: int = 60,
        hours: int = 24,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
    ) -> list[dict]:
        """Fetch price history for a market. period_interval: 1, 60, or 1440 min."""
        if not series_ticker or not ticker:
            return []
        own_session = self._session is None
        if own_session:
            self._session = aiohttp.ClientSession()
        try:
            now = int(time.time())
            resolved_end_ts = end_ts if end_ts is not None else now
            resolved_start_ts = start_ts if start_ts is not None else (resolved_end_ts - (hours * 3600))

            if resolved_start_ts >= resolved_end_ts:
                return []

            path = f"/trade-api/v2/series/{series_ticker}/markets/{ticker}/candlesticks"
            params = {
                "start_ts": int(resolved_start_ts),
                "end_ts": int(resolved_end_ts),
                "period_interval": period_interval,
                "include_latest_before_start": "true",
            }
            data = await self._kalshi_get(
                path, f"{KALSHI_BASE_URL}/series/{series_ticker}/markets/{ticker}/candlesticks", params
            )
            candlesticks = data.get("candlesticks", [])
            points: list[dict] = []
            for c in candlesticks:
                ts = c.get("end_period_ts")
                price_cents = self._extract_candle_close_cents(c)
                if ts is None or price_cents is None:
                    continue
                try:
                    ts_int = int(ts)
                except (TypeError, ValueError):
                    continue
                points.append({
                    "ts": ts_int,
                    "price": round(max(0.0, min(100.0, price_cents)), 2),
                })

            deduped = {p["ts"]: p["price"] for p in points}
            return [{"ts": ts, "price": price} for ts, price in sorted(deduped.items())]
        finally:
            if own_session:
                await self._session.close()
                self._session = None

    async def _get_channel_thumbnail(self, channel_id: str) -> str:
        url = "https://www.googleapis.com/youtube/v3/channels"
        params = {"part": "snippet", "id": channel_id, "key": self.youtube_api_key}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    response.raise_for_status()
                    data = await response.json()
            items = data.get("items", [])
            if items:
                thumbnails = items[0].get("snippet", {}).get("thumbnails", {})
                return (
                    thumbnails.get("default", {}).get("url", "")
                    or thumbnails.get("medium", {}).get("url", "")
                )
        except Exception as e:
            print(f"[channel_thumbnail] Failed to fetch for {channel_id}: {e}")
        return ""

    async def get_video_metadata(self, video_id: str) -> dict:
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {"part": "snippet", "id": video_id, "key": self.youtube_api_key}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()

        if not data.get("items"):
            return {"title": "", "description": "", "channel": "", "thumbnail": "", "channel_thumbnail": ""}

        snippet = data["items"][0]["snippet"]
        channel_id = snippet.get("channelId", "")
        channel_thumbnail = ""
        if channel_id:
            channel_thumbnail = await self._get_channel_thumbnail(channel_id)

        return {
            "title": snippet.get("title", ""),
            "description": snippet.get("description", "")[:500],
            "channel": snippet.get("channelTitle", ""),
            "thumbnail": (
                snippet.get("thumbnails", {}).get("maxres", {}).get("url")
                or snippet.get("thumbnails", {}).get("high", {}).get("url", "")
            ),
            "channel_thumbnail": channel_thumbnail,
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

    async def _build_market_dict(self, market: dict, event: dict, series_ticker: str, keywords: list[str]) -> dict:
        event_ticker = event.get("event_ticker", "") or market.get("event_ticker", "")
        ticker = market.get("ticker", "")
        formatted = await self._format_market_display(market, event, keywords)
        image = await self._resolve_market_image(event_ticker, ticker, event)

        market_details: dict = {}
        market_start_ts = self._get_market_start_ts(market)
        if market_start_ts is None:
            try:
                market_details = await self._get_market(ticker)
                market_start_ts = self._get_market_start_ts(market_details)
            except Exception as e:
                print(f"[market] Failed to get details for {ticker}: {e}")

        market_source = market_details or market
        resolved_series_ticker = (
            series_ticker
            or market_source.get("series_ticker", "")
            or event.get("series_ticker", "")
        )
        yes_price = self._to_cents(market_source.get("yes_bid"), market_source.get("yes_bid_dollars"))
        no_price = self._to_cents(market_source.get("no_bid"), market_source.get("no_bid_dollars"))
        price_history = []
        try:
            if resolved_series_ticker and market_start_ts is not None:
                price_history = await self.get_candlesticks(
                    resolved_series_ticker,
                    ticker,
                    period_interval=1440,
                    start_ts=market_start_ts,
                )
            elif resolved_series_ticker:
                price_history = await self.get_candlesticks(resolved_series_ticker, ticker, 1440, 24 * 365)
        except Exception as e:
            print(f"[candlestick] Failed for {ticker}: {e}")
        return {
            "ticker": ticker,
            "event_ticker": event_ticker,
            "series_ticker": resolved_series_ticker,
            "question": formatted.get("question", ""),
            "outcome": formatted.get("outcome", ""),
            "created_time": market_source.get("created_time"),
            "open_time": market_source.get("open_time"),
            "market_start_ts": market_start_ts,
            "yes_price": round(yes_price or 0, 2),
            "no_price": round(no_price or 0, 2),
            "volume": market.get("volume", 0),
            "image_url": image,
            "price_history": price_history,
        }

    async def match_video(self, video_id: str) -> Optional[dict]:
        own_session = self._session is None
        if own_session:
            self._session = aiohttp.ClientSession()
        try:
            return await self._match_video_inner(video_id)
        finally:
            if own_session:
                await self._session.close()
                self._session = None

    async def _match_video_inner(self, video_id: str) -> Optional[dict]:
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
                event_ticker = markets[0].get("event_ticker", "")
                if event_ticker:
                    try:
                        best_event = await self._get_event(event_ticker)
                    except Exception:
                        pass
                selected = markets[:10]
                series_ticker = best_event.get("series_ticker", "")
                print(f"[{video_id}] SUCCESS (series) - {len(selected)} markets")
                kalshi_list = await asyncio.gather(*[
                    self._build_market_dict(m, best_event, series_ticker, keywords)
                    for m in selected
                ])
                return {
                    "youtube": {
                        "video_id": video_id,
                        "title": metadata["title"],
                        "thumbnail": metadata["thumbnail"],
                        "channel": metadata["channel"],
                        "channel_thumbnail": metadata.get("channel_thumbnail", ""),
                    },
                    "kalshi": list(kalshi_list),
                    "keywords": keywords,
                }

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

        selected = markets[:10]
        series_ticker = best_event.get("series_ticker", "")
        print(f"[{video_id}] SUCCESS (event) - {len(selected)} markets")
        kalshi_list = await asyncio.gather(*[
            self._build_market_dict(m, best_event, series_ticker, keywords)
            for m in selected
        ])

        return {
            "youtube": {
                "video_id": video_id,
                "title": metadata["title"],
                "thumbnail": metadata["thumbnail"],
                "channel": metadata["channel"],
                "channel_thumbnail": metadata.get("channel_thumbnail", ""),
            },
            "kalshi": list(kalshi_list),
            "keywords": keywords,
        }

    async def get_feed(self, video_ids: list[str]) -> list[dict]:
        self._session = aiohttp.ClientSession()
        try:
            tasks = [self.match_video(vid) for vid in video_ids]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            feed = []
            for vid, r in zip(video_ids, results):
                if isinstance(r, Exception):
                    print(f"[{vid}] FAILED: {r}", flush=True)
                elif r:
                    feed.append(r)
            return feed
        finally:
            await self._session.close()
            self._session = None
