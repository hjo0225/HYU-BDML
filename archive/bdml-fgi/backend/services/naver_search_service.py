"""네이버 검색 API 클라이언트."""
import html
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


NAVER_SOURCE_TYPES = {"news", "webkr", "blog", "cafearticle", "doc"}
_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(slots=True)
class SearchResultItem:
    source_type: str
    source_engine: str
    query: str
    title: str
    url: str
    publisher: str | None
    published_at: str | None
    snippet: str


class TTLMemoryCache:
    def __init__(self, ttl_seconds: int = 900):
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, tuple[float, list[SearchResultItem]]] = {}

    def get(self, key: str) -> list[SearchResultItem] | None:
        cached = self._store.get(key)
        if not cached:
            return None
        expires_at, value = cached
        if expires_at < time.time():
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: list[SearchResultItem]) -> None:
        self._store[key] = (time.time() + self.ttl_seconds, value)


class NaverSearchService:
    base_url = "https://openapi.naver.com/v1/search"

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        cache: TTLMemoryCache | None = None,
    ):
        self.client_id = client_id or os.getenv("NAVER_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("NAVER_CLIENT_SECRET")
        self.cache = cache or TTLMemoryCache()

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def search(
        self,
        source_type: str,
        query: str,
        display: int = 5,
        start: int = 1,
        sort: str = "sim",
    ) -> list[SearchResultItem]:
        if source_type not in NAVER_SOURCE_TYPES:
            raise ValueError(f"지원하지 않는 네이버 검색 타입입니다: {source_type}")
        if not self.is_configured():
            raise RuntimeError("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수가 필요합니다.")

        cache_key = f"{source_type}|{query}|{display}|{start}|{sort}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        params = urlencode(
            {
                "query": query,
                "display": max(1, min(display, 100)),
                "start": max(1, start),
                "sort": sort,
            }
        )
        request = Request(
            f"{self.base_url}/{source_type}.json?{params}",
            headers={
                "X-Naver-Client-Id": self.client_id or "",
                "X-Naver-Client-Secret": self.client_secret or "",
            },
            method="GET",
        )

        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))

        items = [
            self._normalize_item(source_type=source_type, query=query, raw=item)
            for item in payload.get("items", [])
        ]
        self.cache.set(cache_key, items)
        return items

    def _normalize_item(self, source_type: str, query: str, raw: dict[str, Any]) -> SearchResultItem:
        raw_url = (raw.get("originallink") or raw.get("link") or "").strip()
        parsed = urlparse(raw_url)
        publisher = self._extract_publisher(raw, parsed.netloc)
        return SearchResultItem(
            source_type=source_type,
            source_engine="naver",
            query=query,
            title=self._clean_text(raw.get("title")),
            url=raw_url,
            publisher=publisher,
            published_at=self._normalize_date(raw),
            snippet=self._clean_text(raw.get("description")),
        )

    def _extract_publisher(self, raw: dict[str, Any], hostname: str) -> str | None:
        publisher = self._clean_text(raw.get("publisher"))
        if publisher:
            return publisher
        if hostname:
            return hostname.replace("www.", "")
        return None

    def _normalize_date(self, raw: dict[str, Any]) -> str | None:
        for key in ("pubDate", "datetime"):
            value = raw.get(key)
            if not value:
                continue
            try:
                if key == "pubDate":
                    return parsedate_to_datetime(value).date().isoformat()
                return datetime.fromisoformat(str(value)).date().isoformat()
            except Exception:
                return str(value)
        return None

    def _clean_text(self, value: Any) -> str:
        text = html.unescape(str(value or ""))
        text = _TAG_RE.sub("", text)
        return re.sub(r"\s+", " ", text).strip()
