import asyncio
import base64
import re
import ssl
import time
from datetime import datetime, timezone
from typing import Optional

import aiohttp
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from utils.env import settings

# Disable SSL verification for local dev (macOS Python SSL cert issue)
_ssl_context = ssl.create_default_context()
_ssl_context.check_hostname = False
_ssl_context.verify_mode = ssl.CERT_NONE

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


class KalshiService:
    def __init__(self) -> None:
        self.api_key = settings.KALSHI_API_KEY
        self.private_key = self._load_private_key()
        self._kalshi_semaphore = asyncio.Semaphore(5)
        self._session: aiohttp.ClientSession | None = None

    async def ensure_session(self) -> None:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=_ssl_context))

    async def close_session(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    def detect_series_from_keywords(self, keywords: list[str]) -> Optional[str]:
        keywords_lower = " ".join(keywords).lower()
        priority_terms = [
            "world cup",
            "fifa",
            "soccer",
            "super bowl",
            "bitcoin",
            "btc",
            "crypto",
        ]
        for term in priority_terms:
            if term in keywords_lower and term in SPORTS_CRYPTO_SERIES:
                return SPORTS_CRYPTO_SERIES[term]
        for term, series in SPORTS_CRYPTO_SERIES.items():
            if term in keywords_lower:
                return series
        return None

    def _load_private_key(self):
        with open(settings.KALSHI_PRIVATE_KEY_PATH, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)

    def _sign_request(self, method: str, path: str, timestamp_ms: int) -> str:
        message = f"{timestamp_ms}{method}{path}"
        signature = self.private_key.sign(
            message.encode("utf-8"),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode("utf-8")

    def _get_headers(self, method: str, path: str) -> dict:
        timestamp_ms = int(time.time() * 1000)
        signature = self._sign_request(method, path, timestamp_ms)
        return {
            "KALSHI-ACCESS-KEY": self.api_key,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": str(timestamp_ms),
            "Content-Type": "application/json",
        }

    async def _kalshi_get(self, path: str, url: str, params: dict | None = None) -> dict:
        await self.ensure_session()
        headers = self._get_headers("GET", path)
        for attempt in range(4):
            async with self._kalshi_semaphore:
                assert self._session is not None
                async with self._session.get(url, params=params, headers=headers) as response:
                    if response.status == 429 and attempt < 3:
                        pass  # will sleep after releasing semaphore
                    else:
                        response.raise_for_status()
                        return await response.json()
            delay = 1.0 * (2 ** attempt)
            print(f"[kalshi] 429 on {path}, retry {attempt + 1} in {delay}s")
            await asyncio.sleep(delay)
            headers = self._get_headers("GET", path)
        return {}

    async def get_events(self, status: str = "open", limit: int = 200) -> list[dict]:
        path = "/trade-api/v2/events"
        params = {"status": status, "limit": limit, "with_nested_markets": "true"}
        data = await self._kalshi_get(path, f"{KALSHI_BASE_URL}/events", params)
        return data.get("events", [])

    async def get_markets_for_event(
        self, event_ticker: str, status: str = "open", limit: int = 50
    ) -> list[dict]:
        path = "/trade-api/v2/markets"
        params = {"status": status, "limit": limit, "event_ticker": event_ticker}
        data = await self._kalshi_get(path, f"{KALSHI_BASE_URL}/markets", params)
        return data.get("markets", [])

    async def get_markets_by_series(
        self, series_ticker: str, status: str = "open", limit: int = 50
    ) -> list[dict]:
        path = "/trade-api/v2/markets"
        params = {"status": status, "limit": limit, "series_ticker": series_ticker}
        data = await self._kalshi_get(path, f"{KALSHI_BASE_URL}/markets", params)
        return data.get("markets", [])

    async def get_market(self, ticker: str) -> dict:
        path = f"/trade-api/v2/markets/{ticker}"
        data = await self._kalshi_get(path, f"{KALSHI_BASE_URL}/markets/{ticker}")
        return data.get("market", {})

    async def get_event(self, event_ticker: str) -> dict:
        path = f"/trade-api/v2/events/{event_ticker}"
        data = await self._kalshi_get(path, f"{KALSHI_BASE_URL}/events/{event_ticker}")
        return data.get("event", {})

    async def get_event_metadata(self, event_ticker: str) -> dict:
        path = f"/trade-api/v2/events/{event_ticker}/metadata"
        try:
            data = await self._kalshi_get(path, f"{KALSHI_BASE_URL}/events/{event_ticker}/metadata")
        except Exception as e:  # pragma: no cover - diagnostic logging
            print(f"[metadata] Failed to get metadata for {event_ticker}: {e}")
            return {}
        print(f"[metadata] Raw response for {event_ticker}: {data}")
        if "event_metadata" in data:
            return data["event_metadata"]
        return data

    async def resolve_market_image(
        self, event_ticker: str, market_ticker: str, event: dict | None = None
    ) -> str:
        if not event_ticker:
            return ""

        try:
            event_metadata = await self.get_event_metadata(event_ticker)
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

        img = to_full_url(event_metadata.get("image_url", ""))
        if img and not is_fallback(img):
            return img
        if img and not best_fallback:
            best_fallback = img

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

        img = to_full_url(event_metadata.get("featured_image_url", ""))
        if img and not is_fallback(img):
            return img
        if img and not best_fallback:
            best_fallback = img

        if first_non_fallback_market_image:
            return first_non_fallback_market_image

        if event:
            img = to_full_url(event.get("image_url", ""))
            if img and not is_fallback(img):
                return img
            if img and not best_fallback:
                best_fallback = img

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
        if not series_ticker or not ticker:
            return []

        now = int(time.time())
        resolved_end_ts = end_ts if end_ts is not None else now
        resolved_end_ts = max(1, int(resolved_end_ts))
        resolved_start_ts = start_ts if start_ts is not None else (resolved_end_ts - (hours * 3600))
        resolved_start_ts = max(0, int(resolved_start_ts))

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
            path,
            f"{KALSHI_BASE_URL}/series/{series_ticker}/markets/{ticker}/candlesticks",
            params,
        )
        candlesticks = data.get("candlesticks", [])
        points: list[dict] = []
        for candle in candlesticks:
            ts = candle.get("end_period_ts")
            price_cents = self._extract_candle_close_cents(candle)
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

    @staticmethod
    def _to_float(value: object) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def to_cents(cls, cents_value: object = None, dollars_value: object = None) -> Optional[float]:
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
                close_cents = cls.to_cents(payload.get("close"), payload.get("close_dollars"))
                if close_cents is not None:
                    return close_cents

        synthetic_previous = cls.to_cents(
            candle.get("previous_price"), candle.get("previous_price_dollars")
        )
        if synthetic_previous is not None:
            return synthetic_previous

        price_payload = candle.get("price", {})
        if isinstance(price_payload, dict):
            previous = cls.to_cents(
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
            ts_seconds = int(parsed.timestamp())
            if ts_seconds <= 0:
                return None
            return ts_seconds
        except ValueError:
            return None

    @classmethod
    def get_market_start_ts(cls, market: dict) -> Optional[int]:
        for field in ("created_time", "open_time"):
            ts = cls._parse_iso_timestamp(market.get(field))
            if ts is not None:
                return ts
        return None
