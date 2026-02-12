import asyncio
import json
import re
import time
from typing import Optional

from openai import AsyncOpenAI

from services.kalshi_service import KalshiService
from services.youtube_service import YoutubeService
from utils.env import settings

# Module-level cache for open Kalshi events (survives across scoped FeedService instances)
_events_cache: list[dict] = []
_events_cache_ts: float = 0.0
_EVENTS_CACHE_TTL: float = 300.0  # 5 minutes
_events_cache_lock: asyncio.Lock | None = None


class FeedService:
    def __init__(self, youtube_service: YoutubeService, kalshi_service: KalshiService) -> None:
        self.openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.youtube_service = youtube_service
        self.kalshi_service = kalshi_service

    async def _extract_keywords(self, title: str, description: str) -> list[str]:
        prompt = f"""Extract 3-5 keywords from this YouTube video that could match prediction market trades.
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

Create a clean, user-friendly trade display:
1. "question": A clear, concise yes/no question about this trade (e.g., "Will Arsenal win today?")
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

    async def _build_market_dict(
        self, market: dict, event: dict, series_ticker: str, keywords: list[str]
    ) -> dict:
        event_ticker = event.get("event_ticker", "") or market.get("event_ticker", "")
        ticker = market.get("ticker", "")
        formatted = await self._format_market_display(market, event, keywords)
        image = await self.kalshi_service.resolve_market_image(
            event_ticker, ticker, event, series_ticker=series_ticker
        )

        market_details: dict = {}
        market_start_ts = self.kalshi_service.get_market_start_ts(market)
        if market_start_ts is None:
            try:
                market_details = await self.kalshi_service.get_market(ticker)
                market_start_ts = self.kalshi_service.get_market_start_ts(market_details)
            except Exception as e:
                print(f"[market] Failed to get details for {ticker}: {e}")

        market_source = market_details or market
        resolved_series_ticker = (
            series_ticker
            or market_source.get("series_ticker", "")
            or event.get("series_ticker", "")
        )
        yes_price = self.kalshi_service.to_cents(
            market_source.get("yes_bid"), market_source.get("yes_bid_dollars")
        )
        no_price = self.kalshi_service.to_cents(
            market_source.get("no_bid"), market_source.get("no_bid_dollars")
        )

        price_history = []
        try:
            if resolved_series_ticker and market_start_ts is not None:
                price_history = await self.kalshi_service.get_candlesticks(
                    resolved_series_ticker,
                    ticker,
                    period_interval=60,
                    start_ts=market_start_ts,
                )
            elif resolved_series_ticker:
                price_history = await self.kalshi_service.get_candlesticks(
                    resolved_series_ticker,
                    ticker,
                    60,
                    24 * 30,
                )
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

    async def _get_cached_events(self) -> list[dict]:
        """Return cached open events, refreshing if stale (>5 min)."""
        global _events_cache, _events_cache_ts, _events_cache_lock
        if _events_cache_lock is None:
            _events_cache_lock = asyncio.Lock()
        now = time.monotonic()
        if _events_cache and (now - _events_cache_ts) < _EVENTS_CACHE_TTL:
            return _events_cache
        async with _events_cache_lock:
            # Double-check after acquiring lock
            now = time.monotonic()
            if _events_cache and (now - _events_cache_ts) < _EVENTS_CACHE_TTL:
                return _events_cache
            print("[cache] Refreshing Kalshi events cache...")
            events = await self.kalshi_service.get_all_events()
            _events_cache = events
            _events_cache_ts = time.monotonic()
            print(f"[cache] Cached {len(events)} open events")
            return _events_cache

    async def _match_event_via_openai(
        self, keywords: list[str], events: list[dict]
    ) -> Optional[dict]:
        """Use GPT-4o-mini to pick the best matching event from a numbered list."""
        if not events:
            return None

        lines: list[str] = []
        for i, event in enumerate(events):
            title = event.get("title", "Unknown")
            category = event.get("category", "")
            suffix = f" [{category}]" if category else ""
            lines.append(f"{i + 1}. {title}{suffix}")

        event_list_str = "\n".join(lines)
        keywords_str = ", ".join(keywords)

        prompt = f"""You are matching a YouTube video to a prediction market event.

Video keywords: {keywords_str}

Below is a numbered list of open prediction market events. Pick the ONE event that is most relevant to the video keywords. If no event is even remotely relevant, respond with just the number 0.

Respond with ONLY the number of the best matching event (e.g., "42"). No explanation.

