"""OpenAI Responses web_search 기반 검색 서비스."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from openai import AsyncOpenAI

from services.naver_search_service import SearchResultItem
from services.usage_tracker import tracker


class OpenAIWebSearchService:
    def __init__(self, client: AsyncOpenAI):
        self.client = client

    async def search(self, section: str, query: str) -> list[SearchResultItem]:
        prompt = (
            f"Search the web for evidence for the Korean market research section '{section}'. "
            f"Focus on sources relevant to this query: {query}. "
            "Write a short answer with inline citations so the response contains source annotations."
        )
        response = await self.client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            tools=[
                {
                    "type": "web_search",
                    "search_context_size": "high",
                    "user_location": {
                        "type": "approximate",
                        "country": "KR",
                        "timezone": "Asia/Seoul",
                    },
                }
            ],
            include=["web_search_call.action.sources"],
            max_output_tokens=500,
            timeout=20,
        )
        self._log_usage(response)
        return self._normalize_response(query=query, response=response)

    def _normalize_response(self, query: str, response) -> list[SearchResultItem]:
        items: list[SearchResultItem] = []
        seen_urls: set[str] = set()

        for output in getattr(response, "output", []):
            if getattr(output, "type", "") != "message":
                continue
            for content in getattr(output, "content", []):
                text = getattr(content, "text", "") or ""
                for annotation in getattr(content, "annotations", []):
                    if getattr(annotation, "type", "") != "url_citation":
                        continue
                    url = self._clean_url(getattr(annotation, "url", ""))
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    title = (getattr(annotation, "title", "") or "").strip() or url
                    snippet = self._extract_snippet(text, title)
                    items.append(
                        SearchResultItem(
                            source_type=self._classify_source_type(url),
                            source_engine="openai_web",
                            query=query,
                            title=title,
                            url=url,
                            publisher=self._publisher_from_url(url),
                            published_at=None,
                            snippet=snippet,
                        )
                    )
        return items

    def _extract_snippet(self, text: str, title: str) -> str:
        if not text:
            return title
        normalized = re.sub(r"\s+", " ", text).strip()
        sentence = normalized.split("\n")[0]
        return sentence[:260].strip() or title

    def _classify_source_type(self, url: str) -> str:
        host = urlparse(url).netloc.lower()
        path = urlparse(url).path.lower()
        if path.endswith(".pdf") or any(token in host for token in ["gov", "ac.", "or.", "research", "report", "statista", "imarc", "grandviewresearch", "expertmarketresearch"]):
            return "doc"
        if any(token in host for token in ["news", "press", "wire", "globenewswire", "yna.co.kr", "chosun", "joongang", "donga", "hani", "khan", "mk.co.kr", "sedaily"]):
            return "news"
        if "blog." in host or "medium.com" in host or "tistory.com" in host:
            return "blog"
        if "cafe." in host:
            return "cafearticle"
        return "webkr" if host.endswith(".kr") else "webkr"

    def _publisher_from_url(self, url: str) -> str:
        return urlparse(url).netloc.replace("www.", "")

    def _clean_url(self, url: str) -> str:
        return re.sub(r"\?utm_source=openai$", "", url.strip())

    def _log_usage(self, response) -> None:
        usage = getattr(response, "usage", None)
        if not usage:
            return
        tracker.log(
            service="research/openai_web_search",
            model="gpt-4.1-mini",
            input_tokens=getattr(usage, "input_tokens", 0),
            output_tokens=getattr(usage, "output_tokens", 0),
        )
