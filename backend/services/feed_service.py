import asyncio
import json
from typing import Optional

from openai import AsyncOpenAI

from services.kalshi_service import KalshiService
from services.youtube_service import YoutubeService
from utils.env import settings


class FeedService:
    def __init__(self, youtube_service: YoutubeService, kalshi_service: KalshiService) -> None:
        self.openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.youtube_service = youtube_service
        self.kalshi_service = kalshi_service

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
        event_titles = [f"{i}: {e.get('title', 'Unknown')}" for i, e in enumerate(events)]
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

    async def _build_market_dict(
        self, market: dict, event: dict, series_ticker: str, keywords: list[str]
    ) -> dict:
        event_ticker = event.get("event_ticker", "") or market.get("event_ticker", "")
        ticker = market.get("ticker", "")
        formatted = await self._format_market_display(market, event, keywords)
        image = await self.kalshi_service.resolve_market_image(event_ticker, ticker, event)

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
                    period_interval=1440,
                    start_ts=market_start_ts,
                )
            elif resolved_series_ticker:
                price_history = await self.kalshi_service.get_candlesticks(
                    resolved_series_ticker,
                    ticker,
                    1440,
                    24 * 365,
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

        events = await self.kalshi_service.get_events(status="open", limit=200)
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
            markets = await self.kalshi_service.get_markets_for_event(best_event.get("event_ticker", ""))

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
