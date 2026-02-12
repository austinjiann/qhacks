import ssl

import aiohttp

from utils.env import settings

# Disable SSL verification for local dev (macOS Python SSL cert issue)
_ssl_context = ssl.create_default_context()
_ssl_context.check_hostname = False
_ssl_context.verify_mode = ssl.CERT_NONE


class YoutubeService:
    def __init__(self) -> None:
        self.api_key = settings.YOUTUBE_API_KEY
        self._connector = aiohttp.TCPConnector(ssl=_ssl_context)

    async def _get_channel_thumbnail(self, channel_id: str) -> str:
        url = "https://www.googleapis.com/youtube/v3/channels"
        params = {"part": "snippet", "id": channel_id, "key": self.api_key}
        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=_ssl_context)) as session:
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
        except Exception as e:  # pragma: no cover - logging side effect only
            print(f"[channel_thumbnail] Failed to fetch for {channel_id}: {e}")
        return ""

    async def batch_check_embeddable(self, video_ids: list[str]) -> list[str]:
        """Filter video IDs to only those that are embeddable."""
        if not video_ids:
            return []

        embeddable_ids: list[str] = []
        # YouTube API allows up to 50 IDs per request
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]
            url = "https://www.googleapis.com/youtube/v3/videos"
            params = {
                "part": "status",
                "id": ",".join(batch),
                "key": self.api_key,
            }
            try:
                async with aiohttp.ClientSession(
                    connector=aiohttp.TCPConnector(ssl=_ssl_context)
                ) as session:
                    async with session.get(url, params=params) as response:
                        response.raise_for_status()
                        data = await response.json()

                for item in data.get("items", []):
                    video_id = item.get("id", "")
                    status = item.get("status", {})
                    if not status.get("embeddable", True):
                        print(f"[embed_check] {video_id}: not embeddable, skipping")
                        continue
                    embeddable_ids.append(video_id)
            except Exception as e:
                print(f"[embed_check] Batch check failed: {e}")
                # On failure, pass through all IDs rather than blocking them
                embeddable_ids.extend(batch)

        return embeddable_ids

    async def get_video_metadata(self, video_id: str) -> dict:
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {"part": "snippet,status", "id": video_id, "key": self.api_key}
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=_ssl_context)) as session:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()

        if not data.get("items"):
            return {
                "title": "",
                "description": "",
                "channel": "",
                "thumbnail": "",
                "channel_thumbnail": "",
                "embeddable": False,
            }

        item = data["items"][0]
        snippet = item["snippet"]
        status = item.get("status", {})
        embeddable = status.get("embeddable", True)
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
            "embeddable": embeddable,
        }