{event_list_str}"""

        try:
            response = await self.openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=10,
            )
            answer = response.choices[0].message.content.strip()
            match = re.search(r"\d+", answer)
            if not match:
                return None
            idx = int(match.group()) - 1  # 1-indexed to 0-indexed
            if idx < 0 or idx >= len(events):
                return None
            return events[idx]
        except Exception as e:
            print(f"[openai] Event matching failed: {e}")
            return None

    @staticmethod
    def _extract_open_markets(event: dict) -> list[dict]:
        """Extract nested open markets from an event dict."""
        markets = event.get("markets", [])
        if not markets:
            return []
        return [m for m in markets if m.get("status") == "open"]

    async def match_video(self, video_id: str) -> Optional[dict]:
        await self.kalshi_service.ensure_session()
        try:
            return await self._match_video_inner(video_id)
        finally:
            await self.kalshi_service.close_session()

    async def _match_video_inner(self, video_id: str) -> Optional[dict]:
        await self.kalshi_service.ensure_session()
        print(f"[{video_id}] Starting match...")
        metadata = await self.youtube_service.get_video_metadata(video_id)
        print(f"[{video_id}] Title: {metadata.get('title', 'No title')}")

        keywords = await self._extract_keywords(metadata["title"], metadata["description"])
        print(f"[{video_id}] Keywords: {keywords}")

        if not keywords:
            print(f"[{video_id}] FAILED: No keywords extracted")
            return None

        series = self.kalshi_service.detect_series_from_keywords(keywords)
        best_event = {}

        if series:
            print(f"[{video_id}] Detected series: {series}")
            markets = await self.kalshi_service.get_markets_by_series(series, limit=50)
            print(f"[{video_id}] Markets from series: {len(markets)}")
            if markets:
                event_ticker = markets[0].get("event_ticker", "")
                if event_ticker:
                    try:
                        best_event = await self.kalshi_service.get_event(event_ticker)
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

        # ── Fallback: semantic matching across all open events ──
        print(f"[{video_id}] No series match, trying semantic fallback...")
        try:
            all_events = await self._get_cached_events()
            if not all_events:
                print(f"[{video_id}] SKIPPED: no events available for fallback")
                return None

            matched_event = await self._match_event_via_openai(keywords, all_events)
            if not matched_event:
                print(f"[{video_id}] SKIPPED: no relevant event found")
                return None

            event_title = matched_event.get("title", "Unknown")
            event_ticker = matched_event.get("event_ticker", "")
            print(f"[{video_id}] Semantic match: {event_title} ({event_ticker})")

            markets = self._extract_open_markets(matched_event)
            if not markets and event_ticker:
                print(f"[{video_id}] No nested markets, fetching explicitly...")
                markets = await self.kalshi_service.get_markets_for_event(
                    event_ticker, limit=50
                )

            if not markets:
                print(f"[{video_id}] SKIPPED: matched event has no open markets")
                return None

            selected = markets[:10]
            series_ticker = matched_event.get("series_ticker", "")
            print(f"[{video_id}] SUCCESS (semantic) - {len(selected)} markets from '{event_title}'")

            kalshi_list = await asyncio.gather(*[
                self._build_market_dict(m, matched_event, series_ticker, keywords)
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
        except Exception as e:
            print(f"[{video_id}] FAILED (semantic fallback): {e}")
            return None

    async def get_feed(self, video_ids: list[str]) -> list[dict]:
        await self.kalshi_service.ensure_session()
        try:
            tasks = [self._match_video_inner(vid) for vid in video_ids]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            feed = []
            for vid, result in zip(video_ids, results):
                if isinstance(result, Exception):
                    print(f"[{vid}] FAILED: {result}", flush=True)
                elif result:
                    feed.append(result)
            return feed
        finally:
            await self.kalshi_service.close_session()

    async def get_trade_advice(
        self,
        question: str,
        side: str,
        amount: float,
        yes_price: float,
        no_price: float,
    ) -> str:
        price = yes_price if side.upper() == "YES" else no_price
        prompt = f"""You are Joe, a friendly and slightly sarcastic trading advisor. Keep it very brief.

Format: One short sentence (max 15 words), then exactly 3 bullet points (each max 10 words). Use this exact format:
<sentence>
- <point 1>
- <point 2>
- <point 3>

Market: {question}
Trade side: {side}
Amount: ${amount}
Current odds: {side} at {price}¢

Give your quick take on this trade. Be casual and fun."""

        try:
            response = await self.openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=200,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Hmm, I'm having trouble thinking right now... but ${amount} on {side}? Just make sure you're okay losing it!"

    async def get_candlesticks(
        self,
        series_ticker: str,
        ticker: str,
        period_interval: int = 60,
        hours: int = 24,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
    ) -> list[dict]:
        await self.kalshi_service.ensure_session()
        try:
            return await self.kalshi_service.get_candlesticks(
                series_ticker,
                ticker,
                period_interval=period_interval,
                hours=hours,
                start_ts=start_ts,
                end_ts=end_ts,
            )
        finally:
            await self.kalshi_service.close_session()