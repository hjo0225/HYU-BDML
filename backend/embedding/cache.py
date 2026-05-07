"""임베딩 JSON 캐시 — 동시 접근 금지 (CLAUDE.md 참조).

캐시 파일은 .gitignore 대상.
"""
from __future__ import annotations

import json
import os

_DEFAULT_CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "embedding_cache.json")


def load_cache(path: str = _DEFAULT_CACHE_PATH) -> dict[str, list[float]]:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_cache(cache: dict[str, list[float]], path: str = _DEFAULT_CACHE_PATH) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


def get_cached(text: str, path: str = _DEFAULT_CACHE_PATH) -> list[float] | None:
    cache = load_cache(path)
    return cache.get(text)


def set_cached(text: str, embedding: list[float], path: str = _DEFAULT_CACHE_PATH) -> None:
    cache = load_cache(path)
    cache[text] = embedding
    save_cache(cache, path)
